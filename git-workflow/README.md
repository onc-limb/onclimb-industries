# Git 運用ルール

## ブランチ戦略

<!-- ASSUMPTION: GitHub Flow ベースを採用。プロジェクト規模が小〜中規模と推測 -->

| ブランチ | 用途 | 保護 |
|----------|------|------|
| `main` | 本番リリース可能な状態を維持 | force push 禁止、PR 必須 |
| `feature/*` | 新機能の開発 | — |
| `fix/*` | バグ修正 | — |
| `docs/*` | ドキュメント変更 | — |
| `refactor/*` | リファクタリング | — |
| `chore/*` | 設定変更・依存更新等 | — |

### ブランチ命名規則

```
{type}/{短い説明}
```

例: `feature/add-user-auth`, `fix/login-redirect-loop`

- 英語・小文字・ハイフン区切り
- Issue 番号がある場合: `feature/123-add-user-auth`

## コミットメッセージ規約

[Conventional Commits](https://www.conventionalcommits.org/) に準拠する。

```
{type}({scope}): {概要}

{本文（任意）}

{フッター（任意）}
```

### type 一覧

| type | 用途 |
|------|------|
| `feat` | 新機能 |
| `fix` | バグ修正 |
| `docs` | ドキュメントのみの変更 |
| `refactor` | 機能変更を伴わないコード改善 |
| `test` | テストの追加・修正 |
| `chore` | ビルド・CI・依存関係等の変更 |
| `style` | フォーマット変更（動作に影響なし） |
| `perf` | パフォーマンス改善 |
| `ci` | CI 設定の変更 |

### ルール

- 概要は命令形・英語・50文字以内
- 本文は「なぜ」を説明する（「何を」はコードが語る）
- 破壊的変更は `BREAKING CHANGE:` フッターまたは `!` を付与

## マージルール

<!-- ASSUMPTION: チーム開発を想定し、レビュー1名以上を要求 -->

1. PR 作成時に変更内容の概要を記載する
2. 最低1名のレビュー承認を得る
3. CI（リント・テスト）が通っていること
4. マージ方法は **Squash merge** を基本とする
5. マージ後、リモートのトピックブランチは削除する

## タグ・リリース

<!-- ASSUMPTION: セマンティックバージョニングを採用 -->

- [Semantic Versioning](https://semver.org/) に従う: `vMAJOR.MINOR.PATCH`
- リリースタグは `main` ブランチに対して打つ
- CHANGELOG はタグ作成時に更新する
