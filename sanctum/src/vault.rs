//! Vault: メモ置き場（リポジトリルート配下の md ファイル群）へのアクセス層。
//! パス安全性の検証・ツリー構築・検索・wikilink 解決を担う。

use std::fs;
use std::path::{Component, Path, PathBuf};
use std::sync::OnceLock;

static VAULT: OnceLock<Vault> = OnceLock::new();

/// アプリ起動時に一度だけ呼ぶ。
pub fn init(vault: Vault) {
    let _ = VAULT.set(vault);
}

pub fn instance() -> &'static Vault {
    VAULT.get().expect("vault is not initialized")
}

/// シンボリックリンク循環対策の再帰深さ上限。
const MAX_DEPTH: usize = 12;

pub struct Vault {
    root: PathBuf,
    excludes: Vec<String>,
}

/// サイドバーに表示するディレクトリツリーのノード。
pub struct DirNode {
    pub name: String,
    pub dirs: Vec<DirNode>,
    /// (表示名, vault ルートからの相対パス)
    pub notes: Vec<(String, String)>,
}

impl Vault {
    pub fn from_env() -> Vault {
        let root = std::env::var("SANCTUM_VAULT")
            .map(PathBuf::from)
            .unwrap_or_else(|_| find_repo_root());
        let root = root.canonicalize().unwrap_or(root);
        // ASSUMPTION: projects/ は他リポジトリの作業場で巨大なため既定で除外する。
        // SANCTUM_EXCLUDE（カンマ区切り）で差し替え可能。
        let excludes = std::env::var("SANCTUM_EXCLUDE")
            .unwrap_or_else(|_| "projects".to_string())
            .split(',')
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty())
            .collect();
        Vault { root, excludes }
    }

    pub fn root(&self) -> &Path {
        &self.root
    }

    fn is_excluded_dir(&self, name: &str) -> bool {
        name.starts_with('.')
            || name == "node_modules"
            || name == "target"
            || self.excludes.iter().any(|e| e == name)
    }

    /// vault 相対パスを検証して絶対パスに解決する。
    /// ルート外への脱出（`..` / 絶対パス）は None。
    pub fn resolve(&self, rel: &str) -> Option<PathBuf> {
        if rel.is_empty() {
            return None;
        }
        let p = Path::new(rel);
        let mut clean = PathBuf::new();
        for comp in p.components() {
            match comp {
                Component::Normal(seg) => clean.push(seg),
                Component::CurDir => {}
                _ => return None,
            }
        }
        if clean.as_os_str().is_empty() {
            return None;
        }
        Some(self.root.join(clean))
    }

    /// ノート（.md）として読み書きしてよいパスか検証して解決する。
    pub fn resolve_note(&self, rel: &str) -> Option<PathBuf> {
        if !is_md(rel) {
            return None;
        }
        self.resolve(rel)
    }

    pub fn read_note(&self, rel: &str) -> Option<String> {
        let path = self.resolve_note(rel)?;
        fs::read_to_string(path).ok()
    }

    pub fn write_note(&self, rel: &str, content: &str) -> Result<(), String> {
        let path = self
            .resolve_note(rel)
            .ok_or_else(|| format!("不正なパスです: {rel}"))?;
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        fs::write(path, content).map_err(|e| e.to_string())
    }

    /// 全ノートを走査する（インデックス構築用）。
    pub(crate) fn walk_notes(&self, f: &mut dyn FnMut(&str, &Path)) {
        self.walk(&self.root, 0, f);
    }

    /// 指定した vault 相対ディレクトリ配下のノートを走査する
    /// （既定の走査から除外されているディレクトリをツリーに追加した場合の補完用）。
    pub(crate) fn walk_notes_at(&self, rel: &str, f: &mut dyn FnMut(&str, &Path)) {
        let Some(abs) = self.resolve(rel) else {
            return;
        };
        self.walk_inner(&abs, rel, 0, f);
    }

    /// rel のパス成分に除外ディレクトリ名が含まれるか
    /// （= 既定の全体走査ではたどり着けない場所か）。
    pub(crate) fn is_rel_excluded(&self, rel: &str) -> bool {
        rel.split('/').any(|seg| self.is_excluded_dir(seg))
    }

    /// 指定した vault 相対ディレクトリを根とするサブツリー。
    /// rel が "." または空なら vault 全体。存在しない・ディレクトリでないなら None。
    pub fn tree_at(&self, rel: &str) -> Option<DirNode> {
        if rel == "." || rel.is_empty() {
            let mut node = self.build_dir(&self.root, "", 0);
            node.name = ".".to_string();
            return Some(node);
        }
        let abs = self.resolve(rel)?;
        if !abs.is_dir() {
            return None;
        }
        let mut node = self.build_dir(&abs, rel, 0);
        node.name = rel.to_string();
        Some(node)
    }

    fn build_dir(&self, dir: &Path, rel: &str, depth: usize) -> DirNode {
        let name = dir
            .file_name()
            .map(|n| n.to_string_lossy().to_string())
            .unwrap_or_default();
        let mut node = DirNode {
            name,
            dirs: Vec::new(),
            notes: Vec::new(),
        };
        if depth > MAX_DEPTH {
            return node;
        }
        let Ok(entries) = fs::read_dir(dir) else {
            return node;
        };
        let mut entries: Vec<_> = entries.flatten().collect();
        entries.sort_by_key(|e| e.file_name());
        for entry in entries {
            let fname = entry.file_name().to_string_lossy().to_string();
            let child_rel = if rel.is_empty() {
                fname.clone()
            } else {
                format!("{rel}/{fname}")
            };
            let Ok(ftype) = entry.file_type() else {
                continue;
            };
            let is_dir = if ftype.is_symlink() {
                fs::metadata(entry.path())
                    .map(|m| m.is_dir())
                    .unwrap_or(false)
            } else {
                ftype.is_dir()
            };
            if is_dir {
                if self.is_excluded_dir(&fname) {
                    continue;
                }
                let child = self.build_dir(&entry.path(), &child_rel, depth + 1);
                // md を 1 つも含まないディレクトリはツリーに出さない
                if !child.dirs.is_empty() || !child.notes.is_empty() {
                    node.dirs.push(child);
                }
            } else if is_md(&fname) {
                node.notes.push((fname, child_rel));
            }
        }
        node
    }

    fn walk(&self, dir: &Path, depth: usize, f: &mut dyn FnMut(&str, &Path)) {
        self.walk_inner(dir, "", depth, f);
    }

    fn walk_inner(&self, dir: &Path, rel: &str, depth: usize, f: &mut dyn FnMut(&str, &Path)) {
        if depth > MAX_DEPTH {
            return;
        }
        let Ok(entries) = fs::read_dir(dir) else {
            return;
        };
        for entry in entries.flatten() {
            let fname = entry.file_name().to_string_lossy().to_string();
            let child_rel = if rel.is_empty() {
                fname.clone()
            } else {
                format!("{rel}/{fname}")
            };
            let Ok(ftype) = entry.file_type() else {
                continue;
            };
            let is_dir = if ftype.is_symlink() {
                fs::metadata(entry.path())
                    .map(|m| m.is_dir())
                    .unwrap_or(false)
            } else {
                ftype.is_dir()
            };
            if is_dir {
                if !self.is_excluded_dir(&fname) {
                    self.walk_inner(&entry.path(), &child_rel, depth + 1, f);
                }
            } else if is_md(&fname) {
                f(&child_rel, &entry.path());
            }
        }
    }
}

/// ファイルの更新時刻（UNIX epoch ミリ秒）。
pub fn mtime_ms(path: &Path) -> Option<u64> {
    fs::metadata(path)
        .ok()?
        .modified()
        .ok()?
        .duration_since(std::time::UNIX_EPOCH)
        .ok()
        .map(|d| d.as_millis() as u64)
}

pub fn is_md(path: &str) -> bool {
    Path::new(path)
        .extension()
        .map(|e| e.eq_ignore_ascii_case("md"))
        .unwrap_or(false)
}

/// 本文中の `[[...]]` の中身を列挙する（コードブロックは考慮しない素朴な走査）。
pub(crate) fn extract_wikilink_targets(content: &str) -> Vec<String> {
    let mut out = Vec::new();
    let bytes = content.as_bytes();
    let mut i = 0;
    while i + 1 < bytes.len() {
        if bytes[i] == b'[' && bytes[i + 1] == b'[' {
            if let Some(end) = content[i + 2..].find("]]") {
                let inner = &content[i + 2..i + 2 + end];
                if !inner.is_empty() && !inner.contains('\n') {
                    out.push(inner.to_string());
                }
                i += 2 + end + 2;
                continue;
            }
        }
        i += 1;
    }
    out
}

/// 本文中の `#tag` を列挙する（フェンスコードブロックは除外、重複除去）。
/// 見出し（`# ` や `##`）はタグ扱いしない。数字のみのタグも除外。
pub(crate) fn extract_tags(content: &str) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    let mut in_fence = false;
    for line in content.lines() {
        let trimmed = line.trim_start();
        if trimmed.starts_with("```") || trimmed.starts_with("~~~") {
            in_fence = !in_fence;
            continue;
        }
        if in_fence {
            continue;
        }
        for tag in extract_tags_in_text(line) {
            if !out.contains(&tag) {
                out.push(tag);
            }
        }
    }
    out
}

/// 1 行（またはテキスト断片）から `#tag` を取り出す。
pub(crate) fn extract_tags_in_text(text: &str) -> Vec<String> {
    let chars: Vec<char> = text.chars().collect();
    let mut out = Vec::new();
    let mut i = 0;
    while i < chars.len() {
        if chars[i] == '#' {
            let prev_ok = i == 0 || chars[i - 1].is_whitespace();
            let next_ok = chars.get(i + 1).map(|c| is_tag_char(*c)).unwrap_or(false);
            if prev_ok && next_ok {
                let mut j = i + 1;
                let mut tag = String::new();
                while j < chars.len() && is_tag_char(chars[j]) {
                    tag.push(chars[j]);
                    j += 1;
                }
                if !tag.chars().all(|c| c.is_ascii_digit()) {
                    out.push(tag);
                }
                i = j;
                continue;
            }
        }
        i += 1;
    }
    out
}

pub(crate) fn is_tag_char(c: char) -> bool {
    c.is_alphanumeric() || c == '-' || c == '_' || c == '/'
}

/// カレントディレクトリから上に辿って git リポジトリのルートを探す。
fn find_repo_root() -> PathBuf {
    let cwd = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    let mut dir = cwd.as_path();
    loop {
        if dir.join(".git").exists() {
            return dir.to_path_buf();
        }
        match dir.parent() {
            Some(parent) => dir = parent,
            None => return cwd,
        }
    }
}
