//! JSON API とバイナリ配信: 自動保存（競合検知付き）・画像アップロード・
//! ノート一覧・更新時刻・テンプレート・vendored ライブラリの配信。

use std::time::{SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};
use topcoat::{
    context::Cx,
    router::{query_params, route, Bytes, Json, RouterErrorExt},
    Result,
};

use crate::vault::{is_md, mtime_ms};
use crate::{config, index, markdown, vault};

// ---------- 保存（自動保存 + 競合検知） ----------

#[derive(Deserialize)]
struct SaveReq {
    path: String,
    content: String,
    /// クライアントがファイルを読み込んだ時点の mtime（ms）。
    /// None のときは競合チェックをせず上書きする（新規作成・強制上書き）。
    base_mtime: Option<u64>,
}

#[derive(Serialize)]
struct SaveResp {
    ok: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    conflict: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    mtime: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    html: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
}

#[route(POST "/api/save")]
async fn save(Json(req): Json<SaveReq>) -> Result<Json<SaveResp>> {
    let v = vault::instance();
    // 競合チェック: 読み込み後に他プロセス（Claude Code 等）が書き換えていたら止める
    if let (Some(base), Some(abs)) = (req.base_mtime, v.resolve_note(&req.path)) {
        if let Some(current) = mtime_ms(&abs) {
            if current > base {
                return Ok(Json(SaveResp {
                    ok: false,
                    conflict: Some(true),
                    mtime: Some(current),
                    html: None,
                    error: Some("ファイルが外部で変更されています".to_string()),
                }));
            }
        }
    }
    match v.write_note(&req.path, &req.content) {
        Ok(()) => {
            index::mark_dirty();
            let mtime = v.resolve_note(&req.path).and_then(|p| mtime_ms(&p));
            Ok(Json(SaveResp {
                ok: true,
                conflict: None,
                mtime,
                html: Some(markdown::render(&req.path, &req.content)),
                error: None,
            }))
        }
        Err(e) => Ok(Json(SaveResp {
            ok: false,
            conflict: None,
            mtime: None,
            html: None,
            error: Some(e),
        })),
    }
}

// ---------- 画像アップロード（クリップボード貼り付け） ----------

#[query_params(error = bad_request)]
struct UploadQuery {
    /// 貼り付け先ノートのディレクトリ（vault 相対。ルートは空文字）
    dir: String,
    ext: String,
}

#[derive(Serialize)]
struct UploadResp {
    ok: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// ノートに挿入する相対パス（例: attachments/paste-123.png）
    insert: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
}

const MAX_UPLOAD_BYTES: usize = 20 * 1024 * 1024;

#[route(POST "/api/upload")]
async fn upload(cx: &Cx, body: Bytes) -> Result<Json<UploadResp>> {
    let q = query_params::<UploadQuery>(cx)?;
    let ext = q.ext.to_lowercase();
    let fail = |msg: &str| {
        Ok(Json(UploadResp {
            ok: false,
            insert: None,
            error: Some(msg.to_string()),
        }))
    };
    if !matches!(ext.as_str(), "png" | "jpg" | "jpeg" | "gif" | "webp") {
        return fail("対応していない画像形式です");
    }
    if body.len() > MAX_UPLOAD_BYTES {
        return fail("画像が大きすぎます (20MB まで)");
    }
    let epoch_ms = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0);
    let insert = format!("attachments/paste-{epoch_ms}.{ext}");
    let rel = if q.dir.is_empty() {
        insert.clone()
    } else {
        format!("{}/{}", q.dir, insert)
    };
    let v = vault::instance();
    let Some(abs) = v.resolve(&rel) else {
        return fail("不正な保存先です");
    };
    if let Some(parent) = abs.parent() {
        if std::fs::create_dir_all(parent).is_err() {
            return fail("ディレクトリを作成できませんでした");
        }
    }
    if std::fs::write(&abs, &body).is_err() {
        return fail("書き込みに失敗しました");
    }
    index::mark_dirty();
    Ok(Json(UploadResp {
        ok: true,
        insert: Some(insert),
        error: None,
    }))
}

// ---------- ノート操作（リネーム/移動・削除・ピン留め） ----------

#[derive(Deserialize)]
struct RenameReq {
    from: String,
    to: String,
}

#[derive(Serialize)]
struct OpResp {
    ok: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    to: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
}

fn op_fail(msg: String) -> Result<Json<OpResp>> {
    Ok(Json(OpResp {
        ok: false,
        to: None,
        error: Some(msg),
    }))
}

fn op_ok(to: Option<String>) -> Result<Json<OpResp>> {
    Ok(Json(OpResp {
        ok: true,
        to,
        error: None,
    }))
}

/// リネーム兼移動。wikilink の書き換えまでは行わない（参照元は backlinks で追える）。
#[route(POST "/api/rename")]
async fn rename(Json(req): Json<RenameReq>) -> Result<Json<OpResp>> {
    let v = vault::instance();
    let mut to = req.to.trim().trim_matches('/').to_string();
    if to.is_empty() {
        return op_fail("変更先を入力してください".to_string());
    }
    if !is_md(&to) {
        to.push_str(".md");
    }
    let Some(from_abs) = v.resolve_note(&req.from) else {
        return op_fail(format!("不正なパスです: {}", req.from));
    };
    if !from_abs.is_file() {
        return op_fail("元のファイルが見つかりません".to_string());
    }
    let Some(to_abs) = v.resolve_note(&to) else {
        return op_fail(format!("不正な変更先です: {to}"));
    };
    if to_abs.exists() {
        return op_fail(format!("変更先が既に存在します: {to}"));
    }
    if let Some(parent) = to_abs.parent() {
        if std::fs::create_dir_all(parent).is_err() {
            return op_fail("ディレクトリを作成できませんでした".to_string());
        }
    }
    if let Err(e) = std::fs::rename(&from_abs, &to_abs) {
        return op_fail(e.to_string());
    }
    // ピン留めの追従
    let mut pins = config::pins();
    if pins.iter().any(|p| p == &req.from) {
        for p in pins.iter_mut() {
            if p == &req.from {
                *p = to.clone();
            }
        }
        let _ = config::save_pins(&pins);
    }
    index::mark_dirty();
    op_ok(Some(to))
}

#[derive(Deserialize)]
struct DeleteReq {
    path: String,
}

/// 削除（完全削除ではなく <memo-data>/.trash/ への退避）。
#[route(POST "/api/delete")]
async fn delete(Json(req): Json<DeleteReq>) -> Result<Json<OpResp>> {
    let v = vault::instance();
    let Some(from_abs) = v.resolve_note(&req.path) else {
        return op_fail(format!("不正なパスです: {}", req.path));
    };
    if !from_abs.is_file() {
        return op_fail("ファイルが見つかりません".to_string());
    }
    let epoch_ms = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0);
    let name = req.path.rsplit('/').next().unwrap_or("note.md");
    let trash_rel = format!("{}/.trash/{epoch_ms}-{name}", config::memo_data());
    let Some(trash_abs) = v.resolve(&trash_rel) else {
        return op_fail("退避先を解決できませんでした".to_string());
    };
    if let Some(parent) = trash_abs.parent() {
        if std::fs::create_dir_all(parent).is_err() {
            return op_fail("退避先を作成できませんでした".to_string());
        }
    }
    if let Err(e) = std::fs::rename(&from_abs, &trash_abs) {
        return op_fail(e.to_string());
    }
    let mut pins = config::pins();
    if pins.iter().any(|p| p == &req.path) {
        pins.retain(|p| p != &req.path);
        let _ = config::save_pins(&pins);
    }
    index::mark_dirty();
    op_ok(Some(trash_rel))
}

#[derive(Deserialize)]
struct PinReq {
    path: String,
    pinned: bool,
}

#[route(POST "/api/pin")]
async fn pin(Json(req): Json<PinReq>) -> Result<Json<OpResp>> {
    let mut pins = config::pins();
    if req.pinned {
        if !pins.iter().any(|p| p == &req.path) {
            pins.push(req.path.clone());
        }
    } else {
        pins.retain(|p| p != &req.path);
    }
    if let Err(e) = config::save_pins(&pins) {
        return op_fail(e);
    }
    op_ok(None)
}

// ---------- ツリー表示フォルダの管理 ----------

#[derive(Deserialize)]
struct RootsReq {
    add: Option<String>,
    remove: Option<String>,
}

#[derive(Serialize)]
struct RootsResp {
    ok: bool,
    roots: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
}

#[route(POST "/api/roots")]
async fn roots(Json(req): Json<RootsReq>) -> Result<Json<RootsResp>> {
    let v = vault::instance();
    let mut roots = config::tree_roots();
    if let Some(add) = req.add {
        let p = add.trim().trim_matches('/').to_string();
        if p == config::memo_data() {
            // memo-data は常時固定表示なので追加不要
            return Ok(Json(RootsResp {
                ok: true,
                roots,
                error: None,
            }));
        }
        let valid = p == "." || v.resolve(&p).map(|a| a.is_dir()).unwrap_or(false);
        if p.is_empty() || !valid {
            return Ok(Json(RootsResp {
                ok: false,
                roots,
                error: Some(format!("ディレクトリが見つかりません: {add}")),
            }));
        }
        if !roots.contains(&p) {
            roots.push(p);
        }
    }
    if let Some(rm) = req.remove {
        roots.retain(|r| r != &rm);
    }
    match config::save_tree_roots(&roots) {
        Ok(()) => {
            index::mark_dirty();
            Ok(Json(RootsResp {
                ok: true,
                roots,
                error: None,
            }))
        }
        Err(e) => Ok(Json(RootsResp {
            ok: false,
            roots,
            error: Some(e),
        })),
    }
}

// ---------- ノート一覧（クイックスイッチャー用） / 更新時刻 ----------

#[route(GET "/api/notes")]
async fn notes() -> Result<Json<Vec<String>>> {
    Ok(Json(index::snapshot().note_paths()))
}

#[query_params(error = bad_request)]
struct MtimeQuery {
    path: String,
}

#[derive(Serialize)]
struct MtimeResp {
    mtime: Option<u64>,
}

#[route(GET "/api/mtime")]
async fn note_mtime(cx: &Cx) -> Result<Json<MtimeResp>> {
    let q = query_params::<MtimeQuery>(cx)?;
    let mtime = vault::instance()
        .resolve_note(&q.path)
        .and_then(|p| mtime_ms(&p));
    Ok(Json(MtimeResp { mtime }))
}

// ---------- テンプレート ----------

const BUILTIN_TEMPLATES: [(&str, &str); 2] = [
    (
        "daily",
        "# {{date}}\n\n## メモ\n\n- {{time}} \n",
    ),
    (
        "meeting",
        "## MTG:  ({{date}} {{time}})\n\n**参加者**: \n\n### アジェンダ\n\n\n### メモ\n\n- {{time}} \n\n### 決定事項\n\n- \n\n### TODO\n\n- [ ] \n",
    ),
];

/// 組み込みテンプレートの生テキスト（プレースホルダ未展開）。
pub fn builtin_template(name: &str) -> Option<&'static str> {
    BUILTIN_TEMPLATES
        .iter()
        .find(|(n, _)| *n == name)
        .map(|(_, c)| *c)
}

/// 利用可能なテンプレート名の一覧（組み込み + テンプレートディレクトリの md）。
pub fn template_names() -> Vec<String> {
    let mut names: Vec<String> = BUILTIN_TEMPLATES
        .iter()
        .map(|(n, _)| n.to_string())
        .collect();
    let v = vault::instance();
    if let Some(dir) = v.resolve(&config::templates_dir()) {
        if let Ok(entries) = std::fs::read_dir(dir) {
            for entry in entries.flatten() {
                let name = entry.file_name().to_string_lossy().to_string();
                if let Some(stem) = name.strip_suffix(".md") {
                    if !names.iter().any(|n| n == stem) {
                        names.push(stem.to_string());
                    }
                }
            }
        }
    }
    names
}

pub fn template_content(name: &str) -> Option<String> {
    if name.contains('/') || name.contains("..") {
        return None;
    }
    let v = vault::instance();
    let custom = format!("{}/{name}.md", config::templates_dir());
    if let Some(content) = v.read_note(&custom) {
        return Some(content);
    }
    BUILTIN_TEMPLATES
        .iter()
        .find(|(n, _)| *n == name)
        .map(|(_, c)| c.to_string())
}

#[query_params(error = bad_request)]
struct TemplateQuery {
    name: String,
}

#[derive(Serialize)]
struct TemplateResp {
    content: String,
}

#[route(GET "/api/template")]
async fn template(cx: &Cx) -> Result<Json<TemplateResp>> {
    let q = query_params::<TemplateQuery>(cx)?;
    let content = template_content(&q.name).ok_or_not_found()?;
    Ok(Json(TemplateResp { content }))
}

// ---------- vault 内ファイルの raw 配信 ----------

#[query_params(error = bad_request)]
struct RawQuery {
    path: String,
}

/// vault 内のファイル（画像など）をそのまま返す。ノート内の相対参照から使う。
#[route(GET "/raw")]
async fn raw(cx: &Cx) -> Result<([(&'static str, String); 1], Vec<u8>)> {
    let q = query_params::<RawQuery>(cx)?;
    let path = vault::instance()
        .resolve(&q.path)
        .ok_or_bad_request("invalid path")?;
    let bytes = std::fs::read(&path).ok().ok_or_not_found()?;
    Ok(([("content-type", mime_for(&q.path).to_string())], bytes))
}

fn mime_for(path: &str) -> &'static str {
    let ext = path.rsplit('.').next().unwrap_or("").to_lowercase();
    match ext.as_str() {
        "png" => "image/png",
        "jpg" | "jpeg" => "image/jpeg",
        "gif" => "image/gif",
        "svg" => "image/svg+xml",
        "webp" => "image/webp",
        "pdf" => "application/pdf",
        "md" | "txt" => "text/plain; charset=utf-8",
        "html" => "text/html; charset=utf-8",
        "json" => "application/json",
        _ => "application/octet-stream",
    }
}

// ---------- vendored ライブラリ配信（assets/vendor/VENDOR.md 参照） ----------

type VendorResp = ([(&'static str, &'static str); 2], &'static [u8]);

fn vendor(content_type: &'static str, bytes: &'static [u8]) -> Result<VendorResp> {
    Ok((
        [
            ("content-type", content_type),
            ("cache-control", "public, max-age=86400"),
        ],
        bytes,
    ))
}

#[route(GET "/vendor/mermaid.js")]
async fn vendor_mermaid() -> Result<VendorResp> {
    vendor(
        "application/javascript; charset=utf-8",
        include_bytes!("../assets/vendor/mermaid.min.js"),
    )
}

#[route(GET "/vendor/highlight.js")]
async fn vendor_highlight() -> Result<VendorResp> {
    vendor(
        "application/javascript; charset=utf-8",
        include_bytes!("../assets/vendor/highlight.min.js"),
    )
}

#[route(GET "/vendor/hljs-github.css")]
async fn vendor_hljs_css() -> Result<VendorResp> {
    vendor(
        "text/css; charset=utf-8",
        include_bytes!("../assets/vendor/hljs-github.min.css"),
    )
}

#[route(GET "/vendor/hljs-github-dark.css")]
async fn vendor_hljs_dark_css() -> Result<VendorResp> {
    vendor(
        "text/css; charset=utf-8",
        include_bytes!("../assets/vendor/hljs-github-dark.min.css"),
    )
}
