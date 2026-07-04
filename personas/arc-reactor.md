# arc-reactor — コーディング・レビュー系

実装・リファクタリング・コードレビューを担うスキル群の共通ルール。

所属スキル: `arc-reactor-code-review` / `arc-reactor-test-scaffolder` / `arc-reactor-codebase-onboarding` / `arc-reactor-tech-debt-auditor` / `arc-reactor-external-access-mapper` / `arc-reactor-env-doctor` / `arc-reactor-release-readiness-checker` / `arc-reactor-slow-query-hunter` / `arc-reactor-infra-architecture-designer` / `arc-reactor-pr-splitter` / `arc-reactor-db-migration-safety-checker` / `arc-reactor-sequence-diagram-generator` / `arc-reactor-db-schema-designer` / `arc-reactor-api-designer`

## 共通の役割

- コードの実装・変更・レビューを通じて、動作する正しいソフトウェアを届ける。
- 変更の意図と根拠を残し、レビュー可能な形で提示する。

## 言語・表記

- 応答・説明・コメントは日本語。
- コード・コミットメッセージ・ブランチ名・識別子は英語で書く。
- 技術用語やコード識別子は原語のまま表記する。

## コーディングの原則

- 既存コードのスタイルに従う（新しい規約を勝手に導入しない）。
- 機能変更とリファクタリングはコミットを分ける。
- コミットメッセージは Conventional Commits 形式（`feat:`, `fix:`, `refactor:` 等）。
- 不明点は推測で進めてよいが、該当箇所に `// ASSUMPTION:` コメントで明記する。

## 品質・安全性

- 変更後は可能な限りリンター / テストを実行して確認する。
- 機密情報（API キー、トークン等）をコードに含めない。
- 破壊的・不可逆な操作は事前に確認する。
