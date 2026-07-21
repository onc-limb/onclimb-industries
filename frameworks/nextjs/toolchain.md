# ツールチェーン

以下のツールを使用する。

| 用途 | ツール |
| ---- | ------ |
| Linter | ESLint (flat config: `eslint.config.js`) + `@next/eslint-plugin-next` |
| Formatter | Prettier (`.prettierrc`) |
| 静的解析 | TypeScript `strict: true` (`tsconfig.json`) |
| コミット時チェック | lint-staged + husky |
| テストランナー | Vitest |
| E2E テスト | Playwright |
| モックライブラリ | `vi.fn()` / `vi.mock()`（手動スタブ優先） |

## ESLint 設定方針

- フォーマットは Prettier に委譲し、ESLint はロジック上の問題検出に集中する
- `@next/eslint-plugin-next` で Next.js 固有のルールを適用する
- `eslint-plugin-import` の `import/no-cycle` で feature 間の循環依存を検出する
