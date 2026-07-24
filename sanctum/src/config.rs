//! アプリ設定の永続化（memo-data/config.json）。
//! 現在はサイドバーのツリーに表示するフォルダの一覧のみ。

use serde::{Deserialize, Serialize};

use crate::vault;

/// 設定ファイルの vault 相対パス。
const CONFIG_REL: &str = "memo-data/config.json";

/// ツリーに表示するフォルダの既定値。
const DEFAULT_ROOTS: &[&str] = &["memo-data"];

#[derive(Serialize, Deserialize, Default)]
struct Config {
    /// None = 未設定（既定値を使う）。空配列は「何も表示しない」の明示。
    #[serde(default, skip_serializing_if = "Option::is_none")]
    tree_roots: Option<Vec<String>>,
}

fn load() -> Config {
    let Some(path) = vault::instance().resolve(CONFIG_REL) else {
        return Config::default();
    };
    std::fs::read_to_string(path)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or_default()
}

/// ツリーに表示するフォルダ（vault 相対パス。"." は vault 全体）。
pub fn tree_roots() -> Vec<String> {
    load()
        .tree_roots
        .unwrap_or_else(|| DEFAULT_ROOTS.iter().map(|s| s.to_string()).collect())
}

pub fn save_tree_roots(roots: &[String]) -> Result<(), String> {
    let path = vault::instance()
        .resolve(CONFIG_REL)
        .ok_or_else(|| "設定ファイルのパスを解決できません".to_string())?;
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let mut config = load();
    config.tree_roots = Some(roots.to_vec());
    let json = serde_json::to_string_pretty(&config).map_err(|e| e.to_string())?;
    std::fs::write(path, json).map_err(|e| e.to_string())
}
