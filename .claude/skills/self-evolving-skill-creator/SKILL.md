---
name: self-evolving-skill-creator
description: Create new Claude skills that ship with a built-in self-evolution pipeline. Every generated skill records each pipeline run (instruction, reasoning trace, output, follow-up feedback, completion state) into its own logs/ directory, and rewrites its own SKILL.md / scripts when accumulated logs cross a configurable threshold (default 10 pipeline runs). Use this skill whenever the user wants to build a skill that learns from usage, adapts SKILL.md to feedback, keeps a structured execution log, or asks for an "adaptive", "self-improving", "auto-tuning", or "self-evolving" skill — even when the user does not name those exact terms but describes a skill that should remember how it was used and improve itself. The meta-skill applies the same pipeline to itself, so improvements to scaffolding compound over time.
metadata:
  type: skill
  has_self_evolution_pipeline: true
  evolution_threshold_default: 10
---

# self-evolving-skill-creator

このスキルは「**自己進化するスキル**」を生成するメタスキルです。生成されるスキル (以下、**子スキル**) は必ず以下を備えます。

1. **自己進化パイプライン** — 1 回の実行サイクル (1 ユーザー入力で複数回まわすことを想定) を構造化ログに残す。
2. **完了条件** — 各サイクルの結末を `success` / `failure` / `unknown` / `error` のいずれかに必ず分類する。
3. **進化トリガー** — パイプラインの累積実行回数がしきい値 (既定 10 回) を超えると、自分自身の `SKILL.md` ・ scripts ・ references を書き換えるレビューに入る。
4. **公共知識優先の改善方針** — ユーザー個別の好みより、論文 / 公開ベストプラクティス / 業界標準を優先して改善案を採用する。

このメタスキル自体も同じ仕組みで動くため、`self-evolving-skill-creator/logs/` には自分のパイプライン履歴が溜まり、しきい値超過時には自身の SKILL.md やスクリプトを書き換えます。

---

## いつ呼び出すか

以下のいずれかに当てはまるとき、必ずこのスキルを使ってください。

- 「自己進化」「self-evolving」「adaptive」「auto-tuning」「self-improving」スキルを作って、と言われた
- 「使うほど賢くなるスキル」「フィードバックから学習するスキル」「学習履歴を残すスキル」を求められた
- 既存スキルに「ログ機能」「自己反省」「pipeline」「completion condition」を後付けしたい
- 「TODO や推測ログを構造化したスキル」「自分の振り返りを書くスキル」が欲しい

明示的に「self-evolving」と言われていなくても、上記の意図が読み取れたらこのスキルを呼び出します (undertriggering を避けるため、迷ったら呼ぶ)。

---

## ワークフロー全体像

```
[A] 子スキルを新規作成する場合
  1. ヒアリング (子スキルの目的・トリガー・出力)
  2. scaffold_skill.py で骨格を生成
  3. SKILL.md / scripts / references をユーザーと合意しながら肉付け
  4. 自己進化パイプラインを組み込み済みであることを確認
  5. README で運用方法 (ログ位置、進化発動条件) を子スキル利用者に伝える

[B] このメタスキルが使われた / 子スキルが実行されたとき (各実行毎)
  1. pipeline.py log-start でサイクル開始イベントを logs/ に追記
  2. 推論・ツール呼び出し・アウトプットを通常通り遂行
  3. 完了条件 (success/failure/unknown/error) を必ず判定
  4. pipeline.py log-end でサイクル終了イベントを追記
  5. しきい値超過なら evolve.py review で進化レビューを起動

[C] 進化レビュー (自己進化)
  1. logs/ を読み、頻度 × 一般性 で改善候補を抽出
  2. 公的ベストプラクティス (論文・標準) と突き合わせる
  3. 差分案を EVOLUTION.md に提案として記録
  4. ユーザー承認またはオートモード設定で SKILL.md / scripts を書き換え
  5. 適用結果を logs/ に「evolution イベント」として書き戻し、サイクルを閉じる
```

各ステップの詳細は本ファイルと `references/` に進行的に記載します。

---

## 自己進化の定義 (このスキルにおける確定定義)

> 自己進化とは、**使われ方・フィードバック・与えられた指示** を構造化ログに記録し、
> 「頻繁に発生し、かつ一般化可能だと判断できる改善」 のみを自分の SKILL.md・scripts・references に反映する行為である。
> ユーザー個別の好みより、公開された論文・標準・ベストプラクティスを優先する。

判断ルール:

- 「**頻度**」しきい値: 同種の指摘 / 同種の修正パターンが直近 N 回 (既定 N=3) のサイクル中で再発したら改善候補。
- 「**一般性**」判定: その改善が「このユーザーのこの案件だけに当てはまる」のなら **保留**。「他のプロジェクトでも妥当」と説明できるなら **採用候補**。
- 「**公共知識照合**」: 採用候補は、関連する標準や論文 (例: タスク管理なら GTD、Kanban、IEEE 1074、ISO/IEC/IEEE 24765 ; 開発手法なら『Accelerate』『The DevOps Handbook』『A Philosophy of Software Design』、関連する arXiv のメタプロンプティング系論文) と矛盾しないかを確認する。矛盾するなら採用しない。
- 「**ユーザーの好み**」は専用セクション `references/user_preferences.md` に分離して反映する。SKILL.md 本体の汎用ルールには混ぜない。

詳細な進化原則は `references/evolution_principles.md` を参照。

---

## 自己進化パイプライン (Self-Evolution Pipeline)

### 1 サイクルの単位

「1 サイクル」 = 1 つの推論 → 行動 → 結果評価のループ。
**1 ユーザー入力 = 1 サイクル ではありません**。1 入力につき複数サイクル回して精度を上げてからユーザーに最終応答を返してください。

### 必須記録項目

各サイクルで次を `logs/pipeline.jsonl` (JSON Lines) に追記します。

| フィールド | 内容 |
|---|---|
| `cycle_id` | サイクル一意 ID (`YYYYMMDDTHHMMSSZ-<rand4>`) |
| `parent_cycle_id` | 同一ユーザー入力内で前段のサイクル ID (なければ null) |
| `skill_name` | 対象スキル名 |
| `started_at` / `ended_at` | ISO8601 UTC |
| `instruction` | 受け取った指示の要約 (個人情報・機密はマスク) |
| `reasoning_summary` | 推論の要点 (300 字以内) |
| `actions` | 使ったツール・呼んだスクリプトなどの配列 |
| `output_summary` | アウトプットの要約 (実物のパスを併記) |
| `followup_feedback` | サイクル後にユーザーから来た追加指示・評価 (なければ null) |
| `completion_state` | `success` / `failure` / `unknown` / `error` |
| `completion_reason` | 上記を選んだ根拠 |
| `assumption_notes` | 推測で進めた箇所のリスト (ログ内のみに保持; 別ファイルには出さない) |

スキーマの厳密版は `references/log_schema.md` を参照。

### 完了条件 4 値の意味

- **success** — 受け取った指示の達成基準を満たし、ユーザー追加指示なしでも提供可能。
- **failure** — 指示を満たせなかったことが分かっており、原因も特定済み。
- **unknown** — アウトプットは出したが、達成基準を満たしているか判定不能 (要追加情報)。
- **error** — 例外・ツール失敗・前提条件欠落で完遂できなかった。

`unknown` を返すサイクルは、必ず次サイクルか質問で解消すること。`error` は同サイクル内では復旧せず、新サイクルで対処する。

### 何を申告するか (Pipeline の生贄)

`instruction → reasoning → output → followup → completion` の 5 つを 1 行 JSON で残します。
過剰な詳細はノイズになるため、要約と参照パスで構成し、本体生成物 (大きなファイル等) は `logs/artifacts/<cycle_id>/` に保存してパスだけ JSON に書きます。

---

## 進化トリガーと頻度

- 既定: パイプラインを **10 回** 回したら進化レビュー。
- カウント対象: **サイクル数** (ユーザー入力数ではない)。
- 設定変更は `pipeline.config.json` の `evolution_threshold` を編集。
- 自己進化自身も 1 サイクル扱いで logs に記録する。

`pipeline.config.json` 既定値:

```json
{
  "evolution_threshold": 10,
  "completion_states": ["success", "failure", "unknown", "error"],
  "recurrence_window": 3,
  "auto_apply": true
}
```

このリポジトリの既定は `auto_apply=true` で、進化レビューは人手承認なしに `SKILL.md` / `references/` / ドメイン固有 `scripts/` を書き換えます (ロールバック用スナップショットは `logs/evolutions/<ts>/before/` に保存)。
ただし `scripts/pipeline.py` だけは自己破壊防止のため自動進化の対象外。明示的に承認制に戻したいときだけ `pipeline.config.json` の `auto_apply` を `false` に変更してください。

---

## ディレクトリ構造 (生成される子スキルもメタスキル自身もこれに従う)

```
<skill-name>/
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

子スキル生成時には `scripts/scaffold_skill.py` がこのレイアウトを自動で組み立てます。

---

## 子スキルを作るときの手順

1. **要件ヒアリング** — 目的・トリガー文・想定入出力・既存類似スキルの有無を確認。
2. **`python scripts/scaffold_skill.py --name <kebab-name> --dest <repo-root>/.claude/skills`** を実行 — 新規スキルは必ず `.claude/skills/` 配下に置くこと。Claude Code がこの場所を自動スキャンするので再起動後すぐ利用可能になる (詳細は `references/scaffold_usage.md`)。
3. 生成された `SKILL.md` の `description` を磨く。子スキルの description にも「自己進化を備える」旨を 1 文入れる。
4. ドメイン固有の `scripts/` `references/` を追加する。**ただし `scripts/pipeline.py` は削除・改変しない**。
5. `evals/evals.json` がある skill-creator フローを併用する場合は通常通りテストする。

子スキル側からの呼び出し例 (SKILL.md 本文に必ず含める)。

```bash
# サイクル開始
python scripts/pipeline.py log-start \
  --skill-name <skill-name> \
  --instruction "<受けた指示の要約>"

# 終了 (completion_state は 4 値のいずれか)
python scripts/pipeline.py log-end \
  --cycle-id <ID> \
  --completion-state success \
  --completion-reason "ユーザー基準すべて満たしたため" \
  --output-summary "out/path/...md"
```

子スキルの SKILL.md 本文には、上記の呼び出しをスキル内のステップに必ず織り込み、**完了条件を出さずに終わってはいけない** ことを明記すること。

---

## 進化レビューの実行

```bash
python scripts/evolve.py review --skill-path .
```

このコマンドは:

1. `logs/pipeline.jsonl` をスキャン。
2. 直近 N 件 (既定 10) の中から、再発する指摘 / 失敗パターン / 追加指示を抽出。
3. 「頻度しきい値」「一般性しきい値」「公共知識照合」をパスする改善案だけを `EVOLUTION.md` に追記。
4. `auto_apply=true` (このリポジトリの既定) の場合、`scripts/pipeline.py` 以外の差分を自動適用。適用前スナップショットは `logs/evolutions/<ts>/before/`、差分は `diff.patch` に保存。
5. 進化サイクル自体を `logs/pipeline.jsonl` に `actions=["evolution-review"]` として書き戻す。

---

## このスキル自身の自己進化 (メタ適用)

このメタスキルを起動したサイクルも `self-evolving-skill-creator/logs/pipeline.jsonl` に記録します。
ユーザーが「新しい自己進化スキルを作って」と言った瞬間に `log-start` し、完了時 (子スキルの引き渡し or 中断) に `log-end` を必ず呼ぶこと。
進化トリガーが発火したら、本ファイル (SKILL.md) や `scripts/scaffold_skill.py` を改善対象として進化レビューを行います。

---

## 参照ファイル

- `references/pipeline_spec.md` — パイプラインと完了条件の厳密仕様
- `references/log_schema.md` — JSON Lines ログのフィールド定義
- `references/evolution_principles.md` — 自己進化の判断原則と参照すべき公共知識
- `references/scaffold_usage.md` — `scaffold_skill.py` の使い方
- `references/user_preferences.md` — ユーザー個別の好み (進化過程で蓄積される)

---

## やってはいけないこと

- ログの後付け改ざん (JSON Lines は append-only; 修正は新行として追記)。
- ユーザー個別の好みを `SKILL.md` 本文の汎用ルールに混ぜる。
- 進化レビューで `scripts/pipeline.py` を破壊的に書き換える (自己破壊回避; 変更は別ファイル化か関数追加で対処)。
- 完了条件を空欄のままサイクルを閉じる (必ず 4 値のいずれか)。
