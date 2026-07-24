# Vendored ライブラリ

CDN 非依存（貸与 PC のネット制限・オフラインでも動く）のためリポジトリに同梱する。
更新時は OSV（https://api.osv.dev）で既知脆弱性が無いことを確認してから差し替え、
この表のバージョンと SHA-256 を更新すること。

| ファイル | パッケージ | バージョン | 取得元 | SHA-256 |
|----------|-----------|-----------|--------|---------|
| mermaid.min.js | mermaid (npm) | 11.16.0 | cdn.jsdelivr.net/npm/mermaid@11.16.0/dist/mermaid.min.js | 74d7c46dabca328c2294733910a8aa1ed0c37451776e8d5295da38a2b758fb9b |
| highlight.min.js | highlight.js (npm) | 11.11.1 | cdnjs.cloudflare.com/ajax/libs/highlight.js/11.11.1/highlight.min.js | c4a399dd6f488bc97a3546e3476747b3e714c99c57b9473154c6fb8d259b9381 |
| hljs-github.min.css | highlight.js styles | 11.11.1 | 同上 /styles/github.min.css | 3a9a5def8b9c311e5ae43abde85c63133185eed4f0d9f67fea4b00a8308cf066 |
| hljs-github-dark.min.css | highlight.js styles | 11.11.1 | 同上 /styles/github-dark.min.css | 9f208d022102b1d0c7aebfecd8e42ca7997d5de636649d2b31ea63093d809019 |

確認日: 2026-07-24（両パッケージとも OSV 照会で vulnerabilities: 0）
