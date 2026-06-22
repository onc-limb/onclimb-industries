# 作業記録システム 作成指示書（改訂版 v2）

このファイルは、Claude Code に渡して「作業記録スキルとその機構」を作らせるための指示書です。
そのまま Claude Code のセッションに貼り付けるか、`@work-log-system-instructions.md` で参照させてください。

---

## 0. 背景と目的（実装者向けコンテキスト）

依頼者は SES 参画中のエンジニアで、コーディングや調査の多くを AI エージェント（Claude Code）への指示で行っている。
最終成果物だけが残り、「何を考え、何を試したか」という過程が残らないため、作業報告・進捗報告・ナレッジ蓄積が困難になっている。

これを解決するため、以下の4ステップを持つ「作業記録システム」を構築する。

1. **記録** … 作業ログを自動で残す（消失リスクに二重で備える）
2. **分類** … プロジェクト・作業単位にグルーピングする
3. **要約** … 報告書／成果報告／ナレッジの3形式に整形する（ノイズ除去込み）
4. **退避** … 要約済みの生ログをアーカイブする（削除ではなく圧縮退避）

---

## 1. 前提知識（事実確認済み・実装の根拠）

実装者はこの前提を踏まえること。これらは設計判断の理由になっている。

### 1-1. Claude Code の会話履歴は自動保存されるが、消える
- CLI のトランスクリプトは JSONL 形式で `~/.claude/projects/<project>/<session-id>.jsonl` に保存される。`<project>` は作業ディレクトリのパスから導出される。
- **デフォルトで30日後に自動削除される**。`~/.claude/settings.json` の `cleanupPeriodDays` で変更可能。
- ⚠️ `cleanupPeriodDays: 0` は「永久保持」ではなく「永続化を完全に無効化（＝書き込まれない）」という挙動なので **絶対に 0 にしない**。永久保持目的なら `36500` 等の大きな値にする。
- ⚠️ さらに、`cleanupPeriodDays` を大きくしていても、CLI / 拡張機能 / アプリの**アップデートや再起動を契機に JSONL が消えるバグが現存**する（数百セッション消失の報告あり）。
- **したがって「Claude Code が保持してくれる」前提に依存してはいけない。早期に自分の管理下（`raw/`）へ収集・退避することが本システムの最優先事項。**

### 1-2. ツール操作までログに残る（好都合）
- JSONL にはプロンプト・応答に加え、**ツール呼び出し（Read / Write / Edit / Bash）、各ターンのトークン数、使用モデル**などが記録される。
- 「何を考え何を試したか」という過程が、会話だけでなくツール操作レベルで残る＝本システムの目的に合致。

### 1-3. ただしノイズが多い
- JSONL には `attachment`、`task_reminder`、IDEイベント、`skill-list`変更、`last-prompt`、`file-history-snapshot`、サブエージェント進捗などのメタデータが大量に混在する（実測でファイルの26%超がメタデータの例あり）。
- **収集・要約段階でノイズを除去しないと品質が落ちる。**

### 1-4. 環境ごとにログの保存場所が違う（同期しない）
- CLI / VS Code拡張 / デスクトップアプリの Code タブ / Web版 はそれぞれ独立した履歴を持ち、相互同期しない。
- **収集対象パス（本システムが取得するログ）:**
  - CLI（メイン）: `~/.claude/projects/`
  - デスクトップアプリ Code タブ:
    - macOS: `~/Library/Application Support/Claude/claude-code-sessions/<accountId>/<orgId>/`
    - Windows: `%AppData%\Claude\claude-code-sessions\<accountId>\<orgId>\`
  - Web版（claude.ai）: **ローカルにファイルが無いため取得対象外**（サーバ側管理）。これは仕様上の制約として README に明記する。

---

## 2. 設計方針

### 2-1. 記録は二重で確実に残す（消失対策）
収集を以下の **2系統で冗長化**する。どちらかが漏れてももう一方が拾う。
1. **SessionEnd Hook**: セッション終了のたびに `bin/collect.sh` を起動し、その時点のログを `raw/` へ収集。
2. **毎日1回のスケジュール実行**: cron（macOS は launchd でも可）で1日1回 `bin/collect.sh` を実行し、取りこぼし・アップデート起因の消失前に確実に退避。
   - README に cron と launchd 両方の設定例を記載すること。

加えて推奨として **PreCompact Hook** でも collect を呼ぶ（`/compact` で要約され情報が失われる前に生ログを確保できるため）。

### 2-2. ノイズ除去は「収集時の構造抽出」＋「要約プロンプト」の二段で行う
- collect 段階で、エントリ種別を見て **`user` / `assistant` / `tool_use`（Read/Write/Edit/Bash等）/ `tool_result` のみ抽出**し、`attachment`・`task_reminder`・`last-prompt`・`file-history-snapshot`・`skill-list`・IDEイベント等の Claude Code 内部メタデータは捨てる。
- summarize 段階の **プロンプトにもノイズ除去指示を明記**する（残ったノイズや重複・冗長なツール出力を要約から除外し、判断・試行・結論に集中させる）。

### 2-3. 分類・要約は半自動（区切りで1回指示）
- 完全無人定期実行はスキル単体では不可。区切りで「まとめて」と指示する半自動を基本とする。
- ただし cron / launchd で `claude -p "..."` をバッチ実行し分類・要約まで自動化する設定例も**オプション**として README に記載。

### 2-4. 生ログは「削除」ではなく「アーカイブ退避」
- 要約は必ず情報を欠落させるため完全削除は禁止。要約済み生ログは月次 zip 圧縮で `archive/` へ退避。

### 2-5. SES 守秘対応（必須）
- 顧客名・固有名詞・APIキー・トークン・接続文字列・本番URL・個人情報は `<REDACTED:種別>` に伏字化。
- マスキング辞書を `config/redaction.yaml` に外出しし、依頼者が編集可能にする。
- マスキングは collect 段階（`raw/` 書き込み前）で適用する＝生ログ時点で機密を残さない。

---

## 3. ディレクトリ構成（作成してほしい成果物）

```
worklog/
├── .claude/
│   ├── skills/
│   │   └── worklog/
│   │       └── SKILL.md          # 分類・要約・退避を呼び出すスキル本体
│   └── settings.json             # Hooks 設定（SessionEnd / PreCompact で collect 実行）
├── bin/
│   ├── collect.sh                # 複数パスの生JSONLを raw/ へ収集・構造抽出・マスキング
│   ├── classify.py               # プロジェクト×作業単位に分類
│   ├── summarize.py              # 3形式の文書を生成（claude -p を呼ぶ、ノイズ除去プロンプト込み）
│   └── archive.sh                # 要約済み生ログを月次zip退避
├── config/
│   ├── sources.yaml              # 収集対象パスの一覧（CLI / デスクトップアプリ）
│   ├── projects.yaml             # プロジェクトID・判定キーワード・パスの定義
│   └── redaction.yaml            # マスキング辞書
├── raw/                          # 収集した生ログ（構造抽出・マスキング済み、未分類）
│   └── .cursor                   # 取り込み済み session_id + 行オフセット
├── classified/                   # 分類済み（プロジェクト/日付別）
│   └── _unclassified/            # 判定不能分
├── reports/
│   ├── progress/                 # 作業報告書（進捗報告用）
│   ├── deliverables/             # 成果報告書
│   └── knowledge/                # ナレッジの種
├── archive/                      # 要約済み生ログのzip（YYYY-MM.zip）
└── README.md                     # 使い方・運用手順・cron/launchd設定例
```

---

## 4. ログのデータ構造（分類・要約の精度を担保する核心）

収集後の `raw/` の1エントリ（JSONL 1行＝1エントリ）。

```json
{
  "ts": "2026-06-22T14:03:11+09:00",
  "source": "cli | desktop",        // どの環境由来か
  "session_id": "abc123",
  "project_id": "未分類",            // 後で classify が確定
  "cwd": "/path/to/working/dir",    // 分類の最有力手がかり
  "role": "user | assistant",
  "kind": "instruction | response | tool_use | tool_result",
  "tool": "Read | Write | Edit | Bash | null",  // kindがtool_*のとき
  "body": "本文（ノイズ除去・マスキング適用後）"
}
```

- `project_id` は収集時は「未分類」でよい。`classify.py` が確定する。
- 分類の手がかり優先順位：① `cwd`（作業ディレクトリパス、最も確実）→ ② git リポジトリ名 → ③本文キーワード。
- 判定不能は「未分類」のまま残し、依頼者が後で手動タグ付けできるようにする（**誤分類より未分類を優先**）。

---

## 5. 各成果物の要件

### 5-1. `config/sources.yaml`
- 収集対象パスを列挙（CLI の `~/.claude/projects/`、デスクトップアプリの `claude-code-sessions/...`）。
- OS（macOS / Windows）でパスが分岐するため、両対応 or 実行環境を検出して切り替える。
- 依頼者が後からパスを追加できる形にする。

### 5-2. `bin/collect.sh`
- `config/sources.yaml` の全パスを走査し、当日（または前回カーソル以降）更新された JSONL を収集。
- §2-2 に従い **`user`/`assistant`/`tool_use`/`tool_result` のみ抽出**、内部メタデータは破棄。
- `config/redaction.yaml` のマスキングを適用してから §4 構造へ変換し `raw/YYYY-MM-DD.jsonl` へ追記。
- `raw/.cursor` に取り込み済み `session_id` + 行オフセットを記録し、**二重取り込みを防止**＝冪等に再実行可能。
- SessionEnd Hook / 毎日cron / 手動、いずれから呼ばれても安全に動くこと。

### 5-3. `.claude/settings.json`（Hooks）
- `SessionEnd` フックで `bin/collect.sh` を起動。
- `PreCompact` フックでも `bin/collect.sh` を起動（compact 前に生ログ確保）。
- 環境依存パスはプレースホルダ `<WORKLOG_HOME>` とし、README で置換手順を案内。

### 5-4. スケジュール実行（README に記載 + サンプル同梱）
- 毎日1回 `bin/collect.sh` を走らせる cron 設定例（Linux/macOS）と launchd plist 例（macOS）を提供。
- 「収集（毎日自動）」と「分類・要約（区切りで手動 or オプションで自動）」を分けて説明。

### 5-5. `bin/classify.py`
- `raw/*.jsonl` を読み、§4 の優先順位で `project_id` を確定。
- `classified/<project_id>/YYYY-MM-DD.jsonl` へ振り分け。未分類は `classified/_unclassified/` へ。

### 5-6. `bin/summarize.py`
- 分類済みログを入力に `claude -p`（ヘッドレス実行）で3形式を生成。
- **要約プロンプトに必ず含める指示:**
  - 残存ノイズ（重複・空の task_reminder・冗長なツール出力・進捗メッセージ等）を除外する。
  - **過程（何を試し、なぜその判断をしたか、何が失敗し何が効いたか）を必ず残す。** 最終結果だけの要約は不可＝本システムの存在理由。
  - 元ログにない内容を捏造しない。不明点は「記録なし」と明示。
- 3形式と各テンプレート（成果物に同梱）:
  - **progress（作業報告書）**: 日付・プロジェクト別に「やったこと／進捗／次の予定／課題」。
  - **deliverables（成果報告書）**: 完成した成果物と、その判断根拠・試行錯誤の要点。
  - **knowledge（ナレッジの種）**: 再利用可能な知見・つまずき・解決策を汎用化。
- 出力は Markdown。

### 5-7. `bin/archive.sh`
- summarize 完了済みの `raw/` `classified/` を月単位で zip 化し `archive/YYYY-MM.zip` へ。
- 圧縮後に元ファイル削除（zip 内には必ず残る＝完全消失しない）。
- 実行前に「未要約のログが残っていないか」チェックし、残っていれば中断・警告。

### 5-8. `.claude/skills/worklog/SKILL.md`
- bin 群を自然言語で呼び出せるスキル。トリガー: "作業ログ", "まとめて", "作業報告", "進捗報告", "ナレッジ" 等。
- 標準フロー（分類→要約→退避）と個別実行の両方をサポート。
- 破壊的操作（archive の削除）は実行前に必ず確認。

### 5-9. `README.md`
- セットアップ（パス置換、`cleanupPeriodDays` を `36500` 等に設定する推奨、Hooks 有効化、cron/launchd 登録）。
- 日々の運用（収集は全自動、分類・要約は区切りで「まとめて」）。
- Web版は取得対象外である制約の明記。
- 消失バグへの注意と、本システムが早期収集で対策している旨。

---

## 6. 実装順序

1. ディレクトリ雛形 + `config/*.yaml` 初期版（`sources.yaml` 含む）
2. `collect.sh` + Hooks + cron/launchd（＝記録の冗長収集をまず動かす）
3. `classify.py`（分類）
4. `summarize.py` + 各テンプレート（要約、ノイズ除去プロンプト込み）
5. `archive.sh`（退避）
6. `SKILL.md` で全体を束ねる
7. `README.md`

各ステップ完了ごとにサンプルログ1日分での動作確認結果を提示すること。

---

## 7. 受け入れ基準（これが満たせたら完成）

- [ ] セッション終了時（Hook）と毎日1回（cron/launchd）の二重で、依頼者が何もせず `raw/` にログが溜まる
- [ ] CLI と デスクトップアプリ Code タブ、両方のパスからログを取得できる
- [ ] 収集時に内部メタデータ（attachment / task_reminder 等）が除去され、user/assistant/tool_use/tool_result のみ残る
- [ ] 顧客固有情報がマスキングされている（テストデータで検証）
- [ ] 「まとめて」の一声で当日分が分類→3形式の報告書まで生成される
- [ ] 報告書に「過程・試行錯誤・判断理由」が含まれている（結果だけでない）
- [ ] 生ログは削除されず zip に必ず残る
- [ ] 誤分類より未分類を優先する挙動になっている

---

## 8. 注意（実装者へ）

- `~/.claude/` の JSONL スキーマは Claude Code のバージョンで変わりうる。実装前に実物を1ファイル `head` で確認し、エントリ種別の実際のフィールド名（`type` 等）を見てから collect.sh のパーサを組むこと。デスクトップアプリ側のスキーマも CLI と差がある可能性があるので同様に確認。
- パスはハードコードせず `config/sources.yaml` / 環境変数 `WORKLOG_HOME` で外出し。
- `cleanupPeriodDays` は 0 にしない（書き込みが止まる）。永久保持目的なら大きな値。
- まず最小構成で end-to-end を通し、その後で精度・整形品質を上げる。
