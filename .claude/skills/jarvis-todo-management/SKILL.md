---
name: jarvis-todo-management
description: プロジェクト別タスク台帳（todo-data/todos.json）を単一の真実として運用するイベント駆動の ToDo 管理スキル(jarvis 系)。時間駆動のチェックインは行わず、(1)登録と 30〜60 分単位への分割、(2)作業の区切りでの台帳突き合わせ（該当 ToDo が無ければ source 付きで自動記載 + 一言通知）、(3)worklog digest・giziroku 議事録・調査/壁打ちからの ToDo 収穫（inbox 行き）、(4)オンデマンド棚卸し（inbox 消化・stale 検知・分割提案・着手順提案）、(5)Google Tasks への push 同期（プロジェクト = 1 リスト、自作 MCP サーバー経由）を担う。「ToDo 追加」「タスク登録して」「このタスク分割して」「ToDo 整理して」「棚卸しして」「これどの ToDo の作業だっけ」「議事録から ToDo 拾って」「Google Tasks に同期して」等で起動。事実の記録（完了・作業実績の追記)は自動 + 毎回一言通知、意図の決定（廃棄・優先度・分割確定・inbox 昇格）は提案してユーザーが確定する。自己進化パイプラインを備え、分割粒度・突き合わせマッチング・収穫の抽出ルールが使用ログから磨かれる。読み手は自分自身の一次記録であり、他者向け報告の清書は friday 系の責務。
model: sonnet
metadata:
  type: skill
  data_dir: <repo>/todo-data
  has_self_evolution_pipeline: true
  evolution_threshold_default: 10
  design_doc: docs/todo-management-redesign-2026-07-02.md
---

# jarvis-todo-management

> **プロジェクト別のタスク台帳を単一の真実とし、「作業したら突き合わせる」「他スキルの出力から収穫する」
> イベント駆動で ToDo を取りこぼさない管理スキル。**
> 読み手は自分自身 (jarvis 系の一次記録)。他者向けの清書はしない。
> 設計の背景・スキーマ定義は [docs/todo-management-redesign-2026-07-02.md](../../../docs/todo-management-redesign-2026-07-02.md) を正とする。

このスキルは **自己進化** を備えています。

- 各サイクルを `logs/pipeline.jsonl` に記録する。
- 完了条件は `success` / `failure` / `unknown` / `error` のいずれかを必ず付与する。
- `pipeline.config.json` の `evolution_threshold` (既定 10) 回サイクルを回したら、`scripts/evolve.py review` を実行し `EVOLUTION.md` に提案を追記、`auto_apply=true` なので自動適用される。

---

## 原則: 事実は自動、意図は提案

- **事実の記録は自動でよい** — 「この作業をやった」という追記・完了マーク・進行中への更新は、
  `source` タグ付きで自動実行し、**毎回チャットで一言通知**する
  （例: 「ToDo に自動追記しました: t-20260702-005 ○○ (source: session)」）。
- **意図の決定は提案制** — 廃棄 (drop)・優先度・分割案の確定・inbox からの昇格は、
  提案してユーザーの確定を待つ。
- 自動収穫・自動記載された未確定タスクは **`inbox`** ステータスに入れる。
  勝手に記載はするが、勝手にコミットメント (todo) にはしない。

---

## データ配置

運用データはリポジトリ直下の `todo-data/` (git 管理外)。環境変数 `TODO_DATA` で上書き可。

```
todo-data/
  todos.json          # タスク台帳 (現在状態・単一の真実。schema_version: 1)
  events.jsonl        # 全変更の追記ログ (原料保全。削除・書き換え禁止)
  google_lists.json   # プロジェクト → Google Tasks リスト ID のキャッシュ (同期時に生成)
```

- 読み書きは必ず `scripts/todo.py` 経由で行う (todos.json を直接編集しない)。
- タスクは削除せず `dropped` にする。`events.jsonl` は追記のみ。
- ダッシュボード等の外部ツールは todos.json / events.jsonl を読み取り専用で参照する前提のため、
  スキーマ変更は設計 doc の schema_version 昇格でのみ行う。

### ステータス

`inbox` (収穫直後・未確定) / `todo` / `in_progress` / `done` / `dropped` (削除の代替。理由を note に残す)

---

## トリガー

| 種別 | 発話例 | 動作 |
|---|---|---|
| **登録** | 「ToDo 追加」「タスク登録して」「あとで〜やる」 | フロー A |
| **分割** | 「このタスク分割して」「着手できる単位にして」 | フロー B |
| **突き合わせ** | 作業の区切り (CLAUDE.md ルールから自動) /「これどの ToDo の作業だっけ」 | フロー C |
| **棚卸し** | 「ToDo 整理して」「棚卸しして」「いま何が残ってる?」 | フロー D |
| **同期** | 「Google Tasks に同期して」/ 棚卸しの最後 | フロー E |
| **収穫** | worklog / giziroku の SKILL.md 末尾ステップから /「議事録から ToDo 拾って」 | フロー F |

定時チェックインは行わない (時間駆動は廃止。すべてイベント駆動・オンデマンド)。

---

## 起動時の手順 (毎サイクル必須)

### Step 0. パイプライン開始

```bash
CYCLE_ID=$(python3 scripts/pipeline.py --skill-root <このスキルのルート> log-start \
  --skill-name jarvis-todo-management \
  --instruction "<受け取った指示の要約 (機密マスク済み)>")
```

### Step 1. 該当フローの実行 (下記 A〜F)

### Step 2. パイプライン終了

```bash
python3 scripts/pipeline.py --skill-root <このスキルのルート> log-end \
  --skill-name jarvis-todo-management \
  --cycle-id "$CYCLE_ID" \
  --completion-state success \
  --completion-reason "<根拠>" \
  --output-summary "todo-data/todos.json 更新 (t-... 追加/完了 など)"
```

**完了条件を出さずにサイクルを閉じてはいけない。** `log-end` の戻り JSON が `"evolution_due": true` なら `python3 scripts/evolve.py review` を実行する。

- **success** — フローを完了し、台帳更新とチャットでの結果提示まで終えた。
- **failure** — ユーザーの意図を満たせず終了 (原因特定済み)。
- **unknown** — 出力したが inbox 昇格・分割案などの確定待ち。
- **error** — スクリプト失敗・todo-data 書き込み不能など。

---

## フロー A: 登録

1. project を確定する。会話の文脈・カレントディレクトリから推定し、
   `jarvis-worklog/config/projects.yaml` の project id 語彙で追認を得る (不明なら `_unclassified`)。
2. `todo.py add --title ... --project ... --estimate ...` で登録する。
3. **30〜60 分で終わらなさそうなタスクは分割を提案する** (フロー B)。見積が語られなかったら
   軽く聞き、答えが無ければ見積なしで登録してよい (棚卸しで拾う)。
4. ユーザー発話からの「あとでやる」「〜しないと」の拾い上げは `--status inbox` で自動追記し、一言通知する。

## フロー B: 分割

1. 対象タスクを「それぞれ完結して検証可能、着手順、各 30〜60 分」のサブタスク案に割る。
2. 案をユーザーに提示し、**確定を得てから** `todo.py split <id> --sub "title|est" ...` を実行する。
3. 親タスクは残り、全サブタスク完了時に自動で done になる (その旨も通知される)。

## フロー C: 突き合わせ (reconcile)

作業の区切りで呼ばれる中核フロー。ルート CLAUDE.md のルールからも起動される。

1. `todo.py list` で開いているタスクを読み、いま終えた/進めた作業と意味的に一致するものを探す。
   手がかりは project (作業ディレクトリ) → タイトルの意味一致の順で確実なものを優先する。
2. **一致あり**: 事実として `start` / `done` を実行し、一言通知する。
3. **一致なし**: `todo.py add --source-type session --source-ref <会話や成果物の参照> --status done`
   (完了済み作業) または `--status inbox` (やりかけ・派生タスク) で自動追記し、一言通知する。
4. 判断に迷う一致 (どのタスクの作業か曖昧) は勝手にマークせず、一言で確認する。

## フロー D: 棚卸し (オンデマンドのみ)

1. **inbox 消化** — `list --status inbox` を提示し、昇格 (`promote` で project・見積を付ける) /
   `drop` をユーザーが確定する。
2. **stale 検知** — `in_progress` のまま updated_at が古いタスク・inbox 滞留を**質問形式で**確認する。
   「詰まっている」と断定しない。ユーザーが「問題ない」と答えたら深追いしない。
3. **分割提案** — 見積なし・60 分超のタスクにフロー B を提案する。
4. **着手順の提案** — due・project・見積から直近の順序を提案する (決定はユーザー)。
5. 最後にフロー E (同期) を実行する。

## フロー E: Google Tasks 同期 (push 一方向)

内部台帳が単一の真実。Google 側は表示用のミラー。

1. `todo.py list --dirty --all` で未同期タスクを列挙する。**inbox は同期しない**。
2. 自作 MCP サーバー (`mcp-servers/google-tasks/`) のツールで反映する:
   - project に対応するリストが無ければ `create_tasklist` で作成し、`todo-data/google_lists.json` に記録する。
   - `google.task_id` が無いタスクは `create_task`、あるタスクは `update_task` (done は status: completed)。
   - dropped で task_id ありは Google 側を completed 扱いにする (削除はしない)。
3. 成功ごとに `todo.py sync-mark <id> --google-task-id <gid>` で dirty を落とす。
4. MCP ツールが見つからない (未接続) 場合は同期をスキップし、dirty のまま残る旨を一言伝える。エラー扱いにしない。

## フロー F: 収穫 (harvest)

他スキル・調査からの取り込み。**すべて inbox 行き**が基本 (確定は棚卸しで)。

| 発生源 | 取り込み |
|---|---|
| worklog digest の「次にやること」「判断待ち」 | `--source-type worklog --source-ref <digest パス>` で自動追記 + 一言通知 |
| giziroku の TODO (自分担当分のみ) | 候補を提示し確認のうえ `--source-type giziroku --source-ref <議事録パス>`。**他人の TODO は入れない** |
| 調査・壁打ちの結論 | 会話の区切りで「これ ToDo にしますか」と候補提示 → 採用分を `--source-type research` |

---

## スクリプト

すべて python3 標準ライブラリのみ。`TODO_DATA` でデータ置き場を上書きできる。

| コマンド | 役割 |
|---|---|
| `todo.py add` | 登録。`--status inbox/done`、`--source-type`、`--source-ref` で収穫・事実記録に対応 |
| `todo.py split <id> --sub "title\|est"` | 30〜60 分単位のサブタスク化 (`parent_id` 紐づけ) |
| `todo.py start / done / drop / promote` | 状態遷移。done は親の自動完了チェック付き。drop は `--reason` 必須 |
| `todo.py edit / note` | 項目修正 / 経緯メモ (ゴール変更等) の events 記録 |
| `todo.py list` | `--status` `--project` `--dirty` `--all` `--json` で絞り込み |
| `todo.py sync-mark <id>` | Google push 成功の記録 (dirty クリア) |
| `pipeline.py` | 自己進化パイプラインのロガー (規約標準・改変禁止) |
| `evolve.py` | 進化レビュー (規約標準) |

---

## 自己進化の範囲

**進化対象 (使用ログから書き換えられる)**

- 分割粒度 — 30〜60 分判定の精度、サブタスクの切り方
- 突き合わせマッチング — 作業とタスクの一致判定の手がかり・優先順位
- 収穫の抽出ルール — digest / 議事録 / 会話から何を候補にするか
- 聞き方 — 棚卸し・stale 確認の問いの量・トーン

**進化対象外 (固定)**

- 「事実は自動 + 一言通知、意図は提案」の原則
- todos.json のスキーマ (変更は設計 doc の schema_version 昇格でのみ)
- 内部台帳が単一の真実 (Google 側を真実にしない)
- `scripts/pipeline.py` (自己破壊防止)
- ユーザー個別の好みは `references/user_preferences.md` に分離し、SKILL.md 本文に混ぜない

---

## 品質・安全性 (jarvis persona 準拠)

- **生ログ保全** — events.jsonl は追記のみ。タスクは削除せず dropped。todo-data/ 配下を消さない。
- **機密マスキング** — API キー・トークン・顧客名等はタスクにもパイプラインログにも書かない。
  Google Tasks に出るタイトルは特に注意 (外部サービスへの送信になる)。
- **推測の明示** — project 推定・突き合わせの一致判断など推測した箇所は明示する。
  コード内は `# ASSUMPTION:`、サイクルログは `--assumption-note`。
- 応答・出力は日本語、コード・識別子は英語。技術用語は原語のまま。

---

## やってはいけないこと

- ユーザーの確定なしに drop・inbox 昇格・分割を確定する (自動でよいのは事実の記録のみ)。
- 自動記載したのに通知を省く (毎回一言通知する)。
- todos.json を `todo.py` を通さず直接編集する。events.jsonl・過去タスクを削除する。
- inbox のタスクを Google Tasks に同期する。他人の TODO を台帳に入れる。
- stale 検知を断定口調で伝える。
- 完了条件を空欄のままサイクルを閉じる。`scripts/pipeline.py` を進化レビューで書き換える。
- 他者向けの清書・報告資料をこのスキルで作る (それは friday 系の責務)。
