//! vault のインメモリインデックス。常駐前提のため負荷を最小にする設計:
//!
//! - バックグラウンドの監視スレッドは持たない（アイドル時の消費ゼロ）。
//! - アクセス時に TTL（2 秒）を過ぎていた場合だけ再構築する遅延方式。
//! - 再構築でもファイル内容の再読み込みは mtime が変わったものだけ
//!   （wikilink グラフの差分更新）。ディレクトリ走査自体は数 ms で済む。
//! - 自プロセスの書き込み（保存・アップロード）は dirty フラグで即時反映。

use std::collections::{BTreeMap, HashMap, HashSet};
use std::sync::{Arc, OnceLock, RwLock};
use std::time::{Duration, Instant};

use crate::config;
use crate::vault::{self, extract_wikilink_targets, is_md, mtime_ms, DirNode};

const TTL: Duration = Duration::from_secs(2);

pub struct NoteMeta {
    pub rel: String,
    pub mtime: u64,
}

pub struct SearchHit {
    pub rel: String,
    pub name_matched: bool,
    /// (行番号, 行テキスト)
    pub lines: Vec<(usize, String)>,
}

pub struct Snapshot {
    /// サイドバーに表示するフォレスト（設定 tree_roots の順）
    pub forest: Vec<DirNode>,
    pub notes: Vec<NoteMeta>,
    note_set: HashSet<String>,
    /// 小文字化した stem → 相対パス一覧
    stems: BTreeMap<String, Vec<String>>,
    /// 相対パス → そのノートが張っている wikilink のターゲット（小文字・生文字列）
    links: HashMap<String, Vec<String>>,
}

impl Snapshot {
    /// wikilink のターゲット（アンカー除去済み）を vault 相対パスに解決する。
    /// 戻り値は (相対パス, 実在するか)。
    pub fn resolve_wikilink(&self, target: &str) -> (String, bool) {
        let target = target.trim();
        let with_md = |s: &str| {
            if is_md(s) {
                s.to_string()
            } else {
                format!("{s}.md")
            }
        };
        if target.contains('/') {
            let rel = with_md(target);
            let exists = self.note_set.contains(&rel);
            return (rel, exists);
        }
        // ファイル名（stem）でインデックスを引く。Obsidian 同様、パス最短のものを優先。
        if let Some(cands) = self.stems.get(&target.to_lowercase()) {
            if let Some(best) = cands
                .iter()
                .min_by_key(|p| (p.matches('/').count(), p.len(), (*p).clone()))
            {
                return (best.clone(), true);
            }
        }
        (with_md(target), false)
    }

    /// target_rel を wikilink で参照しているノートの相対パス一覧。
    pub fn backlinks(&self, target_rel: &str) -> Vec<String> {
        let target_stem = std::path::Path::new(target_rel)
            .file_stem()
            .map(|s| s.to_string_lossy().to_lowercase())
            .unwrap_or_default();
        let target_lower = target_rel.to_lowercase();
        let mut out = Vec::new();
        for (rel, bases) in &self.links {
            if rel == target_rel {
                continue;
            }
            let hit = bases.iter().any(|base| {
                if base.contains('/') {
                    let rel_target = if is_md(base) {
                        base.clone()
                    } else {
                        format!("{base}.md")
                    };
                    rel_target == target_lower
                } else {
                    *base == target_stem
                }
            });
            if hit {
                out.push(rel.clone());
            }
        }
        out.sort();
        out
    }

    /// 更新日時の新しい順に最大 limit 件。
    pub fn recent(&self, limit: usize) -> Vec<(String, u64)> {
        let mut all: Vec<(String, u64)> = self
            .notes
            .iter()
            .map(|n| (n.rel.clone(), n.mtime))
            .collect();
        all.sort_by_key(|(_, mtime)| std::cmp::Reverse(*mtime));
        all.truncate(limit);
        all
    }

    pub fn note_paths(&self) -> Vec<String> {
        self.notes.iter().map(|n| n.rel.clone()).collect()
    }

    /// 大文字小文字を無視した全文検索。ファイル名一致 or 本文一致。
    /// 対象はインデックス済みの全ノート（既定走査 + ツリーに追加した除外配下）。
    pub fn search(&self, query: &str) -> Vec<SearchHit> {
        let q = query.to_lowercase();
        if q.is_empty() {
            return Vec::new();
        }
        let v = vault::instance();
        let mut hits = Vec::new();
        for note in &self.notes {
            if hits.len() >= 100 {
                break;
            }
            let name_matched = note.rel.to_lowercase().contains(&q);
            let mut lines = Vec::new();
            if let Some(abs) = v.resolve(&note.rel) {
                if let Ok(content) = std::fs::read_to_string(abs) {
                    for (i, line) in content.lines().enumerate() {
                        if line.to_lowercase().contains(&q) {
                            lines.push((i + 1, line.trim().to_string()));
                            if lines.len() >= 3 {
                                break;
                            }
                        }
                    }
                }
            }
            if name_matched || !lines.is_empty() {
                hits.push(SearchHit {
                    rel: note.rel.clone(),
                    name_matched,
                    lines,
                });
            }
        }
        // ファイル名一致を先頭に
        hits.sort_by(|a, b| b.name_matched.cmp(&a.name_matched).then(a.rel.cmp(&b.rel)));
        hits
    }
}

struct State {
    snap: Arc<Snapshot>,
    built: Instant,
    dirty: bool,
    /// 前回 wikilink を解析した時点の mtime（差分更新用）
    link_mtimes: HashMap<String, u64>,
}

fn state() -> &'static RwLock<Option<State>> {
    static STATE: OnceLock<RwLock<Option<State>>> = OnceLock::new();
    STATE.get_or_init(|| RwLock::new(None))
}

/// 現在のスナップショットを返す（必要なときだけ再構築）。
pub fn snapshot() -> Arc<Snapshot> {
    {
        let guard = state().read().unwrap();
        if let Some(st) = guard.as_ref() {
            if !st.dirty && st.built.elapsed() < TTL {
                return st.snap.clone();
            }
        }
    }
    let mut guard = state().write().unwrap();
    // write ロック待ちの間に他スレッドが再構築していたら使う
    if let Some(st) = guard.as_ref() {
        if !st.dirty && st.built.elapsed() < TTL {
            return st.snap.clone();
        }
    }
    let (prev_links, prev_mtimes) = match guard.take() {
        Some(st) => {
            let snap = Arc::try_unwrap(st.snap);
            match snap {
                Ok(s) => (s.links, st.link_mtimes),
                Err(arc) => (arc.links.clone(), st.link_mtimes),
            }
        }
        None => (HashMap::new(), HashMap::new()),
    };
    let st = rebuild(prev_links, prev_mtimes);
    let snap = st.snap.clone();
    *guard = Some(st);
    snap
}

/// 自プロセスがファイルを書き換えたとき呼ぶ（次のアクセスで確実に再構築させる）。
pub fn mark_dirty() {
    if let Some(st) = state().write().unwrap().as_mut() {
        st.dirty = true;
    }
}

fn rebuild(prev_links: HashMap<String, Vec<String>>, prev_mtimes: HashMap<String, u64>) -> State {
    let v = vault::instance();
    let roots = config::tree_roots();

    // 表示フォレスト: 存在しない・ディレクトリでないパスも空ノードとして残す
    // （消えたことに気づけるように & 削除ボタンで外せるように）
    let forest = roots
        .iter()
        .map(|r| {
            v.tree_at(r).unwrap_or_else(|| DirNode {
                name: r.clone(),
                dirs: Vec::new(),
                notes: Vec::new(),
            })
        })
        .collect();

    let mut notes = Vec::new();
    let mut links = HashMap::new();
    let mut link_mtimes = HashMap::new();
    let mut stems: BTreeMap<String, Vec<String>> = BTreeMap::new();
    let mut note_set = HashSet::new();

    let mut add_note = |rel: &str, abs: &std::path::Path| {
        if note_set.contains(rel) {
            return;
        }
        let mtime = mtime_ms(abs).unwrap_or(0);
        // wikilink グラフ: mtime が変わっていなければ前回の解析結果を使い回す
        let bases = if prev_mtimes.get(rel) == Some(&mtime) {
            prev_links.get(rel).cloned().unwrap_or_default()
        } else {
            std::fs::read_to_string(abs)
                .map(|content| {
                    extract_wikilink_targets(&content)
                        .iter()
                        .filter_map(|l| {
                            let base = l.split(['|', '#']).next().unwrap_or("").trim();
                            if base.is_empty() {
                                None
                            } else {
                                Some(base.to_lowercase())
                            }
                        })
                        .collect()
                })
                .unwrap_or_default()
        };
        let stem = std::path::Path::new(rel)
            .file_stem()
            .map(|s| s.to_string_lossy().to_lowercase())
            .unwrap_or_default();
        stems.entry(stem).or_default().push(rel.to_string());
        note_set.insert(rel.to_string());
        links.insert(rel.to_string(), bases);
        link_mtimes.insert(rel.to_string(), mtime);
        notes.push(NoteMeta {
            rel: rel.to_string(),
            mtime,
        });
    };

    v.walk_notes(&mut add_note);
    // 除外ディレクトリ（projects/ 等）配下をツリーに追加している場合は
    // その分もインデックスに含める（パレット・wikilink・検索と表示を一致させる）
    for root in &roots {
        if root != "." && v.is_rel_excluded(root) {
            v.walk_notes_at(root, &mut add_note);
        }
    }

    notes.sort_by(|a, b| a.rel.cmp(&b.rel));
    State {
        snap: Arc::new(Snapshot {
            forest,
            notes,
            note_set,
            stems,
            links,
        }),
        built: Instant::now(),
        dirty: false,
        link_mtimes,
    }
}
