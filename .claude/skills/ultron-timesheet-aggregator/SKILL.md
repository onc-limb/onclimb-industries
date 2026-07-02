---
name: ultron-timesheet-aggregator
description: 散在する稼働の手がかり（jarvis-worklog の分類済みログ worklog-data/ や Google カレンダー(MCP)）から、案件別・日別の稼働時間サマリを作る集計スキル。Claude はソースの読み取りとエントリの案件分類（確証がなければ「未分類」に倒す）だけを担い、時間の合算・案件別/日別内訳・重複警告は決定論的スクリプト(scripts/aggregate.py)が計算する（LLM は合計値を暗算しない）。出力は timesheet-data/ 配下の月次エントリ JSON と稼働サマリ Markdown（案件別・日別の稼働表、未分類とソース内訳の明示、警告付き）で、請求書作成スキル（ultron-invoice-builder）の入力になり得る。「今月の稼働時間を集計して」「6月の案件別稼働サマリを出して」「worklogとカレンダーから稼働表を作って」「請求書用に今月の稼働内訳をまとめて」「先月、○○案件に何時間使ったか出して」等で、ユーザーが明示的に依頼したときだけ起動する（自動起動しない）。出力は稼働の情報整理であって、勤怠の公式記録や請求書そのものではない。worklog（ログ整理）・record（作業記録）とは別系統。
metadata:
  type: skill
  data_dir: <repo>/timesheet-data
---

# timesheet-aggregator — 案件別稼働時間の集計スキル

worklog・カレンダーに散在する稼働の手がかりを集め、**案件別・日別の稼働サマリ**を作る。
SES 参画中のフリーランスが、月次の稼働報告・請求書作成（ultron-invoice-builder の入力）の
下ごしらえとして使う。

> **位置づけ**: 出力は稼働の**情報整理**であって、勤怠の公式記録・請求書そのものではない。
> worklog 由来の時間は**推定**を含むため、請求に使う前に必ず本人が確認する。

## 場所（コードとデータは分離されている）

- ツール本体: このスキルディレクトリ `.claude/skills/ultron-timesheet-aggregator/`（`scripts/`）
- **データ**: スキルが属する git リポジトリ直下の `timesheet-data/`
  - `entries/<YYYY-MM>.json` … 分類済みエントリ（集計の入力・検算の根拠）
  - `summaries/<YYYY-MM>.md` … 稼働サマリ（成果物）
  - **(ASSUMPTION: データ置き場は worklog-data/ / stock-data/ と同じ「repo 直下 + 環境変数
    `TIMESHEET_DATA` で上書き可」の慣習に合わせた。稼働情報は案件名を含み機密になり得るため、
    他のデータディレクトリと同様に root `.gitignore` へ `/timesheet-data/` を追加して運用する)**

## 役割分担（重要）

集計値の捏造・計算ミスを構造的に防ぐため、**分類は Claude、合算はスクリプト**に分ける。

- **Claude（あなた）**: ソース（worklog-data/ の分類済みログ、Google カレンダー MCP）の読み取り、
  エントリへの案件 ID 付与（分類）、エントリ JSON の整形、サマリへの注記・根拠の記述。
- **スクリプト（決定論）**: `scripts/aggregate.py` が時間の合算（案件別 / 日別 / 案件×日 /
  ソース別）、重複疑い・日合計 24h 超の警告、未分類時間の算出を行う。

→ **Claude は合計値・構成比を自分で計算して書かない**。サマリに載せる数値はすべて
`aggregate.py` の出力から転記する。分類に確証がなければ案件を推測せず `unclassified`（未分類）に倒す
（worklog の「誤分類より未分類優先」と同じ方針）。

## トリガーと対応フロー

ユーザーが明示的に依頼したときだけ起動する（自動起動しない）。

| ユーザー発話の例 | 実行する標準フロー |
|---|---|
| 「今月の稼働時間を集計して」「稼働サマリ出して」 | 標準フロー（期間: 当月、全案件、worklog + カレンダー） |
| 「6月の案件別稼働サマリを出して」 | 標準フロー（期間を発話から確定） |
| 「worklogとカレンダーから稼働表を作って」 | 標準フロー（ソースを発話から確定） |
| 「請求書用に今月の稼働内訳をまとめて」 | 標準フロー + 請求前チェック（未分類ゼロ・警告ゼロを確認） |
| 「先月、○○案件に何時間使ったか出して」 | 標準フロー（対象案件を絞る） |
| 「この稼働表、未分類を振り直して再集計して」 | 再分類フロー（entries JSON を修正 → aggregate.py 再実行） |

## 標準フロー

```bash
SKILL=/Users/satoshi-onga/Documents/onclimb-industries/.claude/skills/ultron-timesheet-aggregator
DATA=/Users/satoshi-onga/Documents/onclimb-industries/timesheet-data   # TIMESHEET_DATA で上書き可
```

1. **期間と案件の確認**: 対象期間（既定: 当月 1 日〜今日）、対象案件（既定: 全案件）、
   ソース（既定: worklog + カレンダー）を発話から確定する。曖昧なら**集計前に必ずユーザーに確認**する
   （期間がズレた集計は請求事故につながるため）。
2. **ソース収集**:
   - **worklog**: `worklog-data/classified/<project>/<date>.jsonl` の各セッションについて、
     ログのタイムスタンプ（`ts`）から日ごとの稼働時間を推定する。
     **(ASSUMPTION: 推定ルール — 同一セッションのログを時系列に並べ、隣接ログの間隔が
     30 分以内なら連続稼働とみなして合算、30 分超の空白は稼働に数えない。1 区間の最低単位は
     0.25h。worklog 側に確定した稼働時間フィールドは無いため、この推定である旨を必ずサマリに明記する)**
   - **カレンダー**: Google カレンダー MCP（`list_events`）で期間内のイベントを取得し、
     開始/終了時刻から時間数を算出する。**(ASSUMPTION: 終日イベント・辞退済みイベントは
     稼働に数えない。移動・私用と判別できるイベントは除外する)**
   - MCP が使えない/カレンダー不要の場合は worklog のみで続行し、その旨をサマリに明記する。
3. **分類（Claude）**: 各エントリに案件 ID を付与する。
   - worklog 由来は `project_id` をそのまま使う（`_unclassified` は `unclassified` に写す）。
   - カレンダー由来はタイトル・参加者・時間帯から判断する。**確証がなければ `unclassified`**。
   - 案件 ID は worklog の `config/projects.yaml` の `id` に揃える
     **(ASSUMPTION: worklog と同じ ID 体系を使うことで invoice 側との突合を単純にする)**。
   - **重複排除（ソース間）**: 同一日・同一案件で worklog とカレンダーの時間帯が重なる場合は
     二重計上になるため、**カレンダー（実測の予定時間）を優先し、重なる worklog 推定分は採用しない**
     **(ASSUMPTION: カレンダーは開始/終了が明示的で worklog 推定より信頼できるとみなす)**。
     採用しなかった側はエントリに含めず、サマリの注記に「重複のため除外」と記録する。
4. **エントリ JSON 化 → スクリプトで集計（決定論）**: 分類済みエントリを
   `timesheet-data/entries/<YYYY-MM>.json` に保存し、`aggregate.py` に渡す。
   ```json
   [
     {"date": "2026-07-01", "project": "climbinsight", "hours": 3.5, "source": "worklog"},
     {"date": "2026-07-01", "project": "unclassified",  "hours": 1.0, "source": "calendar"}
   ]
   ```
   ```bash
   python3 "$SKILL/scripts/aggregate.py" --file "$DATA/entries/2026-07.json" \
     --round-to 0.25 --format json        # 集計結果（JSON）
   python3 "$SKILL/scripts/aggregate.py" --file "$DATA/entries/2026-07.json" \
     --round-to 0.25 --format markdown    # サマリ用の表（Markdown）
   ```
   **(ASSUMPTION: 丸め単位は 15 分 = `--round-to 0.25` を既定とする。契約の単位が違う場合は
   ユーザー指定で変える)**。エントリ内容の完全重複は警告されるので、意図した重複でなければ
   `--dedupe` で除去する。
5. **サマリ生成**: `--format markdown` の出力を土台に `timesheet-data/summaries/<YYYY-MM>.md` を
   作成し、以下を必ず添える:
   - 期間・ソース内訳・生成日
   - worklog 由来は**推定**である旨と推定ルール
   - `aggregate.py` の警告（重複疑い / 日合計 24h 超 / 未分類あり）と対処の提案
   - 検算方法（`entries/<YYYY-MM>.json` を `aggregate.py` に再投入すれば同じ数値になる）
6. **完了提示**: 総稼働・案件別上位・未分類時間・警告件数を要約し、サマリのパスを提示する。
   未分類が残っている場合は振り直し（再分類フロー）を提案する。

## 出力フォーマット（summaries/<YYYY-MM>.md）

`aggregate.py --format markdown` が生成する固定構造に、Claude が注記を加える。

- **ヘッダ**: 期間 / 総稼働 / エントリ件数 / 稼働日数 / 未分類時間 / ソース内訳
- **案件別合計**: `| 案件 | 稼働時間 (h) | 構成比 |` の表。未分類は `**(未分類)**` として**必ず行を残す**
  （こっそり案件に混ぜない）。
- **日別 × 案件別**: 日付を行・案件を列にした稼働表（日合計付き）。
- **警告 (要確認)**: 重複疑い・日合計 24h 超・未分類あり・未知ソース。
- **注記（Claude が追記）**: 推定/実測の別、ソース間の重複除外の記録、検算手順、
  「本書は情報整理であり公式な勤怠記録・請求書ではない」旨。

## 個別実行

- **集計のみ（JSON）**: `python3 "$SKILL/scripts/aggregate.py" --file <entries.json>`
- **集計のみ（Markdown 表）**: `... --format markdown`
- **標準入力から**: `python3 "$SKILL/scripts/aggregate.py" --stdin <<< '<JSON配列>'`
- **丸め**: `--round-to 0.25`（15 分単位。エントリ単位で四捨五入）
- **完全重複の除去**: `--dedupe`（date+project+hours+source が同一のものを 1 件に）
- 入力不正（日付形式・hours ≦ 0・24h 超など）は exit 2 + stderr にエラー JSON。

## 品質・安全性（persona: ultron）

- **数値の根拠**: サマリの全数値は `aggregate.py` の出力からの転記であり、入力
  `entries/<YYYY-MM>.json` を残すことで**誰でも再計算・検算できる**。推定（worklog 由来）は
  推定であることを明示し、実測（カレンダー由来）と区別する。
- **機密・個人情報**: サマリ・エントリ JSON には**案件 ID と時間数のみ**を記録し、
  カレンダーのイベントタイトル・参加者名・顧客名・個人名の原文を転記しない。
  worklog 側のマスキング（`<REDACTED:種別>`）は復元しない。案件 ID 自体も顧客名を避けた
  汎用 ID（worklog の projects.yaml 方針）を使う。
- **免責（サマリに毎回明記）**: 本出力は稼働の情報整理であって、公式な勤怠記録・請求書ではない。
  請求・報告に使う前に本人が一次情報（カレンダー・契約条件）で再確認する。
- **invoice-builder との連携**: `entries/<YYYY-MM>.json`（構造化データ）と
  `summaries/<YYYY-MM>.md`（案件×時間の表）は、請求書作成スキル（ultron-invoice-builder）の
  入力（稼働時間）になることを想定した形にしてある。請求前チェックとして
  「未分類 0h・警告 0 件」を目安にし、そのうえで案件別合計を invoice 側へ渡す。

## 注意

- 期間の既定は「当月」だが、月初に「今月」と言われた場合など曖昧なときは必ず確認する。
- 同じ月を再集計するときは `entries/<YYYY-MM>.json` を**上書き**する（追記すると重複計上になる）。
  過去分を残したい場合はユーザーに確認してからリネーム退避する。
- `aggregate.py` は python3 標準ライブラリのみで動く（追加依存なし）。
