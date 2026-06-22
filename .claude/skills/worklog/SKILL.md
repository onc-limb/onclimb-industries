---
name: worklog
description: 作業記録システム。Claude Code の会話・ツール操作ログを収集→分類→3形式の報告書に要約→アーカイブ退避する。「作業ログ」「まとめて」「作業報告」「進捗報告」「成果報告」「ナレッジ」「今日の作業を報告書に」等で起動。SES 参画中の作業報告・進捗報告・ナレッジ蓄積のために、最終成果物だけでなく「何を考え・何を試したか」という過程を残す。生ログは削除せず zip 退避するため消失しない。
metadata:
  type: skill
  data_dir: <repo>/worklog-data
---

# worklog — 作業記録スキル

このスキルディレクトリ内の `bin/` ツール群を自然言語から呼び出すスキル。
収集（記録）は Hooks / cron で自動化されているので、このスキルが担うのは主に
**分類 → 要約 → 退避** の半自動オペレーションと、個別ツールの実行。

## 場所（コードとデータは分離されている）

- ツール本体・設定: このスキルディレクトリ `.claude/skills/worklog/`（`bin/` `config/` `templates/`）
- 設定: `config/{sources,projects,redaction}.yaml`
- **データ**: スキルが属する git リポジトリ直下の `worklog-data/`
  （`raw/` `classified/` `reports/` `archive/` `logs/`）。`WORKLOG_DATA` 環境変数で上書き可。
- 実行はスキルディレクトリの絶対パスを `SKILL` に入れて bin を呼ぶ。スクリプトが配置場所から
  自動で config/templates を解決し、データ置き場（`worklog-data/`）も自動算出する。

## トリガーと対応フロー

| ユーザー発話の例 | 実行する標準フロー |
|---|---|
| 「今日の作業まとめて」「作業報告して」「進捗報告」 | 標準フロー（当日: collect → classify → summarize） |
| 「成果報告を作って」 | summarize の `--formats deliverables` |
| 「ナレッジ抽出して」 | summarize の `--formats knowledge` |
| 「ログ集めて」「収集して」 | collect のみ |
| 「分類して」 | classify のみ |
| 「古いログを退避して」「アーカイブして」 | archive（**実行前に必ず確認**） |

## 標準フロー（「まとめて」の一声で当日分を報告書まで）

```bash
SKILL=/Users/satoshi-onga/Documents/portfolio/jarvis/.claude/skills/worklog
TODAY=$(date +%F)
bash   "$SKILL/bin/collect.sh"                 # 1) 取りこぼし収集（冪等）
python3 "$SKILL/bin/classify.py" "$TODAY"      # 2) 当日分を分類
python3 "$SKILL/bin/summarize.py" "$TODAY"     # 3) 3形式の報告書を生成
```

- 生成物は `worklog-data/reports/{progress,deliverables,knowledge}/<project>_<date>.md`。
- 完了後、生成された報告書のパスと要点をユーザーに提示する。
- 日付やプロジェクトを限定したい場合は引数を渡す:
  - 特定日・全プロジェクト: `summarize.py 2026-06-22`
  - 特定日・特定プロジェクト: `summarize.py 2026-06-22 jarvis`
  - 形式を絞る: `summarize.py --formats progress,knowledge 2026-06-22`

## 個別実行

- **収集のみ**: `bash "$SKILL/bin/collect.sh"`
  - 複数ソース（CLI / デスクトップ Code タブ）の生ログを構造抽出・マスキングして `raw/` へ。冪等。
- **分類のみ**: `python3 "$SKILL/bin/classify.py" [YYYY-MM-DD]`
  - cwd → git リポジトリ名 → 本文キーワードの順で `project_id` 確定。不明は `_unclassified`（誤分類より未分類優先）。
- **要約のみ**: `python3 "$SKILL/bin/summarize.py" [YYYY-MM-DD] [project] [--formats ...] [--dry-run]`
  - `claude -p` をヘッドレス実行。`claude` が無い/失敗時はプロンプトを `.prompt.txt` に保存。
- **退避**: `bash "$SKILL/bin/archive.sh" [YYYY-MM] [--force] [--check]`

## 退避（破壊的操作 — 必ず確認してから）

`archive.sh` は要約済みの `raw/` `classified/` を `archive/YYYY-MM.zip` に圧縮し**元ファイルを削除**する
（zip 内には必ず残るので完全消失しない）。**実行前に必ずユーザーに確認する**こと。

```bash
# まず未要約チェック（退避しない）
bash "$SKILL/bin/archive.sh" --check 2026-05
# 問題なければ退避（当月より前の全月。月指定も可）
bash "$SKILL/bin/archive.sh" 2026-05
```

- 未要約ログが残っていると既定で中断する。意図的に進める場合のみ `--force`。
- `_unclassified` は要約対象にしないことが多い。退避前に必要なら要約するか、`--force` で進める判断をユーザーに委ねる。

## 注意

- マスキングは collect 段階で適用済み（`config/redaction.yaml`）。報告書の `<REDACTED:種別>` は復元しない。
- プロジェクトを増やすときは `config/projects.yaml` に、機密語を伏字化するときは `config/redaction.yaml` に追記。
- Web 版（claude.ai）はローカルにログが無いため収集対象外。
