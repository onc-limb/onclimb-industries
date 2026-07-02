---
name: karen-problem-essence-organizer
description: フリーランス本人専用の思考整理スキル。会話・思考・作業ログから「課題発見 → 課題整理 → 解決定義 → 手段検討」の 4 フェーズを判定し、手段先行や目的喪失を批判的に指摘してオープン質問で深掘りする。最終アウトプットは自分用 md (4 章立て・重要/付随で分離) とクライアント向け HTML (Minto 流: 結論 → 根拠 → 提案 → 依頼)。「思考を整理したい」「考えをまとめたい」「一旦落ち着きたい」「目的ってなんだっけ」「一旦まとめよう」など、整理系発話やメタ自己制御発話で起動する。自己進化を備え、判断軸と出力フォーマットは使用ログから磨かれるが、対話スタイル (全肯定禁止 / 選択肢提示禁止 / オープン質問のみ) と 4 フェーズ構造は固定で進化対象外。
metadata:
  type: skill
  has_self_evolution_pipeline: true
  evolution_threshold_default: 10
---

# problem-essence-organizer

> **手段に飛び付かずに「課題の本質」を整理するための本人専用スキル。**
> 4 フェーズモデル × 重要/付随の二項分離 × 批判的オープン対話 × 自己進化。

このスキルは **自己進化** を備えている。

- モード (b)(c) の各サイクルを `logs/pipeline.jsonl` に記録し、完了条件 (`success` / `failure` / `unknown` / `error`) を必ず付与する。
- `pipeline.config.json` の `evolution_threshold` (既定 10) 回サイクルを回したら `scripts/evolve.py review` を実行し `EVOLUTION.md` に提案を追記する。**evolve.py がやるのは提案の起草まで。適用は EVOLUTION.md を読んだ Claude が `evolve.py snapshot` 実行後に Edit で行う (自動適用は無い)**。
- 採否判断は `references/evolution_principles.md` に準拠。**ただし対話スタイル 3 原則と 4 フェーズ構造は進化対象外** (`references/dialogue_style.md` に固定)。

## いつ呼び出すか

- **整理系**: 「思考を整理したい」「考えをまとめたい」「一旦まとめよう」「整理しよう」、議事録・作業メモを渡して「これを構造化して」「振り返って」
- **メタ自己制御系 (これが重要)**: 「一旦落ち着きたい」「ちょっと立ち止まりたい」「目的ってなんだっけ」「何のためにやってるんだっけ」「手段に飛びついてる気がする」「沼にハマってる」

メタ自己制御系は「手段先行 / 目的喪失」の自覚サインなので、**明示的な整理依頼でなくても起動する**。
undertriggering を避けるため、迷ったら起動する。ほかに、商談・参画前後の課題定義フェーズ、
個別最適化 / 検証作業に着手する前のチェックポイント、振り返り (会議・週次レビュー) でも明示的に呼ばれる。

## 中核モデル: 4 フェーズの進行ガイド

`[F1 課題発見] → [F2 課題整理] → [F3 解決定義] → [F4 手段検討]` + 逆流 (違反を検知して前段に戻す)

| フェーズ | 入る条件 | 完了アウトプット |
|---|---|---|
| **F1 課題発見 (Discovery)** | 課題の形すら決まっていない / 手段ベースの要望が出ている | 明確化された課題ステートメント |
| **F2 課題整理 (Structuring)** | 課題候補が複数 / 重なって混在 | 中心課題 (コア) + 外枠課題のリスト |
| **F3 解決定義 (Done Definition)** | 課題は明確だがゴール状態が未言語化 | 観測可能な Done 基準 |
| **F4 手段検討 (Solution)** | Done が定義済み | 手段候補と比較・選定理由 |

**逆流ルール (重要)**: 4 フェーズは一方向ではない。今いるフェーズの違反 (例: F1 なのに「RAG で」等の
手段の話が出る、F4 で「目的ってなんだっけ」発話) を検知したら **必ず前段に戻す**。
判定基準と戻りトリガー表は `references/judgment_axes.md` (進化対象) を参照。

## 3 つの使い方 (モード)

| モード | 使う瞬間 | スキルの動き | 主な出力 |
|---|---|---|---|
| **(a) リアルタイム介入** | 会話 / 思考の最中に呼ぶ | フェーズに対応する短い「ハッとフレーズ」or オープン質問を返す | 短文 1〜3 行 |
| **(b) 事後整理** | 議事録・作業メモを渡す | 4 フェーズの情報を抽出して構造化、不足項目を可視化 | `<topic>.md` / `<topic>__client-proposal.html` |
| **(c) 振り返り** | 会議や作業を終えて振り返る | 目的喪失・手段先行がなかったかを診断 | `<date>__retrospective.md` |

## 起動時の手順

パイプライン記録 (Step 0 / Step 5) は **モード (b)(c) で必須**。モード (a) はサイクル記録を省略してよい (残したい気付きがあればセッション末尾に `event=note` 1 行のみ)。

### Step 0. パイプライン開始 (モード b/c)

```bash
CYCLE_ID=$(python scripts/pipeline.py log-start \
  --skill-name problem-essence-organizer \
  --instruction "<受け取った指示の要約 (PII マスク)>")
```

### Step 1. 現在地のフェーズを確定

最初に必ず 1 分以内に確定する (確定できない場合は明示的に質問する):
(1) 今は F1〜F4 のどれか (2) モードは a/b/c のどれか (3) 「中心 (重要)」と「脇 (付随)」の分離が必要か。
判定方法は `references/judgment_axes.md`。

### Step 2. フェーズ違反を検知

「手段が課題として語られていないか」「Done が定義されていないか」「課題が混在していないか」をチェック。
違反があれば **オープン質問で前段に戻す** (`references/phase_questions.md`)。

### Step 3. フェーズ内の問いかけ・整理

各フェーズの定型問いセット (`references/phase_questions.md`) を使ってオープンに深掘りする。

### Step 4. アウトプット生成 (モード b/c)

- 自分用 md: `scripts/render_markdown.py` (モード c は `--mode retrospective`)。
- クライアント向け HTML: `scripts/render_html.py` (Minto 流)。
- 複数課題が並列している場合は **課題ごとにファイル分割** (`<topic>__<issue-slug>.md`)。

### Step 5. パイプライン終了 (モード b/c)

```bash
python scripts/pipeline.py log-end \
  --skill-name problem-essence-organizer \
  --cycle-id "$CYCLE_ID" \
  --completion-state success \
  --completion-reason "<根拠 (どの達成基準を満たしたか)>" \
  --output-summary "<アウトプットパス or 要約>" \
  --followup-feedback "<サイクル後のユーザー反応 (あれば)>" \
  --action '{"tool":"render_markdown.py","phase_at_close":"F3","backflow":"F4->F3"}'
```

- `--action` に判定フェーズ (`phase_at_close`) と逆流の有無 (`backflow`、無ければキー省略) を必ず記録する (進化レビューの材料)。
- 推測で進めた箇所は `--assumption-note "..."` で残す (コード内の印は `// ASSUMPTION:`)。
- 戻り JSON が `"evolution_due": true` なら `python scripts/evolve.py review` を実行する。
  review は完了時に `evolution-review` note を pipeline.jsonl へ自動追記し、進化カウンタをリセットする。
  提案の適用は EVOLUTION.md を読み、`evolve.py snapshot` を実行した後に Edit で行う。

## 対話スタイル (不変 — 進化対象外)

このスキルの **差別化の核**。`references/dialogue_style.md` で詳述。進化レビューでも書き換え禁止。

1. **全肯定しない** — ユーザーの言葉をなぞらない。批判的に突っ込む。「それで本当にいいのか」「目的とずれていないか」を最低 1 回は出す。
2. **選択肢を提示しない** — 「A or B or C のどれですか」型は禁止。視野を狭めるため。
3. **常にオープン質問** — 5W1H、特に「なぜ」「何を達成したら」「誰のために」を中心に。

短い割り込み用のキラーフレーズ台帳は `references/phase_questions.md` 冒頭を参照。

## 完了条件の判断指針

4 値 (`success` / `failure` / `unknown` / `error`) のセマンティクスは `references/pipeline_spec.md` §3、
フェーズ別の success 基準と failure 判定は `references/judgment_axes.md` の軸 5 を参照。

## 出力フォーマット (進化対象)

- 自分用 md: `<topic>.md` — 4 フェーズ章立て × 重要/付随の分離 (手段は基本「付随」側) + 未解決の問い。
- クライアント向け HTML: `<topic>__client-proposal.html` — 結論 → 根拠 → 提案 → 何をしてほしいか (Minto / SCQA)。「不足情報の可視化」セクション必須。
- 振り返り (モード c): `<date>__retrospective.md`。
- ファイル命名・章立て・粒度の詳細仕様は `references/output_formats.md`。

## 自己進化の範囲

- **進化対象 (使用ログから書き換えられる)**: `references/judgment_axes.md` / `references/phase_questions.md` / `references/output_formats.md` / `scripts/render_markdown.py` / `scripts/render_html.py`
- **進化対象外 (固定)**: `references/dialogue_style.md` (対話スタイル 3 原則) / 4 フェーズ構造と逆流ルール / `scripts/pipeline.py` (自己破壊防止)

## やってはいけないこと

- **全肯定する** / **選択肢を提示する** / **クローズ質問で終わる** (対話スタイル 3 原則違反)。
- F1 にいるのに手段の話を許容する / F3 を飛ばして F4 に進む。
- `scripts/pipeline.py` および `references/dialogue_style.md` を進化レビューで書き換える。
- 完了条件を空欄でサイクルを閉じる。
- ユーザー個別の好みを SKILL.md 本文に混ぜる (`references/user_preferences.md` に分離)。
- このスキルを **他人向けに汎用化する** (本人専用 — 想定ユーザーは 1 人だけ)。

## 参照ファイル

- `references/dialogue_style.md` — 対話スタイル 3 原則 (固定)
- `references/judgment_axes.md` — 課題 / 手段 / Done / 完了条件の判別基準 (進化対象)
- `references/phase_questions.md` — キラーフレーズ台帳と各フェーズの定型問いセット (進化対象)
- `references/output_formats.md` — md / HTML / 振り返りレポートの章立て仕様 (進化対象)
- `references/user_preferences.md` — ユーザー個別の好み (進化過程で蓄積)
- `references/pipeline_spec.md` — パイプライン仕様・完了条件セマンティクス
- `references/log_schema.md` — JSON Lines ログのフィールド定義
- `references/evolution_principles.md` — 自己進化の判断原則
