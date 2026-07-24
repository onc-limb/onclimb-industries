//! アプリ設定。
//!
//! - 起動時設定: `sanctum/sanctum.json`（git 管理外）。memo-data の場所を定義する。
//!   無ければ既定値で動く。雛形は `sanctum.json.example`。
//! - 実行中に変わる設定: `<memo-data>/config.json`。ツリーに追加した表示フォルダの一覧。

use std::sync::OnceLock;

use serde::{Deserialize, Serialize};

use crate::vault;

/// 起動時設定ファイル（vault ルートからの相対パス）。
const STARTUP_CONFIG_REL: &str = "sanctum/sanctum.json";

const DEFAULT_MEMO_DATA: &str = "memo-data";

#[derive(Deserialize, Default)]
struct StartupFile {
    /// メモ実データ置き場（vault 相対）。デイリーノート・テンプレート・
    /// ツリー設定・貼り付け画像はすべてこの配下に置かれる。
    memo_data: Option<String>,
}

static MEMO_DATA: OnceLock<String> = OnceLock::new();

/// 起動時に一度だけ呼ぶ。`sanctum/sanctum.json` を読んで memo-data の場所を確定する。
pub fn init_startup() {
    let loaded = vault::instance()
        .resolve(STARTUP_CONFIG_REL)
        .and_then(|p| std::fs::read_to_string(p).ok())
        .and_then(|s| serde_json::from_str::<StartupFile>(&s).ok())
        .and_then(|f| f.memo_data)
        .map(|s| s.trim().trim_matches('/').to_string())
        .filter(|s| !s.is_empty());
    let _ = MEMO_DATA.set(loaded.unwrap_or_else(|| DEFAULT_MEMO_DATA.to_string()));
}

/// メモ実データ置き場（vault 相対）。ツリーの先頭に固定表示される。
pub fn memo_data() -> &'static str {
    MEMO_DATA
        .get()
        .map(|s| s.as_str())
        .unwrap_or(DEFAULT_MEMO_DATA)
}

pub fn daily_dir() -> String {
    format!("{}/daily", memo_data())
}

pub fn templates_dir() -> String {
    format!("{}/templates", memo_data())
}

fn tree_config_rel() -> String {
    format!("{}/config.json", memo_data())
}

#[derive(Serialize, Deserialize, Default)]
struct TreeConfig {
    #[serde(default)]
    tree_roots: Vec<String>,
}

fn load_tree_config() -> TreeConfig {
    let Some(path) = vault::instance().resolve(&tree_config_rel()) else {
        return TreeConfig::default();
    };
    std::fs::read_to_string(path)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or_default()
}

/// ツリーに追加表示するフォルダ（vault 相対パス）。memo-data は含まない（常時固定のため）。
pub fn tree_roots() -> Vec<String> {
    load_tree_config()
        .tree_roots
        .into_iter()
        .filter(|r| r != memo_data())
        .collect()
}

pub fn save_tree_roots(roots: &[String]) -> Result<(), String> {
    let path = vault::instance()
        .resolve(&tree_config_rel())
        .ok_or_else(|| "設定ファイルのパスを解決できません".to_string())?;
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let config = TreeConfig {
        tree_roots: roots
            .iter()
            .filter(|r| *r != memo_data())
            .cloned()
            .collect(),
    };
    let json = serde_json::to_string_pretty(&config).map_err(|e| e.to_string())?;
    std::fs::write(path, json).map_err(|e| e.to_string())
}
