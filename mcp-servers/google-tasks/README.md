# google-tasks MCP サーバー

jarvis-todo-management の Google Tasks 同期（push 一方向）のための自作 MCP サーバー。
公開されている非公式 MCP サーバーは使わない方針のため自作している。
依存は公式提供物のみ: MCP 公式 Python SDK（`mcp`）+ Google 公式クライアント
（`google-api-python-client` / `google-auth-oauthlib`）。
設計: [docs/todo-management-redesign-2026-07-02.md](../../docs/todo-management-redesign-2026-07-02.md) §4.7。

## 提供ツール

| ツール | 役割 |
|---|---|
| `list_tasklists()` | タスクリスト一覧（プロジェクト → リスト対応の確認） |
| `create_tasklist(title)` | プロジェクト用リストの作成 |
| `create_task(tasklist_id, title, notes?, due?)` | タスク作成（due は YYYY-MM-DD 可） |
| `update_task(tasklist_id, task_id, title?, notes?, due?, status?)` | 更新・完了反映（status: needsAction / completed） |
| `list_tasks(tasklist_id, show_completed?)` | リスト内タスク一覧（同期検証用） |

スコープは `https://www.googleapis.com/auth/tasks` のみ。

## セットアップ

### 1. GCP 側（一度きり・ブラウザ作業）

1. [Google Cloud Console](https://console.cloud.google.com/) で個人用プロジェクトを作成（既存でも可）。
2. 「API とサービス → ライブラリ」で **Google Tasks API** を有効化。
3. 「API とサービス → OAuth 同意画面」を構成（User Type: 外部、公開ステータス: テスト）。
   **テストユーザーに自分の Google アカウントを追加**する。
4. 「認証情報 → 認証情報を作成 → OAuth クライアント ID」でタイプ **デスクトップアプリ**を作成し、
   JSON をダウンロード。
5. ダウンロードした JSON を `~/.config/google-tasks-mcp/credentials.json` に置く。

### 2. ローカル側

```bash
cd mcp-servers/google-tasks
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python auth.py        # ブラウザで認可 → ~/.config/google-tasks-mcp/token.json が保存される
```

### 3. Claude Code への登録

```bash
claude mcp add google-tasks -- \
  <リポジトリ絶対パス>/mcp-servers/google-tasks/.venv/bin/python \
  <リポジトリ絶対パス>/mcp-servers/google-tasks/server.py
```

登録後、ツールは `mcp__google-tasks__create_task` 等の名前で使える。

## 認証情報の置き場所

- `credentials.json`（OAuth クライアント）と `token.json`（認可トークン）は
  `~/.config/google-tasks-mcp/` に置く。**このリポジトリ内には置かない**（コミット事故防止）。
- 置き場所は環境変数 `GOOGLE_TASKS_MCP_CONFIG` で変更できる。
- トークンはリフレッシュトークンで自動更新される。失効したら `auth.py` を再実行する。

## 設計上の注意

- 対話的な OAuth フローは `auth.py` に分離してある。`server.py` は stdio トランスポートを
  汚さないよう、保存済みトークンの読み込み・リフレッシュしかしない
  （トークンが無いときはツール呼び出しがエラーになり、`auth.py` の実行を促す）。
- 同期の真実は常に内部台帳（`todo-data/todos.json`）。このサーバーは書き込みミラー用。
  唯一の逆方向は `backlog` リスト（スマホ等からのキャプチャ用インボックス）の取り込みで、
  スキル側フロー（jarvis-todo-management フロー F）が `list_tasks` で読んで台帳の inbox に
  収穫し、取り込み済みタスクを completed にする。それ以外の Google 側の変更は台帳へ
  取り込まない。
