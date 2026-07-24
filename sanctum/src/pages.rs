//! ページ定義: レイアウト（サイドバー付き外枠）・ホーム・ノート閲覧・編集・検索・デイリーノート。

use std::time::{SystemTime, UNIX_EPOCH};

use topcoat::{
    context::Cx,
    router::{layout, page, query_params, Slot},
    view::{component, view, Unescaped},
    Result,
};

use crate::api::template_names;
use crate::index;
use crate::markdown::{escape_attr, escape_html, render_full, url_encode, TocEntry};
use crate::vault::{self, mtime_ms, DirNode};

const CSS: &str = include_str!("../assets/style.css");
const JS: &str = include_str!("../assets/app.js");

/// デイリーノートの置き場（vault 相対）。
pub fn daily_dir() -> String {
    std::env::var("SANCTUM_DAILY_DIR").unwrap_or_else(|_| "memo-data/daily".to_string())
}

#[layout("/")]
async fn chrome(slot: Slot<'_>) -> Result {
    let snap = index::snapshot();
    let tree_html: String = snap.forest.iter().map(tree_root_html).collect();
    view! {
        <!DOCTYPE html>
        <html lang="ja">
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <title>"Sanctum"</title>
                <style>(Unescaped::new_unchecked(CSS))</style>
            </head>
            <body>
                <aside class="sidebar">
                    <div class="brand"><a href="/">"🏛 Sanctum"</a></div>
                    <a class="btn today" href="/today">"📅 今日のメモ"</a>
                    <form class="search" action="/search" method="get">
                        <input type="search" name="q" placeholder="検索…">
                    </form>
                    <form class="newnote" id="newnote-form">
                        <input type="text" id="newnote-path"
                            placeholder="パスを開く・新規作成 (例: ideas/foo)">
                        <button type="submit">"→"</button>
                    </form>
                    <nav class="tree">(Unescaped::new_unchecked(tree_html))</nav>
                    <form class="addroot" id="addroot-form">
                        <input type="text" id="addroot-path"
                            placeholder="ツリーにフォルダ追加 (例: ideas)">
                        <button type="submit">"+"</button>
                    </form>
                    <div class="hint" id="root-msg"></div>
                    <div class="hint">"i 編集 ／ Esc 閲覧 ／ ⌘K 移動 ／ ⌘S 保存"</div>
                </aside>
                <main class="content">(slot.await?)</main>
                <div id="palette-overlay" hidden="hidden">
                    <div id="palette">
                        <input id="palette-input" type="text"
                            placeholder="ノート名で移動… (Enter: 開く ／ ⌘Enter: 編集)">
                        <div id="palette-list"></div>
                    </div>
                </div>
                <script>(Unescaped::new_unchecked(JS))</script>
            </body>
        </html>
    }
}

#[page("/")]
async fn home() -> Result {
    let v = vault::instance();
    let snap = index::snapshot();
    let recents = snap.recent(15);
    let total = snap.notes.len();
    view! {
        <div class="content-inner">
            <h1>"Sanctum"</h1>
            <p class="muted">(format!("vault: {} ／ ノート {} 件", v.root().display(), total))</p>
            <h2>"最近更新したノート"</h2>
            <ul class="note-list">
                for (rel, mtime) in recents {
                    <li>
                        <a href=(format!("/note?path={}", url_encode(&rel)))>(rel.clone())</a>
                        <span class="meta">(ago_ms(mtime))</span>
                    </li>
                }
            </ul>
        </div>
    }
}

/// ブラウザのローカル日付で今日のデイリーノートの編集画面へ飛ばす。
/// （サーバー側で日付を決めるとタイムゾーン依存になるためクライアントで解決する）
#[page("/today")]
async fn today() -> Result {
    let dir = daily_dir().replace(['\\', '\''], "");
    let script = format!(
        "(function(){{var d=new Date();function p(n){{return(n<10?'0':'')+n}}\
         var name=d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate());\
         location.replace('/edit?path='+encodeURIComponent('{dir}/'+name+'.md'));}})();"
    );
    view! {
        <div class="content-inner">
            <p class="muted">"今日のメモへ移動中…"</p>
            <script>(Unescaped::new_unchecked(script))</script>
        </div>
    }
}

#[query_params(error = bad_request)]
struct NoteQuery {
    path: String,
}

#[query_params(error = bad_request)]
struct SearchQuery {
    q: Option<String>,
}

#[page("/note")]
async fn note_page(cx: &Cx) -> Result {
    let q = query_params::<NoteQuery>(cx)?;
    let rel = q.path.clone();
    view! { note_shell(rel: rel, force_insert: false) }
}

#[page("/edit")]
async fn edit_page(cx: &Cx) -> Result {
    let q = query_params::<NoteQuery>(cx)?;
    let rel = q.path.clone();
    view! { note_shell(rel: rel, force_insert: true) }
}

/// 閲覧（NORMAL）と編集（INSERT）を 1 ページに統合したノート画面。
/// モード切り替えは vim 風キーバインド（i で編集、Esc で閲覧）。
#[component]
async fn note_shell(rel: String, force_insert: bool) -> Result {
    let v = vault::instance();
    let (content, is_new) = match v.read_note(&rel) {
        Some(c) => (c, false),
        None => (String::new(), true),
    };
    let start_insert = force_insert || is_new;
    let rendered = render_full(&rel, &content);
    let toc_html = toc_html(&rendered.toc);
    let backlinks = if is_new {
        Vec::new()
    } else {
        index::snapshot().backlinks(&rel)
    };
    let mtime = v
        .resolve_note(&rel)
        .and_then(|p| mtime_ms(&p))
        .unwrap_or(0)
        .to_string();
    let note_dir = std::path::Path::new(&rel)
        .parent()
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_default();
    let new_flag = if is_new { "1" } else { "0" };
    let start_mode = if start_insert { "insert" } else { "normal" };
    let tpl_names = template_names();
    view! {
        <div class="content-inner note-page" id="note-page">
            <link rel="stylesheet" href="/vendor/hljs-github.css" media="(prefers-color-scheme: light)">
            <link rel="stylesheet" href="/vendor/hljs-github-dark.css" media="(prefers-color-scheme: dark)">
            <script src="/vendor/highlight.js"></script>
            <script src="/vendor/mermaid.js"></script>
            <div class="note-head">
                <div class="note-path">
                    (rel.clone())
                    if is_new {
                        <span class="muted">" （未作成 — 保存時に作成されます）"</span>
                    }
                </div>
                <div class="note-actions">
                    <select id="tpl-select" title="テンプレート">
                        for name in tpl_names {
                            <option value=(name.clone())>(name.clone())</option>
                        }
                    </select>
                    <button class="btn" id="tpl-insert" type="button">"テンプレ挿入"</button>
                    <span class="status" id="save-status"></span>
                    <span class="mode-badge" id="mode-badge">"NORMAL"</span>
                </div>
            </div>
            <div class="banner" id="conflict-banner" hidden="hidden">
                <span id="conflict-msg">"ファイルが外部で変更されています。"</span>
                <button class="btn" id="btn-conflict-reload" type="button">"読み込み直す"</button>
                <button class="btn" id="btn-conflict-force" type="button">"自分の内容で上書き"</button>
            </div>
            if !toc_html.is_empty() {
                <aside class="toc">
                    <div class="toc-title">"目次"</div>
                    (Unescaped::new_unchecked(toc_html))
                </aside>
            }
            <article id="view" class="markdown-body">(Unescaped::new_unchecked(rendered.html))</article>
            <textarea id="editor" hidden="hidden"
                data-path=(rel.clone())
                data-dir=(note_dir)
                data-mtime=(mtime)
                data-new=(new_flag)
                data-daily-dir=(daily_dir())
                data-start-mode=(start_mode)
                spellcheck="false">(content)</textarea>
            if !backlinks.is_empty() {
                <section class="backlinks">
                    <h2>"このノートへのリンク"</h2>
                    <ul class="note-list">
                        for bl in backlinks {
                            <li><a href=(format!("/note?path={}", url_encode(&bl)))>(bl.clone())</a></li>
                        }
                    </ul>
                </section>
            }
        </div>
    }
}

#[page("/search")]
async fn search_page(cx: &Cx) -> Result {
    let q = query_params::<SearchQuery>(cx)?;
    let query = q.q.clone().unwrap_or_default();
    let hits = index::snapshot().search(&query);
    let count = hits.len();
    view! {
        <div class="content-inner">
            <h1>"検索"</h1>
            if query.is_empty() {
                <p class="muted">"サイドバーの検索ボックスからキーワードを入力してください。"</p>
            } else {
                <p class="muted">(format!("「{query}」 — {count} 件"))</p>
                for hit in hits {
                    <div class="search-hit">
                        <div class="hit-title">
                            <a href=(format!("/note?path={}", url_encode(&hit.rel)))>
                                (Unescaped::new_unchecked(highlight(&hit.rel, &query)))
                            </a>
                        </div>
                        for (lineno, line) in hit.lines {
                            <div class="hit-line">
                                <span class="lineno">(format!("{lineno}:"))</span>
                                (Unescaped::new_unchecked(highlight(&truncate_chars(&line, 200), &query)))
                            </div>
                        }
                    </div>
                }
            }
        </div>
    }
}

/// 表示フォルダ（設定した根）1 つ分のツリー HTML。削除ボタン付き。
fn tree_root_html(node: &DirNode) -> String {
    format!(
        "<details open class=\"tree-root\"><summary>{}\
         <span class=\"root-remove\" data-root=\"{}\" title=\"ツリーから外す\">×</span>\
         </summary>{}</details>",
        escape_html(&node.name),
        escape_attr(&node.name),
        tree_children_html(node, 1)
    )
}

/// ノード配下（子ディレクトリ + ノート）の HTML。
fn tree_children_html(node: &DirNode, depth: usize) -> String {
    let mut out = String::new();
    for dir in &node.dirs {
        let open = if depth < 2 { " open" } else { "" };
        out.push_str(&format!(
            "<details{open}><summary>{}</summary>{}</details>",
            escape_html(&dir.name),
            tree_children_html(dir, depth + 1)
        ));
    }
    for (name, rel) in &node.notes {
        let display = name
            .strip_suffix(".md")
            .or_else(|| name.strip_suffix(".MD"))
            .unwrap_or(name);
        out.push_str(&format!(
            "<a href=\"/note?path={}\" data-path=\"{}\">{}</a>",
            url_encode(rel),
            escape_attr(rel),
            escape_html(display)
        ));
    }
    out
}

/// 目次の HTML（見出しが 3 つ未満なら出さない）。
fn toc_html(toc: &[TocEntry]) -> String {
    if toc.len() < 3 {
        return String::new();
    }
    let mut out = String::from("<ul>");
    for entry in toc {
        if entry.level > 4 {
            continue;
        }
        out.push_str(&format!(
            "<li class=\"toc-l{}\"><a href=\"#{}\">{}</a></li>",
            entry.level,
            escape_attr(&entry.id),
            escape_html(&entry.text)
        ));
    }
    out.push_str("</ul>");
    out
}

/// クエリに一致した部分を <mark> で囲んだ HTML を返す（全体をエスケープ済み）。
fn highlight(text: &str, query: &str) -> String {
    if query.is_empty() {
        return escape_html(text);
    }
    let lower = text.to_lowercase();
    let query_lower = query.to_lowercase();
    // to_lowercase でバイト長が変わる文字が混ざる場合は装飾を諦めて全体を返す
    if lower.len() != text.len() {
        return escape_html(text);
    }
    let mut out = String::new();
    let mut pos = 0;
    while let Some(found) = lower[pos..].find(&query_lower) {
        let start = pos + found;
        let end = start + query_lower.len();
        if !text.is_char_boundary(start) || end > text.len() || !text.is_char_boundary(end) {
            return escape_html(text);
        }
        out.push_str(&escape_html(&text[pos..start]));
        out.push_str("<mark>");
        out.push_str(&escape_html(&text[start..end]));
        out.push_str("</mark>");
        pos = end;
    }
    out.push_str(&escape_html(&text[pos..]));
    out
}

fn truncate_chars(s: &str, max: usize) -> String {
    if s.chars().count() <= max {
        s.to_string()
    } else {
        let t: String = s.chars().take(max).collect();
        format!("{t}…")
    }
}

fn ago_ms(mtime_ms: u64) -> String {
    let now_ms = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0);
    let secs = now_ms.saturating_sub(mtime_ms) / 1000;
    match secs {
        0..=59 => "たった今".to_string(),
        60..=3599 => format!("{} 分前", secs / 60),
        3600..=86399 => format!("{} 時間前", secs / 3600),
        _ => format!("{} 日前", secs / 86400),
    }
}
