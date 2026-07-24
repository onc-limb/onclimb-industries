//! ページ定義: レイアウト（サイドバー付き外枠）・ホーム・ノート閲覧・編集・検索・デイリーノート。

use topcoat::{
    context::Cx,
    router::{layout, page, query_params, Slot},
    view::{component, view, Unescaped},
    Result,
};

use crate::api::{builtin_template, template_names};
use crate::markdown::{escape_attr, escape_html, render_full, url_encode, TocEntry};
use crate::vault::{self, mtime_ms, DirNode};
use crate::{config, index};

const CSS: &str = include_str!("../assets/style.css");
const JS: &str = include_str!("../assets/app.js");

#[layout("/")]
async fn chrome(slot: Slot<'_>) -> Result {
    let snap = index::snapshot();
    let tree_html: String = snap
        .forest
        .iter()
        .map(|node| tree_root_html(node, node.name != config::memo_data()))
        .collect();
    let pins = config::pins();
    let tags = snap.tag_counts();
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
                    <a class="btn today" href="/today">"今日のメモ"</a>
                    <form class="search" action="/search" method="get">
                        <input type="search" name="q" placeholder="検索…">
                    </form>
                    <form class="newnote" id="newnote-form">
                        <input type="text" id="newnote-path"
                            placeholder="パスを開く・新規作成 (例: ideas/foo)">
                        <button type="submit">"→"</button>
                    </form>
                    if !pins.is_empty() {
                        <div class="pins">
                            <div class="section-title">"ピン留め"</div>
                            for pin in pins {
                                <a href=(format!("/note?path={}", url_encode(&pin)))
                                    data-path=(pin.clone())
                                    title=(pin.clone())>(pin_display(&pin))</a>
                            }
                        </div>
                    }
                    <nav class="tree">(Unescaped::new_unchecked(tree_html))</nav>
                    if !tags.is_empty() {
                        <details class="tagbox">
                            <summary>"タグ"</summary>
                            <div class="tag-list">
                                for (tag, count) in tags.into_iter().take(30) {
                                    <a class="tag-item" href=(format!("/tag?name={}", url_encode(&tag)))>
                                        (format!("#{tag}"))
                                        <span class="meta">(format!("{count}"))</span>
                                    </a>
                                }
                            </div>
                        </details>
                    }
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
    // ファイルを選択していない状態では何も表示しない
    view! { <div class="content-inner"></div> }
}

/// ブラウザのローカル日付で今日のデイリーノートの編集画面へ飛ばす。
/// （サーバー側で日付を決めるとタイムゾーン依存になるためクライアントで解決する）
#[page("/today")]
async fn today() -> Result {
    let dir = config::daily_dir().replace(['\\', '\''], "");
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
struct TagQuery {
    name: String,
}

#[query_params(error = bad_request)]
struct SearchQuery {
    q: Option<String>,
}

#[page("/tag")]
async fn tag_page(cx: &Cx) -> Result {
    let q = query_params::<TagQuery>(cx)?;
    let tag = q.name.clone();
    let notes = index::snapshot().notes_with_tag(&tag);
    let count = notes.len();
    view! {
        <div class="content-inner">
            <h1>(format!("#{tag}"))</h1>
            <p class="muted">(format!("{count} 件"))</p>
            <ul class="note-list">
                for rel in notes {
                    <li><a href=(format!("/note?path={}", url_encode(&rel)))>(rel.clone())</a></li>
                }
            </ul>
        </div>
    }
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
    // 組み込みテンプレート（daily/meeting）の上書きファイルを新規で開いた場合は、
    // 組み込みの中身を展開した状態から編集を始める（保存するとカスタム版が優先される）。
    let content = if is_new {
        template_prefill(&rel).unwrap_or(content)
    } else {
        content
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
    let daily_nav = daily_nav(&rel);
    let pinned = config::pins().iter().any(|p| p == &rel);
    let pin_label = if pinned {
        "ピン留めを解除"
    } else {
        "ピン留め"
    };
    let pinned_flag = if pinned { "1" } else { "0" };
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
                    if let Some((prev_href, next_href)) = daily_nav {
                        <a class="btn" href=(prev_href)>"← 前日"</a>
                        <a class="btn" href=(next_href)>"翌日 →"</a>
                    }
                    <select id="tpl-select" title="テンプレート">
                        for name in tpl_names {
                            <option value=(name.clone())>(name.clone())</option>
                        }
                    </select>
                    <button class="btn" id="tpl-insert" type="button">"テンプレ挿入"</button>
                    <button class="btn" id="tpl-edit" type="button"
                        data-templates-dir=(config::templates_dir())
                        title="選択中のテンプレートを開いて編集">"テンプレ編集"</button>
                    <span class="status" id="save-status"></span>
                    <span class="mode-badge" id="mode-badge">"NORMAL"</span>
                    <details class="menu" id="note-menu">
                        <summary class="btn" title="ノート操作">"…"</summary>
                        <div class="menu-items">
                            <button type="button" id="btn-pin" data-pinned=(pinned_flag)>(pin_label)</button>
                            <button type="button" id="btn-rename">"名前を変更・移動"</button>
                            <button type="button" id="btn-delete" class="danger">"削除"</button>
                        </div>
                    </details>
                </div>
            </div>
            <div class="banner neutral" id="rename-banner" hidden="hidden">
                <span>"変更先パス:"</span>
                <input type="text" id="rename-input" value=(rel.clone())>
                <button class="btn" id="btn-rename-do" type="button">"変更"</button>
                <button class="btn" id="btn-rename-cancel" type="button">"キャンセル"</button>
            </div>
            <div class="banner" id="delete-banner" hidden="hidden">
                <span>(format!("「{rel}」を memo-data/.trash/ へ移動します。よろしいですか？"))</span>
                <button class="btn" id="btn-delete-do" type="button">"削除する"</button>
                <button class="btn" id="btn-delete-cancel" type="button">"キャンセル"</button>
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
                data-daily-dir=(config::daily_dir())
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

/// ピン留めのサイドバー表示名（ファイル名の stem）。
fn pin_display(rel: &str) -> String {
    std::path::Path::new(rel)
        .file_stem()
        .map(|s| s.to_string_lossy().to_string())
        .unwrap_or_else(|| rel.to_string())
}

/// rel がデイリーノート（<daily>/YYYY-MM-DD.md）なら前日・翌日ノートへの href を返す。
fn daily_nav(rel: &str) -> Option<(String, String)> {
    let dir = config::daily_dir();
    let stem = rel.strip_prefix(&format!("{dir}/"))?.strip_suffix(".md")?;
    let mut parts = stem.split('-');
    let y: i64 = parts.next()?.parse().ok()?;
    let m: i64 = parts.next()?.parse().ok()?;
    let d: i64 = parts.next()?.parse().ok()?;
    if parts.next().is_some() || !(1..=12).contains(&m) || !(1..=31).contains(&d) {
        return None;
    }
    let days = days_from_civil(y, m, d);
    let href = |z: i64| {
        let (yy, mm, dd) = civil_from_days(z);
        format!(
            "/note?path={}",
            url_encode(&format!("{dir}/{yy:04}-{mm:02}-{dd:02}.md"))
        )
    };
    Some((href(days - 1), href(days + 1)))
}

/// グレゴリオ暦 → 通算日数（Howard Hinnant の civil アルゴリズム）。
fn days_from_civil(y: i64, m: i64, d: i64) -> i64 {
    let y = if m <= 2 { y - 1 } else { y };
    let era = if y >= 0 { y } else { y - 399 } / 400;
    let yoe = y - era * 400;
    let mp = (m + 9) % 12;
    let doy = (153 * mp + 2) / 5 + d - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    era * 146097 + doe - 719468
}

/// 通算日数 → グレゴリオ暦。
fn civil_from_days(z: i64) -> (i64, i64, i64) {
    let z = z + 719468;
    let era = if z >= 0 { z } else { z - 146096 } / 146097;
    let doe = z - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    (if m <= 2 { y + 1 } else { y }, m, d)
}

/// rel が組み込みテンプレートの上書きパス（<templates>/<name>.md）なら
/// その組み込みの生テキストを返す。
fn template_prefill(rel: &str) -> Option<String> {
    let dir = config::templates_dir();
    let name = rel.strip_prefix(&format!("{dir}/"))?.strip_suffix(".md")?;
    builtin_template(name).map(|s| s.to_string())
}

/// 表示フォルダ（設定した根）1 つ分のツリー HTML。
/// memo-data（removable = false）には削除ボタンを付けない。
fn tree_root_html(node: &DirNode, removable: bool) -> String {
    let remove_btn = if removable {
        format!(
            "<span class=\"root-remove\" data-root=\"{}\" title=\"ツリーから外す\">×</span>",
            escape_attr(&node.name)
        )
    } else {
        String::new()
    };
    format!(
        "<details open class=\"tree-root\"><summary>{}{}</summary>{}</details>",
        escape_html(&node.name),
        remove_btn,
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
