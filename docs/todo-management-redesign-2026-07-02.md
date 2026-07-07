# jarvis-todo-management 再設計 — チェックイン型からタスク台帳型へ

作成日: 2026-07-02
ステータス: Phase 1〜4 実装済み（2026-07-02）。Phase 4 の利用開始には GCP 側の OAuth
クライアント作成 + `mcp-servers/google-tasks/README.md` のセットアップが必要。
Phase 5（ダッシュボード）は本ドキュメント §3.2 のスキーマを正として別プロジェクト側で開発
対象: `.claude/skills/jarvis-todo-management/`

## 1. 背景と課題

現行の jarvis-todo-management は「約 2 時間おきのチェックイン対話で 1 日の todo を棚卸しする」
時間駆動のジャーナル型スキルとして設計された。しかし他の jarvis / friday 系スキルと毛色が違い、
実際に一度も使われないまま今日に至っている（`logs/pipeline.jsonl` 0 行、`journal/` 未作成）。

使われない理由は運用モデルにある:

- **時間駆動が実態に合わない**。2 時間おきに手を止めてチェックイン対話をする習慣は発生しない。
  実際の困りごとは「ToDo を作らずに作業してしまう」「何が ToDo だったか忘れる」であり、
  定時の棚卸しではなくイベント（作業した・会議した・調べた）に紐づけて拾う必要がある。
- **日付単位のジャーナルがタスクの実態と合わない**。タスクはプロジェクトに属し日をまたぐ。
  日次の todo.md / report.md では繰越の手作業が発生し、プロジェクト横断の見通しが持てない。
- **外部から見えない**。Markdown ジャーナルはこのリポジトリの中でしか読めず、
  スマホの Google ToDo や開発中の個人ダッシュボードから参照できない。

移行すべきデータが無いため、互換性を持たせず全面的に再設計する。

## 2. 再設計のコンセプト

> **プロジェクト別のタスク台帳（JSON）を単一の真実とし、
> 「作業をしたら台帳と突き合わせる」「他スキルの出力から ToDo を収穫する」という
> イベント駆動でタスクを取りこぼさない。外部（Google Tasks・ダッシュボード）へは台帳から同期する。**

解決したい行動パターン（ユーザー要望の言い換え）:

1. ToDo を作成せずに作業してしまう → **作業の区切りで台帳と突き合わせ、無ければ自動で記載する**
2. 何が ToDo だったか忘れる → **調査・壁打ち・worklog・議事録から ToDo になりうるものを収穫して台帳に入れる**
3. タスクが大きすぎて着手できない → **30 分〜1 時間で終わる単位への分割を支援する**
4. リポジトリの外で見えない → **Google Tasks へ同期し、ダッシュボードが読める安定スキーマで持つ**

### 「スキルは提案、確定はユーザー」原則の再定義

現行スキルは全操作をユーザー確定制にしていたが、「勝手に記載してほしい」という要望と衝突する。
次のように線を引き直す:

- **事実の記録は自動でよい** — 「この作業をやった」という事実の追記・完了マーク・進行中への更新は、
  `source` タグと一言通知付きで自動実行する（jarvis 系＝一次記録の思想。事実は確認を待たない）。
- **意図の決定は提案制のまま** — 廃棄（drop）、優先度変更、分割案の確定、収穫候補の採用は提案して確定を待つ。
- 両者の間に **`inbox` ステータス**を置く。自動収穫されたものはまず inbox に入り、
  棚卸しでユーザーが todo に昇格 / drop する。「勝手に記載するが、勝手にコミットメントにしない」。

## 3. データ設計

### 3.1 配置

```
todo-data/                 # git 管理外（.gitignore の /journal/ エントリを置き換え）
  todos.json               # タスク台帳（現在状態のスナップショット。単一の真実）
  events.jsonl             # 全変更の追記ログ（原料保全・ダッシュボードのタイムライン用）
```

- ベースディレクトリは環境変数 `TODO_DATA` で上書き可（既定はリポジトリ直下 `todo-data/`）。
- `events.jsonl` は追記のみ。`todos.json` は todo.py 経由でのみ書き換える（手編集しない）。
- jarvis 原則の「生ログ保全」は events.jsonl が担う。todos.json のタスクは削除せず
  `dropped` ステータスで残す。

### 3.2 todos.json スキーマ（schema_version: 1）

```json
{
  "schema_version": 1,
  "updated_at": "2026-07-02T14:30:00+09:00",
  "tasks": [
    {
      "id": "t-20260702-001",
      "project": "onclimb-industries",
      "title": "todo-management スキルの再設計を実装する",
      "description": "設計 doc: docs/todo-management-redesign-2026-07-02.md",
      "status": "todo",
      "estimate_min": 60,
      "parent_id": null,
      "due": null,
      "source": { "type": "user", "ref": null },
      "created_at": "2026-07-02T14:30:00+09:00",
      "updated_at": "2026-07-02T14:30:00+09:00",
      "started_at": null,
      "completed_at": null,
      "google": { "task_id": null, "synced_at": null, "dirty": true },
      "note": null
    }
  ]
}
```

- **status**: `inbox` / `todo` / `in_progress` / `done` / `dropped` の 5 値。
  - `inbox`: 収穫・自動記載で入った未確定タスク。棚卸しで昇格 or drop。
  - `dropped` は削除の代替。理由を `note` に残す。
- **project**: `jarvis-worklog/config/projects.yaml` の project id と同じ語彙を使う
  （worklog との突き合わせを機械的にするため）。該当なしは `_unclassified`。
- **estimate_min**: 30〜60 を目標粒度とする。それを超える見込みのタスクは親タスクとして残し
  サブタスクに分割する（`parent_id` で紐づけ）。親タスクは全サブタスク完了時に done。
- **source.type**: `user` / `session`（作業突き合わせでの自動記載）/ `worklog` / `giziroku` /
  `research`（調査・壁打ち）。`ref` に根拠のファイルパス等を入れる（後から出所を追える）。
- **google.dirty**: 内部変更があり Google Tasks へ未反映であることを示す同期フラグ。

### 3.2.1 schema_version 2 — `priority` フィールドの追加（2026-07-05）

jarvis-todo-prioritizer 連携のため、タスクに任意の `priority` オブジェクトを追加する。
**追加のみの変更**（v1 の台帳はそのまま読め、次回保存時に version 表記が 2 になる）。

```json
"priority": {
  "impact": 4,
  "urgency": 2,
  "rationale": "根拠となる事実 + ユーザー合意の要点（1〜2 文）",
  "assessed_at": "2026-07-05T14:00:00+09:00"
}
```

- **impact / urgency**: 1〜5。尺度は `jarvis-todo-prioritizer/references/assessment-rubric.md` に固定。
- 未評価タスクは `null`。並べ替えは `todo.py list --sort priority`（score = impact × urgency、
  未評価は末尾）。
- **書き手は `todo.py prioritize` のみ**（評価の運用は jarvis-todo-prioritizer が担う）。
  優先度は「意図の決定」なので、ユーザー確定後にのみ記録する。
- priority は Google Tasks に同期しない（dirty を立てない。内部の判断材料）。

### 3.3 events.jsonl

1 行 1 イベント。`{"ts", "task_id", "event", "detail"}`。
event は `created` / `status_changed` / `split` / `edited` / `synced` / `note` / `prioritized`。
現行 memo.md が担っていた「ゴール変更・計画変更の経緯」は `note` イベントで残す。
started_at / completed_at のタイムスタンプ差から、見積と実績の乖離を後から集計できる
（日次 report.md での手動記録は廃止）。

## 4. 機能設計

### 4.1 登録と分割

- 「ToDo 追加」等で登録。登録時に project を確認（会話の文脈・カレントディレクトリから推定し追認を得る）。
- 登録・棚卸しの際、**30〜60 分で終わらなさそうなタスクは分割を提案する**。
  分割案は「着手順に並んだ、それぞれ完結して検証可能なサブタスク」として提示し、確定はユーザー。
- 分割の粒度判断は自己進化の対象（実績データが貯まったら閾値・切り方を磨く）。

### 4.2 作業突き合わせ（reconcile）— 本再設計の中核

「ToDo を作らずに作業してしまう」対策。**2 層構え**にする。

**Layer 1: セッション内のリアルタイム突き合わせ（ベストエフォート）**

ルート CLAUDE.md に次のルールを追記する（スキル起動に依存せず全セッションで効かせる）:

> まとまった作業（スキル実行・実装・調査など）の区切りで `todo-data/todos.json` を確認し、
> - 対応するタスクがあれば status を更新する（in_progress / done — 事実の記録なので自動、通知のみ）
> - 無ければ `source: session` でタスクを自動追記し（完了済み作業は status: done で）、一言通知する

会話のついでに実行できる軽さが必要なので、判定は「todos.json を読んでタイトル・project の
意味的な一致を見る」だけとし、スクリプト経由の書き込み（`todo.py`）で記録する。

**Layer 2: worklog digest 生成時のバッチ突き合わせ（取りこぼし回収）**

jarvis-worklog はどのみち全作業ログを収集して digest 化するので、
digest 生成後のステップとして次を追加する:

- digest の「作業内容」を台帳と突き合わせ、**やったのに台帳に無い作業**を `source: worklog` で追記
  （完了済み事実なので自動 + 通知）。
- digest の「次にやること / 残課題」を **inbox に収穫**する（コミットメントの決定は棚卸しで）。

Layer 1 が漏らしても Layer 2 が機械的に回収する。これで「作業したのに ToDo が無い」状態は
worklog を回した時点で必ず解消される。

### 4.3 収穫（harvest）

ToDo になりうる情報の発生源ごとに取り込みルートを定める。いずれも **inbox 行き**が基本。

| 発生源 | 取り込み方 | 実装先 |
|---|---|---|
| worklog digest の「次にやること」「判断待ち」 | digest 生成後に自動で inbox へ | jarvis-worklog SKILL.md に 1 ステップ追記 |
| giziroku の TODO セクション（自分担当分） | 議事録生成後に「ToDo 台帳に入れるか」を確認して inbox へ（他人の TODO は入れない） | friday-giziroku SKILL.md に 1 ステップ追記 |
| 調査・壁打ちセッションの結論 | 会話の区切りで「これ ToDo にしますか」と候補提示 → 採用分を inbox へ | CLAUDE.md のルール（Layer 1 と同じ節） |
| ユーザーの発話（「あとでやる」「〜しないと」） | その場で inbox へ自動追記 + 通知 | 同上 |

### 4.4 棚卸し（オンデマンド）

定時チェックインは廃止し、「ToDo 整理して」「棚卸し」等の**要求時のみ**実行する:

1. inbox の消化 — 昇格（project・見積を付ける）/ drop をユーザーが確定
2. stale 検知 — `in_progress` のまま更新が途絶えたタスク、inbox 滞留を質問形式で確認
   （現行ストッパー検知の縮退版。断定しない、深追いしない、は維持）
3. 大きすぎるタスクの分割提案（4.1）
4. 直近の着手順の提案（決定はユーザー）
5. 同期（4.5）を最後に実行

### 4.5 Google Tasks 同期

- **内部台帳（todos.json）が単一の真実**。同期は初版では push 一方向（内部 → Google）。
- `google.dirty: true` の項目を列挙し、MCP ツールで作成 / 更新 / 完了反映する。
  成功したら `task_id` / `synced_at` を記録して dirty を落とす。
- Google 側のリスト構成は **プロジェクト = 1 リスト**（決定済み。スマホで案件別に見られる）。
  リストが無ければ同期時に作成し、リスト ID は `todo-data/google_lists.json` にキャッシュする。
- inbox ステータスのタスクは同期しない（未確定のノイズを外に出さない）。
- Google 側でチェックした完了の pull（双方向化）は運用が回ってからの拡張とする。
- MCP サーバーは**公開されている非公式のものは使わず自作する**（決定済み。設計は §4.7）。
  依存は公式提供物のみ（MCP 公式 Python SDK + Google 公式クライアントライブラリ）。

### 4.7 自作 Google Tasks MCP サーバーの設計

**配置**: 当リポジトリの `mcp-servers/google-tasks/`（git 管理する。認証情報は含めない）。

```
mcp-servers/google-tasks/
  server.py            # MCP サーバー本体（stdio トランスポート）
  requirements.txt     # mcp, google-api-python-client, google-auth-oauthlib
  README.md            # セットアップ手順（GCP 側の作業含む）
```

**技術スタック**（すべて公式提供物。非公式コードに依存しない）:

- MCP 公式 Python SDK（`mcp` パッケージ, FastMCP）で stdio サーバーとして実装
- Google 公式の `google-api-python-client` + `google-auth-oauthlib` で Tasks API v1 を叩く
- スコープは `https://www.googleapis.com/auth/tasks` のみ

**公開ツール**（push 一方向同期に必要な最小セット）:

| ツール | 役割 |
|---|---|
| `list_tasklists()` | タスクリスト一覧（プロジェクト → リスト対応の確認用） |
| `create_tasklist(title)` | プロジェクト用リストの作成 |
| `create_task(tasklist_id, title, notes?, due?)` | タスク作成。戻りの task_id を台帳に記録 |
| `update_task(tasklist_id, task_id, title?, notes?, due?, status?)` | 更新・完了反映（status: needsAction / completed） |
| `list_tasks(tasklist_id, show_completed?)` | リスト内タスク一覧（同期検証・将来の pull 用） |

**認証**: OAuth 2.0 インストール型アプリフロー。

- ユーザー側の一度きりの作業: GCP プロジェクト作成 → Tasks API 有効化 →
  OAuth クライアント ID（デスクトップ）作成 → `credentials.json` をダウンロード。
- 認証情報の置き場は `~/.config/google-tasks-mcp/`（`credentials.json` と初回認可後の
  `token.json`）。**リポジトリ内には置かない**。トークンはリフレッシュトークンで自動更新。
- 初回起動時（またはトークン失効時）にブラウザで認可フローを実行する。

**登録**: `claude mcp add google-tasks -- <venv の python> mcp-servers/google-tasks/server.py`。
ツール名は `mcp__google-tasks__create_task` 等になり、SKILL.md の同期フローから直接参照する。

### 4.6 ダッシュボード連携（将来）

- ダッシュボード側は `todo-data/todos.json`（現在状態）と `events.jsonl`（タイムライン）を
  読み取り専用で参照する。書き込みはしない。
- そのために `schema_version` を持たせ、スキーマ変更時は version を上げて後方互換を保つ。
  スキーマ定義は本ドキュメント §3.2 を正とし、変更時はここを更新する。
- スキル側の追加実装は不要（安定スキーマの維持だけが責務）。

## 5. スクリプト設計

すべて python3 標準ライブラリのみ。`TODO_DATA` で置き場を上書き可能。

| スクリプト | 役割 |
|---|---|
| `scripts/todo.py` | 台帳 CLI。`add` / `split` / `start` / `done` / `drop` / `promote`（inbox→todo）/ `list`（--status, --project, --dirty フィルタ）/ `note`。全変更を events.jsonl に追記し、todos.json を更新して dirty を立てる |
| `scripts/pipeline.py` | 自己進化パイプラインのロガー（現行のまま・改変禁止） |
| `scripts/evolve.py` | 進化レビュー（現行のまま） |

廃止: `init_today.py` / `append_memo.py` / `finalize_day.py` / `journal_paths.py`（日次ジャーナル前提のため）。

## 6. 現行から捨てるもの・残すもの

| 現行要素 | 扱い |
|---|---|
| 2 時間おきチェックイン・始業/終業フロー | **廃止**（オンデマンド棚卸しに置き換え） |
| journal/ の日次 todo.md / memo.md / report.md | **廃止**（todos.json + events.jsonl に置き換え。日報は friday-daily-report の責務で重複していた） |
| backlog.md | **廃止**（inbox / todo ステータス + project 軸で代替） |
| ストッパー検知（状態不変・見積 1.5 倍超過） | **縮退して維持**（棚卸し時の stale 検知。質問形式・断定しない、は維持） |
| 見積の 3 段フォールバック | **簡素化**（30〜60 分粒度への分割が主役。実績は events.jsonl のタイムスタンプから将来集計） |
| 「確定はユーザー」原則 | **再定義**（事実の記録は自動 + 通知、意図の決定は提案制。§2） |
| 自己進化パイプライン | **維持**（進化対象を再定義: 分割粒度、突き合わせマッチング精度、収穫の抽出ルール、Google 同期の運用） |
| 生ログ保全・機密マスキング・推測の明示 | **維持**（jarvis persona 準拠のまま） |

スキル名は `jarvis-todo-management` のまま（一次記録・自分が読み手、という jarvis の定義に引き続き合致）。

## 7. 実装フェーズ

| Phase | 内容 | 依存 |
|---|---|---|
| **1. コア台帳** | `todo-data/` スキーマ + `todo.py` CLI + SKILL.md 全面書き換え + .gitignore 更新（/journal/ → /todo-data/）+ 旧スクリプト削除 | なし |
| **2. 突き合わせ** | CLAUDE.md に Layer 1 ルール追記 + jarvis-worklog SKILL.md に digest 後突き合わせステップ追記 | Phase 1 |
| **3. 収穫** | friday-giziroku SKILL.md に TODO 収穫ステップ追記 + 調査・壁打ちからの候補提案ルール | Phase 1 |
| **4. Google Tasks 同期** | 自作 MCP サーバー実装（`mcp-servers/google-tasks/`, §4.7）+ SKILL.md の同期フロー実装 | Phase 1 + **GCP 側の OAuth クライアント作成（ユーザー作業。手順は README に記載）** |
| **5. ダッシュボード** | スキーマ凍結の確認のみ（本体は別プロジェクト側で開発） | Phase 1 |

Phase 2〜3 は他スキルの SKILL.md への追記が発生するが、いずれも末尾 1 ステップの追加であり
各スキルの固定の芯（分類ロジック・発言の聖域など）には触れない。

## 8. 決定事項（2026-07-02 ユーザー決定）

1. **Google Tasks への接続方式** — 公開されている非公式 MCP サーバーは信用しないため**自作する**。
   依存は MCP 公式 SDK と Google 公式クライアントライブラリのみ（設計は §4.7）。
2. **Google 側のリスト構成** — **プロジェクト = 1 リスト**。
3. **自動記載の通知粒度** — 自動で inbox / done に入れたとき、**毎回チャットで一言通知**する。
