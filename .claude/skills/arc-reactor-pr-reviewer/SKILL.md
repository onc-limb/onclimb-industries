---
name: arc-reactor-pr-reviewer
description: GitHub PR を対象にした観点別コードレビュースキル。gh CLI で PR のメタ情報・diff・既存コメントを取得し、固定チェックリスト(references/review-checklist.md)に沿って バグ / 可読性 / 規約(+補助: テスト / セキュリティ)の観点別に、重要度ラベル([must]/[imo]/[nit]/[ask])と file:line 付きのレビューコメントを生成する。対象リポジトリの CLAUDE.md や linter 設定からプロジェクト規約を読み取り指摘の根拠にする。デフォルトはチャットへの下書き提示で、ユーザーの明示承認後にのみ gh で PR へ投稿する。「PR #123 をレビューして」「この PR のレビューコメント作って」「PR を観点別にレビューして」「レビューコメントを GitHub に投稿して」等で起動。ローカルの作業中 diff(自分の変更)を検品する /code-review とは別系統で、本スキルは GitHub 上の PR(主に他人の変更)へのレビューを担う。
metadata:
  type: skill
---

# arc-reactor-pr-reviewer — GitHub PR の観点別レビュー

GitHub PR を入力に、**観点別（バグ / 可読性 / 規約）・投稿可能なレビューコメント**を生成するスキル。
レビューの初動を自動化し、観点の属人化を references の固定チェックリストで防ぐ。

## 役割

- `gh` CLI で PR の diff・説明・既存コメントを取得し、レビューの土台を数分で用意する。
- [references/review-checklist.md](references/review-checklist.md) の固定観点で diff を評価し、
  指摘を「観点ラベル + 重要度ラベル + `file:line`」の統一書式で提示する。
- 対象リポジトリのプロジェクト規約（CLAUDE.md / linter 設定 / CONTRIBUTING.md）を根拠として引用する。
- ユーザーが承認した指摘のみを、`gh` で PR 上のレビューコメントとして投稿する。

## /code-review との棲み分け

| | `/code-review`（組み込み） | 本スキル |
|---|---|---|
| 対象 | ローカルの作業中 diff（自分の変更） | GitHub 上の PR（主に他人の変更） |
| 目的 | コミット前の検品（バグ + 品質改善） | レビュー成果物の作成（観点別コメント） |
| 観点 | 汎用（正しさ・簡素化・効率） | チェックリストで固定（バグ / 可読性 / 規約 + 補助観点） |
| 成果物の置き場 | チャット内 / 作業ツリーへの適用 | チャット下書き → 承認後に PR 上へ投稿 |
| 規約参照 | なし | 対象リポジトリの規約ファイルを読み取り根拠にする |

自分のコミット前の変更を見たいときは `/code-review` を案内し、本スキルは起動しない。
組み込みの `/review` とも異なり、本スキルは観点・書式の固定とプロジェクト規約の参照を担う。

## トリガーと対応フロー

| ユーザー発話の例 | 動作 |
|---|---|
| 「PR #123 をレビューして」 | 全観点でレビューし下書きを提示 |
| 「この PR のレビューコメント作って」 | 会話中の PR を対象に下書きを提示 |
| 「PR を観点別にレビューして」「バグと規約だけ見て」 | 指定観点に絞ってレビュー |
| 「https://github.com/o/r/pull/45 を見て」 | URL から repo / 番号を解決してレビュー |
| 「レビューコメントを GitHub に投稿して」 | 提示済み下書きを承認扱いで PR へ投稿 |

## 標準フロー

1. **PR の解決**: 発話から PR 参照（番号 / URL / ブランチ名）を特定する。repo が不明なら
   cwd の `git remote` から解決し、それも無ければユーザーに `owner/repo` を確認する。
2. **PR 情報の取得**（読み取りのみ）:

   ```bash
   gh pr view <num> --repo <owner/repo> --json title,body,url,baseRefName,headRefName,headRefOid,files,additions,deletions
   gh pr diff <num> --repo <owner/repo>
   gh pr view <num> --repo <owner/repo> --comments   # 既存コメント（指摘の重複回避に使う）
   ```

3. **プロジェクト規約の読み込み**: 対象リポジトリの CLAUDE.md / linter・formatter 設定
   （`.eslintrc*`, `ruff.toml`, `.editorconfig` 等）/ CONTRIBUTING.md を確認する。
   ローカルに clone が無ければ `gh api repos/<owner>/<repo>/contents/<path>` で取得する。
   規約が見つからなければ、規約観点の指摘には根拠が推測である旨を ASSUMPTION として明記する。
4. **diff の下ごしらえ**: 自動生成物（lock ファイル、ビルド成果物）はレビュー対象から除外。
   巨大 diff（目安: 数千行超）はファイル単位に分割してレビューし、見きれない場合は
   重点ファイルを選んだうえで「未レビュー範囲」を必ず明示する。
5. **観点別レビュー**: [references/review-checklist.md](references/review-checklist.md) の
   観点（バグ / 可読性 / 規約 + 補助: テスト / セキュリティ）を順に適用する。
   ユーザーが観点を指定した場合はその観点に絞る。既存コメントと重複する指摘は除外 or「既出」と注記。
6. **下書きの提示**: 後述の出力フォーマットでチャットに提示する。**この時点では PR に一切書き込まない。**
7. **投稿（明示承認後のみ）**: ユーザーが投稿を承認したら実行する。

   ```bash
   # 総評（PR 全体へのコメント）
   gh pr review <num> --repo <owner/repo> --comment --body "<総評>"

   # インラインコメント（headRefOid を commit_id に使う）
   gh api repos/<owner>/<repo>/pulls/<num>/comments \
     -f body="<指摘本文>" -f commit_id="<headRefOid>" \
     -f path="<file>" -F line=<line> -f side=RIGHT
   ```

   承認 (`--approve`) / 変更要求 (`--request-changes`) は、ユーザーがそのように明示した場合のみ使う。
8. **完了報告**: 投稿した場合はコメントの URL、下書きのみの場合は指摘件数の観点別内訳を提示する。

## レビュー観点

観点の定義・チェック項目・重要度ラベル（[must]/[imo]/[nit]/[ask]）の使い分けは
[references/review-checklist.md](references/review-checklist.md) を正とする。
観点を追加・修正したいときはチェックリスト側を更新する（本文には観点の詳細を重複して書かない）。

## 出力フォーマット

```markdown
## PR レビュー: <PR タイトル> (#<num>)

### サマリ
- 変更概要: <1〜2 文>
- 指摘件数: must <n> / imo <n> / nit <n> / ask <n>
- 未レビュー範囲: <なし | 除外・分割したファイルと理由>

### 指摘一覧
#### バグ
- [must] `src/app.py:42` — <指摘>。<根拠>。提案: <修正案>

#### 可読性
- [imo] `src/util.py:10` — <指摘>...

#### 規約
- [nit] `src/api.ts:5` — <指摘>（根拠: <規約ファイルの該当箇所>）

### 総評（PR に投稿する場合の本文）
<ねぎらい + 全体所感 + must の要約>
```

- 指摘は必ず「観点見出し配下 + 重要度ラベル + `file:line`」を揃える。該当なしの観点は「指摘なし」と書く。
- 良い変更点はレビューの信頼のために総評で 1 つ以上言及する。

## 品質・安全性

- **無承認投稿の禁止**: PR への書き込み（`gh pr review` / `gh api` の POST）は、下書き提示後に
  ユーザーが明示承認した場合のみ実行する。デフォルトは常に下書き。
- **ASSUMPTION の明記**: diff 外のコンテキストや規約を推測で補った指摘には、指摘文中に
  `(ASSUMPTION: ...)` と根拠が推測であることを明記する。確信の持てない指摘は [ask] に落とし質問形式にする。
- **機密を含めない**: diff にトークン・鍵などのシークレット様文字列を見つけたら、値は伏せたまま
  「機密の混入疑い」として [must] で指摘する。レビューコメントに機密値を転記しない。
- **創作しない**: diff と取得した規約・コメントに無い事実を根拠にしない。根拠は引用できる形で添える。
- **既存スタイル尊重**: 規約観点の指摘は対象リポジトリの既存規約に基づくものに限り、
  自分の好みの規約を持ち込まない（根拠のない様式指摘はしない）。
