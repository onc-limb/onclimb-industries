# architecture/ — 設計知識の正本

設計原則・コードスメル・結合/依存のヒューリスティックなど、フレームワークに依存しない
アーキテクチャ知識を 1 テーマ 1 ファイルで蓄積するディレクトリ。
旧 my-best-practices リポジトリの `standards/coding-rules/` と、
arc-reactor-architecture-review スキルの初期 knowledge を統合したもの。

- `arc-reactor-architecture-review` スキルが週次レビューの判断基準としてここを全部読む
  （どのファイルを読むかはスキル側の `perspectives/<観点>/INDEX.md` が管理）。
- レビュー観点として追記するときの書式はスキル側の
  `.claude/skills/arc-reactor-architecture-review/perspectives/general/knowledge-template.md`。
  書式に従わない原則ドキュメント（clean-architecture.md 等）が混ざっていてもよい。
- フレームワーク固有の知識は `frameworks/<fw>/`、テスト戦略は `testing/` へ。
