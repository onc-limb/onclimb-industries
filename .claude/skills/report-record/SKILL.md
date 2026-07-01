---
name: report-record
description: 依頼者向け報告の一次記録スキル(2段階のStage1)。worklog の project digest を入力に、案件ごと・対応日ごとの「作業記録」を Markdown で積み上げる。digest と前日までの記録を読み、足りない情報は対話でヒアリングしてから、固定見出し(取り組んだ課題 / やったこと / 今どうなっているか / 検討したが採用しなかった案 / 障害 / この先 / 相談)で記録する。「今日の作業を案件ごとに記録して」「worklog の整理を報告用に落とし込んで」「<案件>の今日の分を記録して」等で起動。技術者が読める正確な一次記録(信頼の源泉)を作るのが目的で、脱専門用語の清書は後段の report-deck が担う。
metadata:
  type: skill
  stage: 1
  pairs_with: report-deck
  data_dir: <repo>/report-record
---

# report-record — 依頼者向け報告の一次記録 (Stage 1)

worklog の「プロジェクト整理情報(project digest)」を、**案件×対応日の作業記録(Markdown)**へ
落とし込むスキル。後段の [report-deck](../report-deck/) がこの記録を入力に、非エンジニア向けの
日次報告スライドへ清書する。本スキルは**事実の正確な一次記録**を担い、用語の言い換えはしない。

> 位置づけ: worklog digest = 技術者向けの網羅的整理。本スキルの記録 = 報告に向けて
> 案件×日付で構造化した一次記録。report-deck = それを依頼者言語に清書した配布物。

## データ配置

- 記録: `<repo>/report-record/<project>/<YYYY-MM-DD>.md`(案件ごとにディレクトリ → 日付ごとにファイル)
- 入力の worklog digest: `<repo>/worklog-data/digests/project/<project>_<date>.md`
- 上書き: `REPORT_RECORD_DIR` / `WORKLOG_DATA` 環境変数

## トリガー

| ユーザー発話の例 | 動作 |
|---|---|
| 「今日の作業を案件ごとに記録して」 | 当日の全案件を記録 |
| 「worklog の整理を報告用に落とし込んで」 | digest を記録へ変換 |
| 「<案件>の今日の分を記録して」 | 案件を限定して記録 |
| 「6/25 の分を記録して」 | 日付を限定 |

## 標準フロー

```bash
SKILL=/Users/satoshi-onga/Documents/onclimb-industries/.claude/skills/report-record
TODAY=$(date +%F)
python3 "$SKILL/bin/locate.py" "$TODAY"        # 入力(digest/前日記録/出力先)を JSON で取得
```

1. **入力をロケート**: `locate.py <date> [project]` を実行。対象案件ごとに、worklog digest・
   前日までの記録・出力先パス・`is_unclassified` フラグが返る。
2. **`_unclassified` の確認**: `is_unclassified: true` の案件があれば、**報告に含めるか都度ユーザーに確認**
   (`AskUserQuestion`)。含めない場合はその案件をスキップ。
3. **入力を読む**: 各案件について digest(主入力)と `prev_record`(あれば前日の記録)を Read。
   前日の「この先やること」と当日 digest の作業内容を突き合わせ、継続タスクの文脈をつなぐ。
4. **不足のヒアリング**: digest だけで埋まらない項目を `AskUserQuestion` で確認する。例:
   - 依頼者からの口頭フィードバック・対外的なやり取り
   - digest が「判断待ち: なし」のとき、本当に相談事項が無いか
   - 「検討したが採用しなかった案」の理由が digest に薄いとき
   **digest に無い事実を創作しない。** 埋まらない欄は「なし」/「記録なし」と書く。
5. **記録を生成**: `templates/record.md` の見出し構成で `record_out` のパスに Write する。
   - 見出しは固定(増減しない): 取り組んだ課題 / やったこと / 今どうなっているか /
     検討したが採用しなかった案（と見送った理由）/ 障害・つまづき / この先やること / 依頼者への相談・判断待ち
   - 「やったこと」の各項目に `[完了]` / `[進行中]` / `[着手のみ]` / `[中断]` を付ける
   - 末尾 meta コメントに `source`(digest パス)・`prev`・`heard`(ヒアリングで補った項目)を残す
   - **この段階では専門用語を残してよい**(清書は report-deck の責務)
6. **完了提示**: 生成パスと、report-deck へ渡せる状態か(障害・相談事項の有無)を要約して提示。

## テンプレート

`templates/record.md` を見出しの正とする。見出しの順番・文言は変更しない(report-deck が
この構造に依存する)。digest の各セクションとの対応:

| 記録の見出し | worklog digest の出どころ |
|---|---|
| 取り組んだ課題 | 目的・背景 + 前日記録の「この先やること」 |
| やったこと | 作業内容(進捗ステータス付き) |
| 今どうなっているか | 最終的にどうしたか |
| 検討したが採用しなかった案 | 作業内容内の不採用案 / 判断根拠 |
| 障害・つまづき | つまづき・問題(Problem) |
| この先やること | 次の予定・次への改善(Next/Try) |
| 依頼者への相談・判断待ち | 課題・判断待ち |

## 注意

- worklog 未実行で当日 digest が無ければ、先に worklog の「まとめて」を促す。
- 機密はマスキング済み digest を前提とする。記録に実名・顧客名を新たに書き起こさない。
- 学習: ヒアリングで繰り返し問う項目が出てきたら、本ファイルの「不足のヒアリング」例に追記して育てる。
