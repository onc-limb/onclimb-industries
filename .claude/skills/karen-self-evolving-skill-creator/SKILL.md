---
name: karen-self-evolving-skill-creator
description: Create new Claude skills that ship with a built-in self-evolution pipeline. Generated skills log every pipeline run (instruction, reasoning, output, feedback, completion state) into their own logs/ directory and rewrite their own SKILL.md / scripts when accumulated logs cross a configurable threshold (default 10 runs). Use whenever the user wants a skill that learns from usage — "adaptive", "self-improving", "auto-tuning", "self-evolving" — or describes a skill that should remember how it was used and improve itself. The meta-skill applies the same pipeline to itself, so improvements to scaffolding compound over time.
metadata:
  type: skill
  has_self_evolution_pipeline: true
  evolution_threshold_default: 10
---

# karen-self-evolving-skill-creator

このスキルは「**自己進化するスキル**」を生成するメタスキルです。生成されるスキル (以下、**子スキル**) は必ず以下を備えます。

1. **自己進化パイプライン** — 実行サイクルを構造化ログに残す。
2. **完了条件** — 各サイクルの結末を `success` / `failure` / `unknown` / `error` のいずれかに必ず分類する。
3. **進化トリガー** — パイプラインの累積実行回数がしきい値 (既定 10 回) を超えると、自分自身の `SKILL.md` ・ scripts ・ references を書き換えるレビューに入る。
4. **公共知識優先の改善方針** — ユーザー個別の好みより、論文 / 公開ベストプラクティス / 業界標準を優先して改善案を採用する。

このメタスキル自体も同じ仕組みで動き、`karen-self-evolving-skill-creator/logs/` に自分の履歴が溜まり、しきい値超過時には自身の SKILL.md やスクリプトを書き換えます。

## いつ呼び出すか

以下のいずれかに当てはまるとき、必ずこのスキルを使ってください。

- 「自己進化」「self-evolving」「adaptive」「auto-tuning」「self-improving」スキルを作って、と言われた
- 「使うほど賢くなるスキル」「フィードバックから学習するスキル」「学習履歴を残すスキル」を求められた
- 既存スキルに「ログ機能」「自己反省」「pipeline」「completion condition」を後付けしたい
- 「TODO や推測ログを構造化したスキル」「自分の振り返りを書くスキル」が欲しい

明示的に「self-evolving」と言われていなくても、上記の意図が読み取れたらこのスキルを呼び出します (undertriggering を避けるため、迷ったら呼ぶ)。

## ワークフロー全体像

```
[A] 子スキルを新規作成する場合
  1. ヒアリング (目的・トリガー・出力) + プレフィックス決定 (personas/<prefix>.md 参照)
  2. scaffold_skill.py で骨格を生成
  3. SKILL.md / scripts / references をユーザーと合意しながら肉付けし、
     自己進化パイプラインが組み込み済みであることを確認

[B] このメタスキルが使われた / 子スキルが実行されたとき (各実行毎)
  1. pipeline.py log-start でサイクル開始イベントを logs/ に追記
  2. 通常の作業を遂行し、完了条件を必ず判定して pipeline.py log-end で追記
  3. しきい値超過なら evolve.py review で進化レビューを起動

[C] 進化レビュー (自己進化)
  1. evolve.py review が logs/ を読み、改善提案を EVOLUTION.md に起草
  2. Claude が公的ベストプラクティスと突き合わせて採否を判断し、
     evolve.py snapshot → Edit → diff 保存の順に適用
  3. 適用結果を logs/ に「evolution イベント」として書き戻し、サイクルを閉じる
```

## 自己進化の定義

> 自己進化とは、**使われ方・フィードバック・与えられた指示** を構造化ログに記録し、「頻繁に発生し、かつ一般化可能だと判断できる改善」のみを自分の SKILL.md・scripts・references に反映する行為である。
> ユーザー個別の好みより、公開された論文・標準・ベストプラクティスを優先する。

判断ルール (詳細は `references/evolution_principles.md`):

- **頻度**: 同種の指摘・修正パターンが直近 N 回 (既定 N=3) のサイクル中で再発したら改善候補。
- **一般性**: 「他のプロジェクトでも妥当」と説明できるものだけ採用候補。この案件だけの話なら保留。
- **公共知識照合**: 採用候補は関連する標準・論文と矛盾しないか確認する。矛盾するなら不採用。
- **ユーザーの好み**は `references/user_preferences.md` に分離し、SKILL.md 本体の汎用ルールには混ぜない。

## 自己進化パイプライン

「1 サイクル」= 1 つの推論 → 行動 → 結果評価のループ。**単純タスクは 1 サイクルで閉じてよい**。アウトプットを自己検証できない場合のみ、1 ユーザー入力を複数サイクルに分割して精度を上げる。

各サイクルの開始・終了を `logs/pipeline.jsonl` (JSON Lines, append-only) に追記する。最低限のフィールドは `cycle_id` / `instruction` / `completion_state` / `completion_reason`。
全フィールド定義は `references/log_schema.md`、運用ルールの厳密仕様は `references/pipeline_spec.md` を参照。
大きな生成物は `logs/artifacts/<cycle_id>/` に保存し、パスだけを JSON に書く。

完了条件は `success` (達成基準を満たした) / `failure` (達成不可と確定) / `unknown` (達成判定不能) / `error` (例外・前提欠落) の 4 値。セマンティクスの詳細は `references/pipeline_spec.md` を参照。
`unknown` は次サイクルで解消するか、ユーザーへの確認質問を返して閉じてよい (その場合、追加サイクルの強制起動は不要)。

## 進化トリガーと頻度

- 既定: パイプラインを **10 回** (サイクル数; ユーザー入力数ではない) 回したら進化レビュー。
- 設定は `pipeline.config.json` で変更 (`evolution_threshold`、`recurrence_window`、`auto_apply` — 既定 `true`)。
- 自己進化自身も 1 サイクル扱いで logs に記録する。

`evolve.py review` は **提案の起草 (EVOLUTION.md への追記) まで** を行う。適用は Claude が `evolve.py snapshot` → Edit → diff 保存の順に行う。
`auto_apply=true` (既定) なら人手承認なしに適用してよい。ただし `scripts/pipeline.py` だけは自己破壊防止のため進化対象外。承認制にしたいときは `auto_apply` を `false` に変更する。

## ディレクトリ構造 (子スキルもメタスキル自身もこれに従う)

```
<prefix>-<skill-name>/
├── SKILL.md                  # 本体 (frontmatter に has_self_evolution_pipeline: true)
├── pipeline.config.json      # しきい値・自動適用フラグ
├── EVOLUTION.md              # 進化レビューの提案・適用履歴 (Append-only)
├── scripts/
│   ├── pipeline.py           # ログ追記・しきい値判定の薄いラッパ
│   └── (skill-specific)
├── references/
│   ├── user_preferences.md   # ユーザー固有の好み (分離)
│   └── (skill-specific)
└── logs/
    ├── pipeline.jsonl        # サイクルログ (JSON Lines)
    ├── artifacts/            # 大きい中間生成物
    └── evolutions/           # 進化レビュー時のスナップショット
```

## 子スキルを作るときの手順

1. **要件ヒアリング** — 目的・トリガー文・想定入出力・既存類似スキルの有無を確認。あわせて `.claude/skills/README.md` の一覧から分類プレフィックスを決め、**その分類の `personas/<prefix>.md` を必ず参照**して共通ルールに従う。
2. **`python scripts/scaffold_skill.py --name <prefix>-<skill-name> --dest <repo-root>/.claude/skills`** を実行 — 名前は既知プレフィックス始まりでないとエラーになる (`--allow-no-prefix` で例外的に回避可)。新規スキルは必ず `.claude/skills/` 配下に置くこと (詳細は `references/scaffold_usage.md`)。
3. 生成された `SKILL.md` の `description` を磨く。子スキルの description にも「自己進化を備える」旨を 1 文入れる。
4. ドメイン固有の `scripts/` `references/` を追加する。**ただし `scripts/pipeline.py` は削除・改変しない**。
5. `evals/evals.json` がある skill-creator フローを併用する場合は通常通りテストする。

子スキル側からの呼び出し例 (SKILL.md 本文に必ず織り込み、**完了条件を出さずに終わってはいけない** ことを明記する)。

```bash
# サイクル開始
python scripts/pipeline.py log-start \
  --skill-name <skill-name> \
  --instruction "<受けた指示の要約>"

# 終了 (completion_state は 4 値のいずれか)
python scripts/pipeline.py log-end \
  --skill-name <skill-name> \
  --cycle-id <ID> \
  --completion-state success \
  --completion-reason "ユーザー基準すべて満たしたため" \
  --output-summary "out/path/...md"
```

## 進化レビューの実行

```bash
python scripts/evolve.py review   # skill root は scripts/ の位置から自動解決
```

1. `logs/pipeline.jsonl` の直近 N 件 (既定 10) から再発する指摘・失敗パターンを抽出し、頻度 / 一般性 / 公共知識照合をパスする改善案だけを `EVOLUTION.md` に追記する (**起草までで、適用はしない**)。
2. 適用は Claude が行う: `evolve.py snapshot` でロールバック点を `logs/evolutions/<ts>/before/` に保存 → SKILL.md / scripts / references を Edit → 差分を `logs/evolutions/<ts>/diff.patch` に保存。`auto_apply=true` (既定) なら人手承認なしで適用してよい。
3. 進化サイクル自体を `pipeline.py log-end` (`--action evolve.py`) で記録して閉じる。

このメタスキル自身にも同じ手順を適用する。起動時に `log-start`、完了時 (子スキルの引き渡し or 中断) に `log-end` を必ず呼ぶこと。

## 参照ファイル

`references/` 配下: `pipeline_spec.md` (厳密仕様) / `log_schema.md` (ログのフィールド定義) / `evolution_principles.md` (進化の判断原則) / `scaffold_usage.md` (scaffold の使い方) / `user_preferences.md` (ユーザー個別の好み)。

## やってはいけないこと

- ログの後付け改ざん (JSON Lines は append-only; 修正は新行として追記)。
- ユーザー個別の好みを `SKILL.md` 本文の汎用ルールに混ぜる。
- 進化レビューで `scripts/pipeline.py` を破壊的に書き換える (自己破壊回避; 変更は別ファイル化か関数追加で対処)。
- 完了条件を空欄のままサイクルを閉じる (必ず 4 値のいずれか)。
