//! Markdown → HTML 変換。wikilink（[[...]]）と相対リンクを
//! アプリ内 URL（/note?path=... / /raw?path=...）に書き換える。

use pulldown_cmark::{
    html, CodeBlockKind, CowStr, Event, HeadingLevel, LinkType, Options, Parser, Tag, TagEnd,
};
use std::collections::HashMap;
use std::path::Path;

use crate::vault::{extract_tags_in_text, is_md, is_tag_char};

/// 目次の 1 エントリ。
pub struct TocEntry {
    pub level: u8,
    pub id: String,
    pub text: String,
}

pub struct Rendered {
    pub html: String,
    pub toc: Vec<TocEntry>,
}

pub fn render(current_rel: &str, src: &str) -> String {
    render_full(current_rel, src).html
}

pub fn render_full(current_rel: &str, src: &str) -> Rendered {
    let snap = crate::index::snapshot();
    let mut options = Options::empty();
    options.insert(Options::ENABLE_TABLES);
    options.insert(Options::ENABLE_FOOTNOTES);
    options.insert(Options::ENABLE_STRIKETHROUGH);
    options.insert(Options::ENABLE_TASKLISTS);
    options.insert(Options::ENABLE_WIKILINKS);

    let current_dir = Path::new(current_rel)
        .parent()
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_default();

    let mut in_wikilink = false;
    let events = Parser::new_ext(src, options).map(|event| match event {
        Event::Start(Tag::Link {
            link_type: LinkType::WikiLink { .. },
            dest_url,
            ..
        }) => {
            let (base, frag) = split_fragment(&dest_url);
            let (rel, exists) = snap.resolve_wikilink(base);
            let class = if exists {
                "wikilink"
            } else {
                "wikilink missing"
            };
            let href = format!("/note?path={}{}", url_encode(&rel), frag);
            in_wikilink = true;
            Event::Html(CowStr::from(format!(
                "<a href=\"{}\" class=\"{}\">",
                escape_attr(&href),
                class
            )))
        }
        Event::End(TagEnd::Link) if in_wikilink => {
            in_wikilink = false;
            Event::Html(CowStr::from("</a>"))
        }
        Event::Start(Tag::Link {
            link_type,
            dest_url,
            title,
            id,
        }) => {
            let dest_url = rewrite_relative(&current_dir, &dest_url, LinkKind::Note);
            Event::Start(Tag::Link {
                link_type,
                dest_url,
                title,
                id,
            })
        }
        Event::Start(Tag::Image {
            link_type,
            dest_url,
            title,
            id,
        }) => {
            let dest_url = rewrite_relative(&current_dir, &dest_url, LinkKind::Raw);
            Event::Start(Tag::Image {
                link_type,
                dest_url,
                title,
                id,
            })
        }
        other => other,
    });
    let events: Vec<Event> = events.collect();

    // 第 2 パス: 見出しに id を振って目次を集め、mermaid コードブロックを図用の要素に変換する。
    let mut out_events: Vec<Event> = Vec::with_capacity(events.len());
    let mut toc: Vec<TocEntry> = Vec::new();
    let mut used_slugs: HashMap<String, usize> = HashMap::new();
    let mut in_code = false;
    let mut in_link = 0i32;
    let mut i = 0;
    while i < events.len() {
        match &events[i] {
            ev @ Event::Start(Tag::Link { .. }) => {
                in_link += 1;
                out_events.push(ev.clone());
                i += 1;
            }
            ev @ Event::End(TagEnd::Link) => {
                in_link -= 1;
                out_events.push(ev.clone());
                i += 1;
            }
            Event::Html(h) if h.starts_with("<a ") => {
                in_link += 1;
                out_events.push(events[i].clone());
                i += 1;
            }
            Event::Html(h) if h.as_ref() == "</a>" => {
                in_link -= 1;
                out_events.push(events[i].clone());
                i += 1;
            }
            // 本文テキスト中の #tag をクリック可能に
            Event::Text(t) if !in_code && in_link == 0 && t.contains('#') => {
                match linkify_tags(t) {
                    Some(html) => out_events.push(Event::Html(CowStr::from(html))),
                    None => out_events.push(events[i].clone()),
                }
                i += 1;
            }
            Event::Start(Tag::Heading { level, .. }) => {
                let lvl = heading_level(*level);
                let mut j = i + 1;
                let mut text = String::new();
                while j < events.len() {
                    match &events[j] {
                        Event::End(TagEnd::Heading(_)) => break,
                        Event::Text(t) | Event::Code(t) => text.push_str(t),
                        _ => {}
                    }
                    j += 1;
                }
                let id = unique_slug(&text, &mut used_slugs);
                out_events.push(Event::Html(CowStr::from(format!(
                    "<h{lvl} id=\"{}\">",
                    escape_attr(&id)
                ))));
                for ev in &events[i + 1..j] {
                    out_events.push(ev.clone());
                }
                out_events.push(Event::Html(CowStr::from(format!("</h{lvl}>"))));
                toc.push(TocEntry {
                    level: lvl,
                    id,
                    text,
                });
                i = j + 1;
            }
            Event::Start(Tag::CodeBlock(CodeBlockKind::Fenced(lang)))
                if lang.as_ref() == "mermaid" =>
            {
                let mut j = i + 1;
                let mut code = String::new();
                while j < events.len() {
                    match &events[j] {
                        Event::End(TagEnd::CodeBlock) => break,
                        Event::Text(t) => code.push_str(t),
                        _ => {}
                    }
                    j += 1;
                }
                out_events.push(Event::Html(CowStr::from(format!(
                    "<pre class=\"mermaid\">{}</pre>",
                    escape_html(&code)
                ))));
                i = j + 1;
            }
            // タグリンク化の抑制範囲（コードブロック・リンク内）を追跡
            ev @ Event::Start(Tag::CodeBlock(_)) => {
                in_code = true;
                out_events.push(ev.clone());
                i += 1;
            }
            ev @ Event::End(TagEnd::CodeBlock) => {
                in_code = false;
                out_events.push(ev.clone());
                i += 1;
            }
            ev => {
                out_events.push(ev.clone());
                i += 1;
            }
        }
    }

    let mut out = String::new();
    html::push_html(&mut out, out_events.into_iter());
    Rendered { html: out, toc }
}

/// テキスト断片中の `#tag` を <a class="tag"> に変換した HTML を返す。タグが無ければ None。
fn linkify_tags(text: &str) -> Option<String> {
    if extract_tags_in_text(text).is_empty() {
        return None;
    }
    let chars: Vec<char> = text.chars().collect();
    let mut out = String::new();
    let mut plain = String::new();
    let mut i = 0;
    while i < chars.len() {
        let c = chars[i];
        if c == '#' {
            let prev_ok = i == 0 || chars[i - 1].is_whitespace();
            let next_ok = chars.get(i + 1).map(|n| is_tag_char(*n)).unwrap_or(false);
            if prev_ok && next_ok {
                let mut j = i + 1;
                let mut tag = String::new();
                while j < chars.len() && is_tag_char(chars[j]) {
                    tag.push(chars[j]);
                    j += 1;
                }
                if !tag.chars().all(|ch| ch.is_ascii_digit()) {
                    out.push_str(&escape_html(&plain));
                    plain.clear();
                    out.push_str(&format!(
                        "<a href=\"/tag?name={}\" class=\"tag\">#{}</a>",
                        url_encode(&tag),
                        escape_html(&tag)
                    ));
                    i = j;
                    continue;
                }
            }
        }
        plain.push(c);
        i += 1;
    }
    out.push_str(&escape_html(&plain));
    Some(out)
}

fn heading_level(level: HeadingLevel) -> u8 {
    match level {
        HeadingLevel::H1 => 1,
        HeadingLevel::H2 => 2,
        HeadingLevel::H3 => 3,
        HeadingLevel::H4 => 4,
        HeadingLevel::H5 => 5,
        HeadingLevel::H6 => 6,
    }
}

/// 見出しテキストからアンカー id を作る（日本語はそのまま残す）。重複には連番を付ける。
fn unique_slug(text: &str, used: &mut HashMap<String, usize>) -> String {
    let mut slug = String::new();
    let mut prev_dash = true;
    for c in text.trim().to_lowercase().chars() {
        if c.is_alphanumeric() {
            slug.push(c);
            prev_dash = false;
        } else if !prev_dash {
            slug.push('-');
            prev_dash = true;
        }
    }
    let slug = slug.trim_end_matches('-').to_string();
    let base = if slug.is_empty() {
        "section".to_string()
    } else {
        slug
    };
    let count = used.entry(base.clone()).or_insert(0);
    *count += 1;
    if *count == 1 {
        base
    } else {
        format!("{base}-{count}")
    }
}

enum LinkKind {
    Note,
    Raw,
}

/// vault 内相対リンクをアプリ内 URL に書き換える。外部 URL・絶対パスはそのまま。
fn rewrite_relative(current_dir: &str, dest: &str, kind: LinkKind) -> CowStr<'static> {
    let is_external = dest.contains("://") || dest.starts_with("mailto:");
    if is_external || dest.starts_with('/') || dest.starts_with('#') || dest.is_empty() {
        return CowStr::from(dest.to_string());
    }
    let (base, frag) = split_fragment(dest);
    let decoded = url_decode(base);
    let Some(joined) = normalize_join(current_dir, &decoded) else {
        return CowStr::from(dest.to_string());
    };
    let rewritten = match kind {
        LinkKind::Note if is_md(&joined) => {
            format!("/note?path={}{}", url_encode(&joined), frag)
        }
        LinkKind::Note => return CowStr::from(dest.to_string()),
        LinkKind::Raw => format!("/raw?path={}{}", url_encode(&joined), frag),
    };
    CowStr::from(rewritten)
}

fn split_fragment(s: &str) -> (&str, &str) {
    match s.find('#') {
        Some(i) => (&s[..i], &s[i..]),
        None => (s, ""),
    }
}

/// current_dir 基準で相対パスを結合し `..` を解決する。ルート外に出たら None。
fn normalize_join(current_dir: &str, rel: &str) -> Option<String> {
    let mut parts: Vec<&str> = current_dir.split('/').filter(|s| !s.is_empty()).collect();
    for seg in rel.split('/') {
        match seg {
            "" | "." => {}
            ".." => {
                parts.pop()?;
            }
            other => parts.push(other),
        }
    }
    if parts.is_empty() {
        return None;
    }
    Some(parts.join("/"))
}

pub fn url_encode(s: &str) -> String {
    let mut out = String::with_capacity(s.len() * 3);
    for b in s.bytes() {
        match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                out.push(b as char)
            }
            _ => out.push_str(&format!("%{b:02X}")),
        }
    }
    out
}

fn url_decode(s: &str) -> String {
    let bytes = s.as_bytes();
    let mut out = Vec::with_capacity(bytes.len());
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b'%'
            && i + 2 < bytes.len()
            && bytes[i + 1].is_ascii_hexdigit()
            && bytes[i + 2].is_ascii_hexdigit()
        {
            if let Ok(v) = u8::from_str_radix(&s[i + 1..i + 3], 16) {
                out.push(v);
                i += 3;
                continue;
            }
        }
        out.push(bytes[i]);
        i += 1;
    }
    String::from_utf8_lossy(&out).into_owned()
}

pub fn escape_html(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for c in s.chars() {
        match c {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '"' => out.push_str("&quot;"),
            '\'' => out.push_str("&#39;"),
            _ => out.push(c),
        }
    }
    out
}

pub fn escape_attr(s: &str) -> String {
    escape_html(s)
}
