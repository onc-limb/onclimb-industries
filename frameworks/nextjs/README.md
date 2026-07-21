# Next.js コーディング規約

<!-- 前提: アーキテクチャ規約・テスト戦略は別ドキュメントで定義済み -->
<!-- 本ドキュメントはそれらを「Next.js + React でどう実装するか」に特化する -->

## 参照する基盤ドキュメント

本規約は以下の基盤ドキュメントに準拠する。各ドキュメントの内容はここでは繰り返さず、Next.js での具体的な実現方法を記載する。

| 基盤ドキュメント | 本規約での適用箇所 |
| --- | --- |
| [feature-based.md](../../architecture/feature-based.md) | ディレクトリ構成・コンポーネント分割 |
| [core-philosophy.md](../../architecture/core-philosophy.md) | DRY / YAGNI / KISS の判断基準 |
| [solid-principle.md](../../architecture/solid-principle.md) | インターフェース設計・責務分離 |
| [clean-architecture.md](../../architecture/clean-architecture.md) | レイヤー分離・依存方向 |
| [domain-model.md](../../architecture/domain-model.md) | 値オブジェクト・エンティティの実装 |
| [contract-programming.md](../../architecture/contract-programming.md) | バリデーション・事前条件の実装 |

## 技術スタック

- **Next.js**: v16 (App Router)
- **React**: 19
- **言語**: TypeScript (strict mode)
- **パッケージマネージャー**: pnpm
- **CSS**: Tailwind CSS
- **ORM**: Drizzle
- **バリデーション**: TypeBox
- **クライアントサイドデータ取得**: TanStack Query

## ドキュメント構成

用途に応じて必要なドキュメントを参照する。

| ファイル | 内容 | 参照タイミング |
| --- | --- | --- |
| [toolchain.md](toolchain.md) | Linter / Formatter / テストランナー等の設定 | 環境構築・CI 設定時 |
| [directory-structure.md](directory-structure.md) | ディレクトリ構成と各ディレクトリの責務 | 実装・レビュー時 |
| [naming-conventions.md](naming-conventions.md) | 命名規則・型定義の方針 | 実装・レビュー時 |
| [implementation-patterns.md](implementation-patterns.md) | Next.js 固有の実装パターン | 実装・レビュー時 |
| [testing.md](testing.md) | テストの書き方・配置・モック方針 | テスト作成・レビュー時 |
