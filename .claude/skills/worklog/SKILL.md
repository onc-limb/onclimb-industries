---
name: worklog
description: 作業記録システム。Claude Code の会話・ツール操作ログを収集→分類→「整理された情報」2形式（プロジェクト視点 / 技術者視点）に整理→アーカイブ退避する。「作業ログ」「まとめて」「作業報告」「進捗報告」「整理して」「技術整理」「今日の作業をまとめて」等で起動。出力は最終報告書そのものではなく、後段の別スキルがきちんとした報告書へ整形するための詳細な整理情報。SES 参画中の作業報告・ナレッジ蓄積のために、最終成果物だけでなく「何を考え・何を試したか」という過程を残す。生ログは削除せず zip 退避するため消失しない。
metadata:
  type: skill
  data_dir: <repo>/worklog-data
---

# worklog — 作業記録スキル

このスキルディレクトリ内の `bin/` ツール群を自然言語から呼び出すスキル。
収集（記録）は Hooks / cron で自動化されているので、このスキルが担うのは主に
**分類 → 整理 → 退避** の半自動オペレーションと、個別ツールの実行。

> **位置づけ**: このスキルが生成するのは「報告書を書くための整理された情報（digest）」であって、
> 最終報告書そのものではない。プロジェクト視点・技術者視点の 2 形式で過程を網羅的に構造化し、
> 後段の別スキルがこの digest を入力にきちんとした報告書へ整形する、という二段構えを想定している。

## 場所（コードとデータは分離されている）

- ツール本体・設定: このスキルディレクトリ `.claude/skills/worklog/`（`bin/` `config/` `templates/`）
- 設定: `config/{sources,projects,redaction}.yaml`
- **データ**: スキルが属する git リポジトリ直下の `worklog-data/`
  （`raw/` `classified/` `digests/` `archive/` `logs/`）。`WORKLOG_DATA` 環境変数で上書き可。
- 実行はスキルディレクトリの絶対パスを `SKILL` に入れて bin を呼ぶ。スクリプトが配置場所から
  自動で config/templates を解決し、データ置き場（`worklog-data/`）も自動算出する。

## トリガーと対応フロー

| ユーザー発話の例 | 実行する標準フロー |
|---|---|
| 「今日の作業まとめて」「作業報告して」「整理して」 | 標準フロー（当日: collect → classify → summarize で 2 形式の整理情報） |
| 「プロジェクト視点でまとめて」 | summarize の `--formats project` |
| 「技術整理して」「技術的にまとめて」 | summarize の `--formats tech` |
| 「ログ集めて」「収集して」 | collect のみ |
| 「分類して」 | classify のみ |
| 「古いログを退避して」「アーカイブして」 | archive（**実行前に必ず確認**） |

## 標準フロー（「まとめて」の一声で当日分を整理情報まで）

```bash
SKILL=/Users/satoshi-onga/Documents/portfolio/jarvis/.claude/skills/worklog
TODAY=$(date +%F)
bash   "$SKILL/bin/collect.sh"                 # 1) 取りこぼし収集（冪等）
python3 "$SKILL/bin/classify.py" "$TODAY"      # 2) 当日分を分類
python3 "$SKILL/bin/summarize.py" "$TODAY"     # 3) 2形式の整理情報を生成
```

- 生成物は `worklog-data/digests/{project,tech}/<project>_<date>.md`（＝報告書の素材となる整理情報）。
  各 digest は結論層（TL;DR/サマリ）と詳細層を両方持ち、用途別に出し分けられるよう設計してある:
  - `project` … プロジェクト視点。TL;DR / 成果サマリ(上長・顧客向け) / 作業(進捗ステータス付) / Keep / Problem / 次の予定・Try / 課題・判断待ち。
    → 進捗報告書・作業報告書、上長/顧客向けサマリ、振り返り(レトロ) の素材。
  - `tech` … 技術者視点。TL;DR / 技術選定と判断 / トラブルシュート表 / 再現手順(Runbookの種) / 検証結果 / 学び(状況→結論→根拠→適用条件) / スキル証跡・タグ。
    → 技術ナレッジ・スキル証跡、手順書/Runbook、技術報告書/技術メモ の素材。
- 完了後、生成された整理情報のパスと要点をユーザーに提示する。
- 日付やプロジェクトを限定したい場合は引数を渡す:
  - 特定日・全プロジェクト: `summarize.py 2026-06-22`
  - 特定日・特定プロジェクト: `summarize.py 2026-06-22 jarvis`
  - 形式を絞る: `summarize.py --formats project 2026-06-22`

## 個別実行

- **収集のみ**: `bash "$SKILL/bin/collect.sh"`
  - 複数ソース（CLI / デスクトップ Code タブ）の生ログを構造抽出・マスキングして `raw/` へ。冪等。
- **分類のみ**: `python3 "$SKILL/bin/classify.py" [YYYY-MM-DD]`
  - cwd → git リポジトリ名 → 本文キーワードの順で `project_id` 確定。不明は `_unclassified`（誤分類より未分類優先）。
- **整理のみ**: `python3 "$SKILL/bin/summarize.py" [YYYY-MM-DD] [project] [--formats project,tech] [--dry-run]`
  - `claude -p` をヘッドレス実行し `digests/{project,tech}/` に整理情報を生成。`claude` が無い/失敗時はプロンプトを `.prompt.txt` に保存。
- **退避**: `bash "$SKILL/bin/archive.sh" [YYYY-MM] [--force] [--check]`

## 退避（破壊的操作 — 必ず確認してから）

`archive.sh` は整理済みの `raw/` `classified/` を `archive/YYYY-MM.zip` に圧縮し**元ファイルを削除**する
（zip 内には必ず残るので完全消失しない）。**実行前に必ずユーザーに確認する**こと。

```bash
# まず未整理チェック（退避しない）
bash "$SKILL/bin/archive.sh" --check 2026-05
# 問題なければ退避（当月より前の全月。月指定も可）
bash "$SKILL/bin/archive.sh" 2026-05
```

- 未整理ログ（digest 未生成）が残っていると既定で中断する。意図的に進める場合のみ `--force`。
- `_unclassified` は整理対象にしないことが多い。退避前に必要なら整理するか、`--force` で進める判断をユーザーに委ねる。

## 注意

- マスキングは collect 段階で適用済み（`config/redaction.yaml`）。整理情報の `<REDACTED:種別>` は復元しない。
- プロジェクトを増やすときは `config/projects.yaml` に、機密語を伏字化するときは `config/redaction.yaml` に追記。
- Web 版（claude.ai）はローカルにログが無いため収集対象外。
