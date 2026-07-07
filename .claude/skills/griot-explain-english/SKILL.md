---
name: griot-explain-english
description: >-
  説明練習の英語化スキル(griot 説明練習パイプラインの Step 4。英語学習用の派生ステップ)。
  griot-explain-prep のノート・資料(添削 review.md があればその改善を反映)を入力に、
  英語版の 1 枚 HTML 説明資料(deck-en.html)と、声に出して読むための口語スクリプト
  (script-en.md: 英語スクリプト + 日本語対訳 + キーフレーズ)を生成する。
  日本語で説明練習した内容を英語でも発声して英語学習を兼ねるのが目的。
  「これを英語でも練習したい」「英語版の資料とスクリプト作って」等で起動。
model: sonnet
metadata:
  type: skill
  stage: 4
  pairs_with: griot-explain-prep, griot-explain-coach
  data_dir: <repo>/explain-practice-data
---

# griot-explain-english — 説明の英語化（Step 4・英語練習用）

日本語で練習した説明を英語でも発声できるように、**英語版資料**と**音読用スクリプト**を作る。
説明練習そのものの添削は Step 3（griot-explain-coach）の領分。ここは英語学習を兼ねた派生ステップ。
persona は [`personas/griot.md`](../../../personas/griot.md)（語学練習: 練習対象言語は英語、解説は日本語）。

## データ配置

- 入力: `<repo>/explain-practice-data/sessions/<YYYY-MM-DD>-<slug>/` の
  `note.md`・`deck.html`（＋あれば `review.md`）
- 出力: 同セッション配下 `en/`
  - `deck-en.html` — 英語版説明資料（テンプレは prep の
    [`templates/deck.html`](../griot-explain-prep/templates/deck.html) を流用。単一ソース維持のためコピーを持たない）
  - `script-en.md` — 音読用スクリプト（テンプレ: [`templates/script-en.md`](templates/script-en.md)）

## トリガー

| ユーザー発話の例 | 動作 |
|---|---|
| 「これを英語でも練習したい」「英語版も作って」 | 直近 or 指定セッションを英語化 |
| 「英語スクリプトだけ作り直して」 | script-en.md のみ再生成 |

## 標準フロー

### 1. 対象セッションと入力の確定

- 対象セッションを特定（既定 = 直近。`sessions/` を ls して候補提示）。
- **`review.md` があれば添削を反映した流れで英語化する**（指摘された構成・結論先出しの
  改善を英語版に取り込む。添削前の悪い構成をそのまま英訳しない）。
  無ければ note.md の「説明の流れ」に従う。

### 2. 英語版資料の生成（deck-en.html）

- prep の `templates/deck.html` に従い、英語で埋めて `en/deck-en.html` に出力する。
  デザイン・構成は日本語版と同一（`lang="en"` に変更。見出しは Why / What / How /
  Example / Speaking order 等の対応英語）。
- 日本語版と同じく**キーワードのみ**。読み上げ原稿にしない。

### 3. 音読用スクリプトの生成（script-en.md）

`templates/script-en.md` の書式で、資料のセクション（結論 → なぜ → 何を → どうやって →
具体例 → まとめ）に対応させて作る。方針:

- **スポークンスタイル**で書く（書き言葉の直訳にしない）。1 文はおよそ 15 語以内。
  声に出して読んで息継ぎできる長さに切る。
- 全体で 2〜3 分で話し切れる分量（およそ 250〜350 語）。
- 語彙レベルは**想定聞き手（note.md の audience）が英語話者だったら**で調整する
  （非エンジニア相手なら技術用語に一言の言い換えを添える、等）。
- 各セクションに **日本語対訳**と **Key phrases**（説明・報告で使い回せる言い回し 2〜3 個）を付ける。
- 発音・リズムで詰まりやすい語（音節の多い語・カタカナ語と音が違う語）を
  末尾の「発音注意」にまとめる。

### 4. 完了提示

- 生成パス 2 件と、使い方を一言（「deck-en.html を見ながら script-en.md を見ずに話す →
  詰まったらスクリプトを確認、を繰り返すと効きます」）。

## 注意

- 内容の創作をしない。note.md / review.md に無い情報・主張を英語版で足さない
  （自然な英語にするための言い回しの変更・文の分割はよい）。
- ユーザーが英語版スクリプトの読み上げを添削してほしい場合は griot-explain-coach を案内する
  （その際の指摘も同じ台帳に記録される。persona は「英語話者の◯◯」として渡す）。
- 過去セッションの英語化はいつでも可（en/ が無いセッションを後からまとめて英語化してよい）。
- 解説・対訳は日本語、スクリプト本文は英語。機密情報を出力に含めない。
