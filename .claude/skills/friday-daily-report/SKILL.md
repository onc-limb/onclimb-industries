---
name: friday-daily-report
description: >-
  エンジニア個人の日次作業報告を Markdown と HTML の両形式で生成する。前回の報告作成時刻から
  今回までを対象窓とし、worklog のイベント・生ログ・ToDo 台帳を材料に、稼働時間・作業内容・
  進捗・課題・相談事項・翌営業日予定を対話で確定して固定テンプレートに落とす。
  「日次報告を作って」「今日の作業報告にして」「日報を出して」「作業報告資料にして」等で起動。
  日々の digest 生成は jarvis-worklog、プロジェクト単位の依頼者向け報告は将来の別スキルの領分。
model: sonnet
effort: medium
metadata:
  type: skill
  pairs_with: jarvis-worklog
  data_dir: <repo>/report-daily
---

# friday-daily-report — 個人の日次作業報告(Markdown + HTML)

**エンジニアとしての自分個人**の日次作業報告を生成する。読み手は報告先の管理者/PM
(準委任契約の精算・進捗管理の文脈。技術者向けなのでチケット番号・PR リンクは原語のまま載せる)。
フォーマットの一貫性は `bin/render_report.py`(決定論的レンダラー)が保証し、
エージェントは**材料の突き合わせ**と**対話での確定**に専念する。

> 2026-08-08 に役割を特化した。それ以前の「依頼者向け日次報告スライド」の資産
> (`bin/render_deck.py` / `templates/deck.html` / `config/glossary.yaml`、出力 `report-deck/`)は
> プロジェクト報告スキルを将来分離するまで残置(本スキルのフローからは使わない)。

## データ配置

- 出力: `<repo>/report-daily/<YYYY-MM>/<YYYY-MM-DD>.md` と同名 `.html`(常に両方生成)
- 作成履歴(ウォーターマーク): `<repo>/report-daily/.report-log.jsonl`
- 上書き: `REPORT_DAILY_DIR` 環境変数
- 入力(読み取りのみ): `worklog-data/events/` `worklog-data/raw/` `worklog-data/digests/`
  (jarvis-worklog)、`todo-data/todos.json`(jarvis-todo-management)

## 報告窓 — ウォーターマーク方式

固定の cutoff 時刻は持たない。**前回の報告作成時刻 〜 今回の作成時刻**が報告の対象窓。

- 報告を確定するたびに `.report-log.jsonl` に窓を追記し、次回はその終点から始める。
  取りこぼしも二重報告も構造的に発生しない。
- 金曜の報告作成後にやった作業は、次に報告を作った日(=翌営業日)の報告に自動的に入る。
  繰越の特別処理は不要。
- 報告日(`report_date`)は作成した当日。ヘッダに対象期間を明記するので、名目日付と
  実作業時刻のズレは読み手に伝わる。
- 初回(履歴なし)は当日 0:00 が始点になる。必要ならユーザーに確認して調整する。
- 作り直しは `window --redo`(直前の報告の始点から引き直す)。

## 標準フロー

```bash
SKILL=/Users/satoshi-onga/Documents/onclimb-industries/.claude/skills/friday-daily-report
```

1. **報告窓の確定**: `python3 "$SKILL/bin/report_tool.py" window`(作り直しは `--redo`)。
   窓(start〜end)と report_date をユーザーに提示。`mode` が `first` なら始点を確認する。
2. **材料集め**: `python3 "$SKILL/bin/report_tool.py" activity --start <S> --end <E>` で
   窓内の worklog イベント(骨格)と生ログの活動時刻を取得。当該日の
   `worklog-data/digests/` と `todo-data/todos.json`(必ず `todo.py list` 経由)も参照する。
3. **稼働時間の確定**(対話必須): activity の `first`/`last` を開始・終了の推定として、
   `gaps` を休憩候補として提示し、ユーザーに確定してもらう(ログは AI 作業時間しか
   映さないため、推定はあくまで叩き台。会議・レビュー等ログ外の稼働を必ず聞く)。
   **ユーザー確認前の推定値を報告に記載しない**(確定値のみ記載する)。
4. **作業内容の整理**: イベントの `did` をタスク単位にまとめ、
   **予定タスク(kind=planned)と突発タスク(kind=unplanned)に分類**する。
   - 予定の根拠は、前回報告の「翌営業日の予定」(window の `previous.out_md` を Read)・
     ToDo 台帳・朝会等での宣言。それ以外の当日発生分が突発。判断に迷うものは確認する。
   - 各タスクは「どのような作業をしたか(did)」「どういう結果・状況になったか(result)」を
     各 1〜2 行で簡潔に書く。**ファイル名・関数名・パスなど実装の具体は書かない**
     (日次報告の目的はタスクの量・内容・状況を伝えること。詳細は別ドキュメントの領分)。
     チケット番号と PR/チケット等の URL のみ紐付けてよい。
   - 記録に無い進捗を創作しない(不足は対話で確認)。
5. **対話で確定**: 以下を順に確認する。
   - 進捗: 各タスクの状態(完了/進行中/未着手/中断)、進行中は残作業見込み、
     当初予定とのズレとその理由
   - 課題・ブロッカー: worklog の blocker イベントを起点に、「誰の何を待っているか」
     「スケジュールへの影響」を補完
   - 相談・確認事項: 報告先にボールがあるもの。回答希望期限も
   - 決定事項・認識合わせ: 今日決まったこと・この認識で進める事項(認識齟齬の早期発見用)
   - 翌営業日の予定: ToDo 台帳の進行中/inbox から候補を提示して選んでもらう
   - その他連絡: 休暇予定・稼働変更など
6. **生成**: payload(スキーマは `render_report.py` の docstring 参照)を組み、
   `python3 "$SKILL/bin/render_report.py" --in payload.json` で md + html を生成。
   実稼働時間はレンダラーが start/end/breaks から自動計算する(手計算しない)。
7. **自己チェック**: [`personas/writing-style.md`](../../../personas/writing-style.md) の
   清書パス(ビジネス文書なので明確さ優先)。「調整を進めました」型の抽象表現でなく
   記録にある数字・固有の作業内容で書けているか。機密(顧客実名・キー類)が
   残っていないか。events の `<REDACTED:…>` は復元しない。
8. **確定**: ユーザーが内容を承認したら
   `python3 "$SKILL/bin/report_tool.py" commit --date <D> --start <S> --end <E> --md <path> --html <path>`
   でウォーターマークを進める。**承認前に commit しない**(破棄したら窓は進めない)。
9. **完了提示**: md(貼り付け用)と html(印刷・配布用)の両パスを提示する。

## 報告の構成(固定 — 崩さない)

ヘッダ(報告日・報告者・案件・対象期間)+ 8 セクション。空のセクションも「なし」で必ず出す。

1. 稼働情報(開始・終了・休憩・実稼働。準委任の精算根拠。ユーザー確定値のみ)
2. 進捗状況(タスク・区分(予定/突発)・状態・残作業見込み・予定とのズレの一覧表。
   先に全体像を見せてから詳細に入る)
3. 本日の作業内容(予定タスク → 突発タスクの 2 群。タスクごとに【作業】【結果】を簡潔に)
4. 課題・ブロッカー(待ち先・影響つき)
5. 相談・確認事項(報告先にボールがあるもの。回答希望期限つき)
6. 決定事項・認識合わせ
7. 翌営業日の予定
8. その他連絡

## デザイン方針(固定 — 崩さない)

- Markdown と HTML は同一 payload から生成し、内容を完全に一致させる(手で片方だけ直さない)。
- HTML は単一の自己完結文書(外部 CDN・フレームワーク依存なし)。寒色系ミニマル、印刷で A4。
- ステータスは色でなく語(「完了」「進行中」)で示す。
- レイアウト変更は `templates/report.html` の CSS と
  `<!-- SECTIONS_START/END -->` マーカーを直す。

## 注意

- worklog / todo のデータは**読み取りのみ**(書き込みは各スキルの CLI の領分)。
- worklog 側の events/raw のスキーマを変えるときは `report_tool.py` も同時に見直す。
- 稼働時間はログからの推定を無確認で確定しない(3. の対話を飛ばさない)。
  推定値がそのまま成果物に残るのは禁止。
- 作業内容にファイル名・関数名・パス等の実装詳細を書かない(タスク・作業・状況の粒度を保つ)。
- 過去日の報告を頼まれたら、まず `.report-log.jsonl` と `report-daily/` の既存出力を確認する
  (二重生成・窓の重複を避ける)。
