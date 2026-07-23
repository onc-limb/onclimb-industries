---
name: jarvis-worklog
description: 作業記録システム。Claude Code の会話・ツール操作ログを収集→分類→「整理された情報」2形式（プロジェクト視点 / 技術者視点）に整理→アーカイブ退避する。「作業ログ」「まとめて」「作業報告」「進捗報告」「整理して」「技術整理」「今日の作業をまとめて」「6/28 の作業をまとめて」「昨日の分を整理して」等で起動（日付指定に対応。対象日は既定で当日、指定があればその日付で collect → classify → summarize を回す）。出力は最終報告書そのものではなく、後段の別スキルがきちんとした報告書へ整形するための詳細な整理情報。SES 参画中の作業報告・ナレッジ蓄積のために、最終成果物だけでなく「何を考え・何を試したか」という過程を残す。生ログは削除せず zip 退避するため消失しない。
model: sonnet
metadata:
  type: skill
  data_dir: <repo>/worklog-data
---

# worklog — 作業記録スキル

このスキルディレクトリ内の `bin/` ツール群を自然言語から呼び出すスキル。
収集（記録）は Hooks / cron で自動化できるが、未設定の環境でも標準フロー先頭の
collect（カーソル方式・冪等）が未取り込み分を日付を問わず遡って回収する。
このスキルが担うのは主に**収集 → 分類 → 整理 → 退避** の半自動オペレーションと、個別ツールの実行。

> **位置づけ**: このスキルが生成するのは「報告書を書くための整理された情報（digest）」であって、
> 最終報告書そのものではない。プロジェクト視点・技術者視点の 2 形式で過程を網羅的に構造化し、
> 後段の別スキルがこの digest を入力にきちんとした報告書へ整形する、という二段構えを想定している。

## 場所（コードとデータは分離されている）

- ツール本体・設定: このスキルディレクトリ `.claude/skills/jarvis-worklog/`（`bin/` `config/` `templates/`）
- 設定: `config/{sources,projects,redaction}.yaml`
- **データ**: スキルが属する git リポジトリ直下の `worklog-data/`
  （`raw/` `classified/` `digests/` `archive/` `logs/`）。`WORKLOG_DATA` 環境変数で上書き可。
- 実行はスキルディレクトリの絶対パスを `SKILL` に入れて bin を呼ぶ。スクリプトが配置場所から
  自動で config/templates を解決し、データ置き場（`worklog-data/`）も自動算出する。

## トリガーと対応フロー

| ユーザー発話の例 | 実行する標準フロー |
|---|---|
| 「今日の作業まとめて」「作業報告して」「整理して」 | 標準フロー（対象日 = 当日） |
| 「6/28 の作業をまとめて」「昨日の分を整理して」「先週金曜のログ取って」 | 標準フロー（対象日 = 指定日。相対表現は実行日から解決し、確定した日付を復唱する） |
| 「プロジェクト視点でまとめて」 | summarize の `--formats project` |
| 「技術整理して」「技術的にまとめて」 | summarize の `--formats tech` |
| 「ログ集めて」「収集して」 | collect のみ |
| 「分類して」 | classify のみ |
| 「手動メモ: <内容>」「手動でやったのでメモして」 | 手動操作の申告メモを追記（下記） |
| 「古いログを退避して」「アーカイブして」 | archive（**実行前に必ず確認**） |

## 標準フロー（「まとめて」の一声で対象日分を整理情報まで）

対象日 `DATE` は既定で当日。ユーザーが日付を指定したらその日付を使う（複数日は 2〜4 を日付ごとに繰り返す）。

```bash
SKILL=/Users/satoshi-onga/Documents/onclimb-industries/.claude/skills/jarvis-worklog
DATE=$(date +%F)   # 日付指定があれば DATE=2026-06-28 のように置き換える
bash   "$SKILL/bin/collect.sh"                 # 1) 取りこぼし収集（冪等。過去日の未取り込み分もここで raw/ に遡って入る）
python3 "$SKILL/bin/classify.py" "$DATE"       # 2) 対象日を分類（①②決定論→③LLM/Haiku→④keyword fallback）
python3 "$SKILL/bin/suggest_projects.py" "$DATE"  # 3) 未分類に未登録プロジェクトが無いか調査
python3 "$SKILL/bin/summarize.py" "$DATE"      # 4) 2形式の整理情報を生成
```

> **過去日でも必ず collect から始める**。`raw/<日付>.jsonl` が無いと classify が「対象 raw なし」で
> 空振りするが、その日付の生ログが CLI 側に残っていれば collect が遡って取り込む。
> CLI の生ログ保持期間を過ぎた日付は遡れない（既に `raw/` へ収集済みの日付はいつでも処理できる）。
> `raw/` に無く収集でも取れなかった場合は「その日のログは残っていない」と正直に報告する。

> **再実行は差分スキップで速い**: classify は内容が変わらない classified ファイルを触らず（mtime 保持）、
> summarize は digest が classified より新しければ生成をスキップする。したがって標準フローを
> 何度回しても、新しいログが増えた分だけが再生成される。意図的に作り直したいとき
> （テンプレ変更後など）だけ `summarize.py --force` を使う。

### 未分類プロジェクトの調査と登録（classify と summarize の間に挟む）

classify は「誤分類より未分類優先」のため、`config/projects.yaml` に未登録のプロジェクトは
`_unclassified` に落ちる。LLM 判定（③）でも既知プロジェクトに当てられなかった＝**未登録の新規プロジェクトの
可能性が高い**ので、放置せず登録の要否を必ず確認する。放置すると本来別プロジェクトの作業が未分類に埋もれ、
報告の取りこぼしになる。そこで **summarize の前に未分類を調査し、新しいプロジェクトなら projects.yaml に
登録して再分類する**。`_unclassified` が空なら本節はスキップしてよい。

1. `suggest_projects.py [date]` を実行する。`_unclassified` を cwd / git リポジトリ単位で集計し、
   projects.yaml 未登録の候補（`suggested_id` / `path_glob` / `repo` / `entries` / `sample_bodies`）を JSON で返す。
2. 候補があれば **Claude が調査する**: 候補の `cwds`（や `path_glob`）の README / package.json / git remote 等を
   読み、適切な `id`（顧客名は避け汎用 id・マスキング前提）を判断する。`id_conflict: true` は既存 id と
   衝突するので別名にする。`is_git_repo: false` や一過性の作業ディレクトリは登録を見送ってよい。
3. **ユーザーに確認**（`AskUserQuestion`）: 「この cwd を `<id>` として登録してよいか / 見送るか」。
   勝手に登録せず、id の妥当性を必ず確認する。
4. 合意したら `config/projects.yaml` に 1 ブロック追記（`id` / `path_globs` / `repos` / `keywords`）。
5. `classify.py [date]` を再実行して `_unclassified` から正しい `project_id` へ振り直す。
6. その後 `summarize.py` に進む（正しいプロジェクト名で digest が生成される）。

> 既に digest を生成済みの日を後から登録し直した場合は、旧 `_unclassified`（や誤った id）の
> digest が残る。`classify.py [date]` 再実行後に該当日の digest を作り直し、古い digest は削除する。

- 生成物は `worklog-data/digests/{project,tech}/<project>_<date>.md`（＝報告書の素材となる整理情報）。
  各 digest は結論層（TL;DR/サマリ）と詳細層を両方持ち、用途別に出し分けられるよう設計してある:
  - `project` … プロジェクト視点。TL;DR / 成果サマリ(上長・顧客向け) / 作業(進捗ステータス付) / Keep / Problem / 次の予定・Try / 課題・判断待ち。
    → 進捗報告書・作業報告書、上長/顧客向けサマリ、振り返り(レトロ) の素材。
  - `tech` … 技術者視点。TL;DR / 技術選定と判断 / トラブルシュート表 / 再現手順(Runbookの種) / 検証結果 / 学び(状況→結論→根拠→適用条件) / スキル証跡・タグ。
    → 技術ナレッジ・スキル証跡、手順書/Runbook、技術報告書/技術メモ の素材。
- 完了後、生成された整理情報のパスと要点をユーザーに提示する。
- **ToDo 台帳とのバッチ突き合わせ**（jarvis-todo-management との連携。取りこぼし回収）:
  digest 提示後に `todo-data/todos.json` と突き合わせる。
  1. digest の「作業内容」にあるのに台帳に無い作業は、`todo.py add --source-type worklog
     --source-ref <digest パス> --status done` で事実として自動追記し、一言通知する。
     台帳にあるものは `start` / `done` で状態を更新する。
  2. digest の「次の予定・次にやること」「課題・判断待ち」は `--status inbox` で収穫する
     （コミットメントにするかは todo 側の棚卸しで確定。追記のたびに一言通知）。
  手順の詳細は jarvis-todo-management の SKILL.md（フロー C / F）を参照。台帳が無い環境ではスキップしてよい。
- 日付やプロジェクトを限定したい場合は引数を渡す:
  - 特定日・全プロジェクト: `summarize.py 2026-06-22`
  - 特定日・特定プロジェクト: `summarize.py 2026-06-22 onclimb-industries`
  - 形式を絞る: `summarize.py --formats project 2026-06-22`

## 個別実行

- **収集のみ**: `bash "$SKILL/bin/collect.sh"`
  - 複数ソース（CLI / デスクトップ Code タブ）の生ログを構造抽出・マスキングして `raw/` へ。冪等。
- **分類のみ**: `python3 "$SKILL/bin/classify.py" [YYYY-MM-DD] [--no-llm]`
  - ①cwd → ②git リポジトリ名（決定論）→ ③LLM 判定（`claude -p`/Haiku, ①②を外したセッションのみ）
    → ④本文キーワード部分一致（LLM 不在/失敗/`--no-llm` 時の fallback）の順で `project_id` 確定。
    不明は `_unclassified`（誤分類より未分類優先）。LLM は確信が低ければ「未分類」に倒す。
  - `--no-llm`: LLM を使わず決定論+キーワードのみ（cron 無人運用・検証・オフライン時）。`claude` が
    無ければ自動で fallback する。
- **未分類の調査（プロジェクト登録の提案）**: `python3 "$SKILL/bin/suggest_projects.py" [YYYY-MM-DD]`
  - `_unclassified` を cwd / git リポジトリ単位で集計し、projects.yaml 未登録の候補を JSON で返す（**読み取り専用**）。
  - 出力を受けて Claude が候補を調査・確認し、ユーザー合意のうえ `config/projects.yaml` を編集して再分類する。
    手順は「標準フロー」の『未分類プロジェクトの調査と登録』を参照。
- **整理のみ**: `python3 "$SKILL/bin/summarize.py" [YYYY-MM-DD] [project] [--formats project,tech] [--force] [--dry-run]`
  - `claude -p`（`--model sonnet`＝現行 Sonnet に追従）をヘッドレス実行し `digests/{project,tech}/` に整理情報を生成。`claude` が無い/失敗時はプロンプトを `.prompt.txt` に保存し、失敗があると exit 1 で終わる。
  - project / tech の両形式が対象のときは **1 回の claude 呼び出しで両形式を出力**させ、区切り行で分割して保存する（呼び出し回数半減）。区切りの分割に失敗した場合は生出力を `.raw*.txt` に保存して失敗扱いにする。
  - **差分スキップ**: 既存 digest が classified より新しければ生成しない。`--force` で無効化。
  - tool_result（ツール実行の生出力）は情報密度が低いので先頭/末尾のみ残して圧縮する。
  - 1 ファイルのログが上限（`MAX_LOG_CHARS`）を超える場合は、時系列のまま文字数ベースで時間帯分割し、各時間帯の整理を `## 【時間帯 i/n: HH:MM–HH:MM】` 見出しで 1 ファイルに連結する（各時間帯は H1 と冒頭の TL;DR/成果サマリを持たず、`##` 見出しから始まる）。
  - 時間帯分割した digest には、band 間で同じ作業が重複・食い違っていないかを検知した
    `## 【時間帯間の重複・矛盾（jarvis-record での突き合わせ用）】` セクションを冒頭に自動生成する
    （並行セッションが別 band に分かれると同一作業が別内容で書かれうるため）。これは「ユーザーに
    確認する候補」であり正誤は判定しない。解消は jarvis-record の確認サイクルが行う。
  - ログに無い情報は「記録なし」に加えて可能なら欠損の型を添える（`記録なし（セッション中断）` /
    `記録なし（ユーザー手動・ログ外）` / `記録なし（背景の記載なし）`）。下流の jarvis-record が
    ヒアリングの聞き方を変えるために使う。
  - 複数の整理を並列生成する。同時数は環境変数 `WORKLOG_SUMMARIZE_CONCURRENCY`（既定 4）で調整可能。上げるほど速いが Max プランのレート枠に当たりやすくなる。
- **退避**: `bash "$SKILL/bin/archive.sh" [YYYY-MM] [--force] [--check]`

## 夜間の先回り実行（推奨の自動化）

`bin/nightly.sh` が collect →（raw が更新された日だけ）classify → summarize を無人で回す。
毎晩これを動かしておくと digest が常に先回りで生成済みになり、日中の「まとめて」は
未分類プロジェクトの確認と ToDo 突き合わせだけで**ほぼ即答**になる。

- セットアップ: `deploy/com.user.worklog.nightly.plist`（launchd。毎日 23:50）を使う。
  手順は plist 冒頭のコメント参照。cron 派は `deploy/crontab.sample` のオプション節。
  **collect 単体の plist（com.user.worklog.collect.plist）とは併用しない**（nightly が collect を内包）。
- 処理済み管理は `worklog-data/logs/nightly/<日付>.stamp`。classify と summarize が両方成功した日だけ
  stamp を更新し、失敗した日は翌晩に再試行する（差分スキップがあるので再試行は安い）。
- 夜間に生成された `_unclassified` の digest は、後日プロジェクト登録して再分類すると
  classified が変わり、次の summarize で自動的に作り直される（標準フローの注意書きどおり
  古い digest の削除だけ忘れないこと）。
- ログ: `/tmp/worklog-nightly.log`。

## 手動メモ（ログに写らない作業の申告口）

本番への手動適用・手動検証など、Claude のツール操作として残らない作業は収集の限界で
digest に写らない。ユーザーが「手動メモ: <内容>」と言ったら、その場で
`worklog-data/manual/<YYYY-MM-DD>.md` に 1 行追記する（無ければ作成）:

```
- HH:MM [<project_id>] <内容そのまま>
```

- project が特定できなければ `[?]` として残す（分類はしない。誤分類より未分類優先）。
- このメモは jarvis-record が④の入力（locate.py の `manual_notes`）として拾い、
  記録の「手動で実施した操作」欄の原料になる。
- あくまで申告の受け皿であり、書き漏れは仕組みでは埋まらない。手動作業をしたら
  その場で一言メモする運用習慣とセットで機能する。

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

- **原料保全**（personas/jarvis.md）: digest はきれいな要約より情報の保全を優先する。
  つまずき・エラー原文・試行錯誤・不採用案は「些末」として要約で潰さない
  （Problem / トラブルシュート表 / 検証結果は、下流の jarvis-record・friday 系の品質を決める原料）。
- マスキングは collect 段階で適用済み（`config/redaction.yaml`）。整理情報の `<REDACTED:種別>` は復元しない。
- プロジェクトを増やすときは `config/projects.yaml` に、機密語を伏字化するときは `config/redaction.yaml` に追記。
- Web 版（claude.ai）はローカルにログが無いため収集対象外。
