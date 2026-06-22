# worklog — 作業記録システム

Claude Code での作業（会話＋ツール操作）を自動で記録し、**最終成果物だけでなく
「何を考え・何を試したか」という過程**を作業報告・進捗報告・ナレッジとして残すためのシステム。

4 ステップで動く:

1. **記録** … セッション終了 Hook と毎日の定期実行で、生ログを `raw/` へ二重に収集（消失対策）
2. **分類** … プロジェクト×日付にグルーピング
3. **整理** … プロジェクト視点 / 技術者視点の 2 形式の「整理された情報（digest）」に構造化（ノイズ除去込み）。最終報告書ではなく、別スキルが報告書へ整形するための素材
4. **退避** … 整理済みの生ログを月次 zip でアーカイブ（削除ではなく圧縮退避）

---

## なぜ必要か（消失対策）

- Claude Code の会話履歴は `~/.claude/projects/<project>/<session-id>.jsonl` に保存されるが、
  **既定で 30 日後に自動削除**される（`~/.claude/settings.json` の `cleanupPeriodDays`）。
- さらに **CLI / 拡張 / アプリのアップデートや再起動を契機に JSONL が消えるバグが現存**する。
- したがって「Claude Code が保持してくれる」前提に依存せず、**早期に自分の管理下（`raw/`）へ収集**することが
  本システムの最優先事項。Hook（セッション終了ごと）と cron/launchd（毎日）の二重で確実に退避する。

> ⚠️ `cleanupPeriodDays` は **0 にしない**（「永久保持」ではなく「永続化を無効化＝書き込まれない」挙動）。
> 永久保持目的なら `36500` 等の大きな値にする。

---

## ディレクトリ構成（コードとデータは分離）

**コード・設定**（git 追跡）＝ スキルディレクトリ内:

```
.claude/skills/worklog/
├── SKILL.md                  # スキル本体（自然言語トリガー）
├── README.md
├── bin/
│   ├── collect.sh / collect_impl.py   # 生JSONL を raw/ へ収集・構造抽出・マスキング
│   ├── classify.py                    # プロジェクト×日付に分類
│   ├── summarize.py                   # 2形式の整理情報を生成（claude -p）
│   ├── archive.sh / archive_impl.py   # 整理済み生ログを月次 zip 退避
│   └── worklog_lib.py                 # 共通ライブラリ（軽量YAMLパーサ含む・依存ゼロ）
├── config/
│   ├── sources.yaml          # 収集対象パス（CLI / デスクトップアプリ）
│   ├── projects.yaml         # プロジェクトID・判定キーワード・パス
│   └── redaction.yaml        # マスキング辞書（SES守秘）
├── templates/                # 整理情報2形式のテンプレート（project / tech）
└── deploy/                   # Hooks 設定サンプル + cron / launchd サンプル
    ├── settings.sample.json
    ├── crontab.sample
    └── com.user.worklog.collect.plist
```

**データ**（git 追跡しない＝`worklog-data/` をリポジトリ直下の `.gitignore` で除外）:

```
<repo>/worklog-data/          # 既定。WORKLOG_DATA 環境変数で変更可
├── raw/                      # 収集した生ログ（構造抽出・マスキング済み、未分類）
│   └── .cursor               # 取り込み済みオフセット（冪等化用）
├── classified/               # 分類済み（プロジェクト/日付別）。_unclassified/ は判定不能分
├── digests/{project,tech}/   # 生成された整理情報（報告書の素材）
├── archive/                  # 整理済み生ログの zip（YYYY-MM.zip）
└── logs/                     # cron/launchd の実行ログ
```

> データ置き場は `worklog_lib.data_home()` が決める: `WORKLOG_DATA` 環境変数 → 無ければ
> スキルが属する git リポジトリ直下の `worklog-data/` → どちらも無ければ `~/worklog-data`。
> コード（スキル）を別リポジトリにコピーすれば、そのリポジトリ直下にデータが作られる。

---

## セットアップ

`<SKILL>` はスキルディレクトリの絶対パス
（例: `/Users/satoshi-onga/Documents/portfolio/jarvis/.claude/skills/worklog`）。

### 1. 依存

- `python3`（標準ライブラリのみ。pyyaml 等の追加パッケージ不要）
- `claude` CLI（整理に使用。無くても収集・分類は動き、整理はプロンプトを `.prompt.txt` に書き出す）

### 2. 履歴の保持期間を延ばす（推奨）

`~/.claude/settings.json` に追記:

```json
{ "cleanupPeriodDays": 36500 }
```

### 3. Hooks を有効化（セッション終了ごとに収集）

`deploy/settings.sample.json` がテンプレート。`<SKILL>` を実パスに置換し、
**プロジェクトの `.claude/settings.json`** か **`~/.claude/settings.json`** にマージする。

```json
{
  "hooks": {
    "SessionEnd": [
      { "hooks": [ { "type": "command",
        "command": "bash <SKILL>/bin/collect.sh" } ] }
    ],
    "PreCompact": [
      { "hooks": [ { "type": "command",
        "command": "bash <SKILL>/bin/collect.sh" } ] }
    ]
  }
}
```

- `SessionEnd`: セッション終了のたびに収集。
- `PreCompact`: `/compact` で要約され情報が失われる前に生ログを確保（推奨）。
- プロジェクト `.claude/settings.json` に置くとそのプロジェクトでの作業時に発火。
  全プロジェクトで確実に発火させたい場合は `~/.claude/settings.json`（グローバル）に置く。
  どちらでも collect は全プロジェクトのログを走査するので、取りこぼしは毎日の cron が拾う。
- データを既定（リポジトリ直下 `worklog-data/`）以外に置きたい場合は、command 先頭に
  `WORKLOG_DATA=/path ` を付ける。

### 4. 毎日の定期収集を登録（消失対策の本命）

**cron（Linux / macOS）** — `deploy/crontab.sample` を参照。`crontab -e` で:

```
50 23 * * * /bin/bash <SKILL>/bin/collect.sh >> <SKILL>/../../../worklog-data/logs/collect.log 2>&1
```

**launchd（macOS 推奨）** — `deploy/com.user.worklog.collect.plist` の `<SKILL>` を置換して:

```sh
cp deploy/com.user.worklog.collect.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.user.worklog.collect.plist
```

---

## 日々の運用

- **収集は全自動**（Hook ＋ 毎日 cron/launchd）。普段は何もしなくてよい。
- **分類・整理は区切りで半自動**。一日の終わりやタスクの区切りで、Claude Code に
  「**今日の作業まとめて**」と言えば、スキル `worklog` が当日分を 収集→分類→2形式の整理情報 まで生成する。
- 手動で回す場合:

```bash
SKILL=<SKILL>
TODAY=$(date +%F)
bash   "$SKILL/bin/collect.sh"
python3 "$SKILL/bin/classify.py" "$TODAY"
python3 "$SKILL/bin/summarize.py" "$TODAY"
```

生成物: `worklog-data/digests/{project,tech}/<project>_<date>.md`（＝報告書の素材となる整理情報）

各 digest は結論層（TL;DR/サマリ）＋詳細層を持ち、下流の用途別に出し分けできる:
- `project` … 進捗報告書・作業報告書 / 上長・顧客向けサマリ / 振り返り(レトロ) の素材
- `tech` … 技術ナレッジ・スキル証跡 / 手順書(Runbook) / 技術報告書・技術メモ の素材

### 退避（任意・区切りで）

整理が済んだ月の生ログを zip に固めて元ファイルを消す（zip には必ず残る）。

```bash
bash "$SKILL/bin/archive.sh" --check 2026-05   # 未整理チェックのみ
bash "$SKILL/bin/archive.sh" 2026-05           # 退避実行
```

未整理ログ（digest 未生成）が残っていると既定で中断する（`--force` で強制）。

---

## 設定のカスタマイズ

- **プロジェクトを増やす**: `config/projects.yaml` に `id` / `path_globs` / `repos` / `keywords` を追加。
  判定は cwd → git リポジトリ名 → 本文キーワードの順。**誤分類より未分類を優先**する設計。
- **機密語を伏字化**: `config/redaction.yaml` に `literals`（顧客名等の固定文字列）や `patterns`（正規表現）を追加。
  マスキングは collect 段階で適用され、`raw/` には機密が残らない。
- **収集元を増やす**: `config/sources.yaml` にパスを追加。
  > これらの YAML は依存ゼロの簡易パーサで読むため**ブロックスタイル**で書くこと（`{a: b}` のフロー記法は不可）。

---

## 制約

- **Web 版（claude.ai）は収集対象外**。ローカルにログファイルが無く、サーバ側管理のため取得できない（仕様）。
- デスクトップアプリ Code タブのトランスクリプト実体は CLI と同じ `~/.claude/projects/` に
  `cliSessionId` で保存される。`claude-code-sessions/` 側はメタデータ（タイトル等）として参照する。
- 整理は `claude -p`（ヘッドレス）を使う。`claude` が無い/失敗時は合成プロンプトを
  `digests/<type>/<...>.prompt.txt` に保存するので、後から手動生成できる。

---

## データ構造（`raw/` の 1 エントリ）

```json
{
  "ts": "2026-06-22T14:03:11+09:00",
  "source": "cli | desktop",
  "session_id": "abc123",
  "project_id": "未分類",
  "cwd": "/path/to/working/dir",
  "role": "user | assistant",
  "kind": "instruction | response | tool_use | tool_result",
  "tool": "Read | Write | Edit | Bash | null",
  "body": "本文（ノイズ除去・マスキング適用後）"
}
```

`attachment` / `file-history-snapshot` / `mode` / `permission-mode` / `system` / `last-prompt` 等の
Claude Code 内部メタデータは収集時に破棄され、`user` / `assistant` / `tool_use` / `tool_result` のみ残る。
