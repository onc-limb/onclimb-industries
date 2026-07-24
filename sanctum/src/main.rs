//! Sanctum — onclimb-industries のローカルメモ Web アプリ（Obsidian 風）。
//! `cargo run` で起動し、既定で http://127.0.0.1:14141 から利用する。

mod api;
mod config;
mod index;
mod markdown;
mod pages;
mod vault;

use topcoat::router::{Router, RouterBuilderDiscoverExt};

/// 定番の開発ポート（3000/5173/8080 等）や macOS の AirPlay(5000)、
/// ephemeral 範囲(49152〜)と被らない既定ポート。
const DEFAULT_PORT: &str = "14141";

fn main() {
    // topcoat::start は PORT 環境変数を読むため、未指定時の既定をここで差し込む
    if std::env::var_os("PORT").is_none() {
        std::env::set_var("PORT", DEFAULT_PORT);
    }

    let v = vault::Vault::from_env();
    println!("Sanctum vault: {}", v.root().display());
    vault::init(v);
    config::init_startup();
    println!("Sanctum memo-data: {}", config::memo_data());

    let host = std::env::var("HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
    let port = std::env::var("PORT").unwrap_or_else(|_| DEFAULT_PORT.to_string());
    println!("Sanctum: http://{host}:{port}/");

    // 常駐前提のためワーカースレッドは 2 本に絞る（アイドル時のフットプリント削減）
    tokio::runtime::Builder::new_multi_thread()
        .worker_threads(2)
        .enable_all()
        .build()
        .unwrap()
        .block_on(async {
            topcoat::start(Router::builder().discover().build())
                .await
                .unwrap();
        });
}
