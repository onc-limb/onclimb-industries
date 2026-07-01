# `logs/pipeline.jsonl` スキーマ

JSON Lines: 1 行 1 JSON オブジェクト。`event` で種別を区別。

## 共通フィールド

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `event` | string | yes | `start` / `end` / `amend` / `note` のいずれか |
| `cycle_id` | string | yes | `YYYYMMDDTHHMMSSZ-<rand4>` |
| `skill_name` | string | yes | スキル名 (kebab-case) |

## `event=start`

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `parent_cycle_id` | string \| null | yes | 同一 user_turn での前段サイクル |
| `started_at` | string (ISO8601 UTC) | yes | |
| `instruction` | string | yes | 指示要約 (PII マスク済み) |
| `context_hash` | string | no | 入力ハッシュ (再現性確認用) |

## `event=end`

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `ended_at` | string (ISO8601 UTC) | yes | |
| `reasoning_summary` | string | yes | 推論要約 (<=300 字推奨) |
| `actions` | array of {tool, target?, note?} | yes | 行為ログ。空配列可 |
| `output_summary` | string | yes | アウトプット要約 |
| `followup_feedback` | string \| null | yes | サイクル後のユーザー追記 |
| `completion_state` | enum | yes | `success` / `failure` / `unknown` / `error` |
| `completion_reason` | string | yes | 完了条件を選んだ根拠 |
| `assumption_notes` | array of string | yes | 推測した箇所の要約 (ログ内のみに保持) |

## `event=amend`

過去エントリの誤りを訂正するときに使う (`pipeline.jsonl` は append-only なので過去行を直接書き換えない)。

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `amended_at` | string | yes | |
| `target_cycle_id` | string | yes | 訂正対象のサイクル ID |
| `patch` | object | yes | 上書きしたいキーと新値 |
| `reason` | string | yes | 訂正理由 |

## `event=note`

サイクルに属さない情報 (例: 設定変更、外部イベント) を記録する。

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `noted_at` | string | yes | |
| `note` | string | yes | 自由記述 |
| `category` | string | no | `config-change` / `external` / `manual` など |

## バリデーション

`scripts/pipeline.py validate` で次を検証:

- `event=start` と `event=end` が `cycle_id` でペアになっている
- `event=end` の `completion_state` が 4 値のいずれか
- ISO8601 形式の `started_at` / `ended_at`
- JSON 構文エラー行の検出

エラー行は破損として `logs/pipeline.broken.jsonl` に隔離される。
