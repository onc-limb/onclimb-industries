# ツールチェーン

[Vite+](https://viteplus.dev/) を統合ツールチェーンとして使用する。ビルド・Lint・フォーマット・テスト・タスク実行を単一の CLI (`vp`) に集約し、個別ツールの設定・バージョン管理を不要にする。

| 用途 | ツール（Vite+ 内蔵） |
| ---- | ------ |
| ビルド / 開発サーバー | Vite + Rolldown |
| Linter | Oxlint（ESLint 互換 600+ ルール） |
| Formatter | Oxfmt（Prettier 互換） |
| 静的解析 / 型チェック | tsgo |
| テストランナー | Vitest |
| コミット時チェック | `vp check`（staged 設定で lint + format + type-check を一括実行） |
| E2E テスト | Playwright |
| モックライブラリ | `vi.fn()` / `vi.mock()`（手動スタブ優先） |

## 主要コマンド

| コマンド | 用途 |
| -------- | ---- |
| `vp dev` | 開発サーバー起動 |
| `vp build` | プロダクションビルド |
| `vp check` | フォーマット + Lint + 型チェックを一括実行 |
| `vp test` | テスト実行（Vitest） |
| `vp run` | スクリプト実行（キャッシュ付き） |
| `vp install` | 依存パッケージのインストール |

## 設定方針

- Vite+ の統一設定ファイルで lint / fmt / test / build の設定を一元管理する
- SolidJS の JSX 変換は Vite プラグイン（`vite-plugin-solid`）で行う
- TanStack Start は Vite をベースとしており、`app.config.ts` で TanStack Router のプラグイン設定を行う
- パスエイリアス `~` は Vite の `resolve.alias` で設定する

## Lint 方針

- フォーマットは Oxfmt に委譲し、Oxlint はロジック上の問題検出に集中する
- Oxlint の ESLint 互換ルールで SolidJS 固有のルール（リアクティビティの誤用検出等）を適用する
- `import/no-cycle` 相当のルールで feature 間の循環依存を検出する
