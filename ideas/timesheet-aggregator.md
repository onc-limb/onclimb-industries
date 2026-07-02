---
name: timesheet-aggregator
status: shipped  # draft | refining | ready | building | shipped | dropped
created: 2026-07-02
updated: 2026-07-02
tags: [timesheet, worklog, calendar, aggregation, freelance, ses, invoice, admin]
related: [invoice-builder, work-log-system-instructions.md]
---

# timesheet-aggregator (案件別稼働時間の集計スキル)

> SES 参画中のフリーランスエンジニアが、月次の稼働報告・請求書作成の前に、
> worklog・カレンダーに散在する稼働の手がかりを**案件別・日別の稼働サマリ**へ
> 1 コマンドで集約するためのスキル。分類は Claude、時間の合算は決定論スクリプトが担う。

---

## 場面 (When)

ユーザーが**意図的に起動**する（自動起動しない）。

- 月末・月初に「今月（先月）の稼働時間を集計して」と頼んだとき
- 請求書を作る前に「請求書用に稼働内訳をまとめて」と下ごしらえを頼んだとき
- 特定案件の稼働を確認したくて「○○案件に何時間使った？」と聞いたとき
- worklog の整理（jarvis-worklog）を回した後、「これを稼働表に落として」と続けたとき
- 生成済みの稼働表に対し「未分類を振り直して再集計して」と修正を頼んだとき

### 想定トリガー文 (実際のユーザー発話例)

1. 「今月の稼働時間を集計して」
2. 「6月の案件別稼働サマリを出して」
3. 「worklogとカレンダーから稼働表を作って」
4. 「請求書用に今月の稼働内訳をまとめて」
5. 「先月、climbinsight に何時間使ったか出して」
6. 「日別の稼働を表にして」
7. 「この稼働表、未分類を振り直して再集計して」

> 起動の明示性: description は「稼働時間の集計・案件別サマリ」に限定し、
> worklog（ログ整理）・record（作業記録）と誤起動しないようにする。

---

## 解決する課題 (Problem)

- 現状: 稼働時間の手がかりが worklog のログ（`worklog-data/classified/`）、Google カレンダーの
  予定、記憶の 3 か所に散在しており、月次の稼働報告・請求のたびに手作業で突き合わせて
  Excel 等に転記している。案件をまたぐ日は「どの案件に何時間か」の振り分けも目視。
- 痛みの種類: 時間（毎月の転記・突き合わせ）/ 認知負荷（どこまで拾ったか）/
  見落とし・重複（同じ稼働を二重計上、拾い漏れ）/ 手戻り（請求後に数字が合わない）
- 影響範囲: 個人作業だが、成果物（稼働報告・請求書）はクライアントに出るため、
  **数字の誤りは信用と金額に直結**する。

---

## 解決策 (Solution)

集計値の捏造・計算ミスを構造的に防ぐため、**ソース読み取り・案件分類は Claude、
時間の合算・内訳計算は決定論スクリプト**に分ける（high-dividend-stock-screener の
「取得は Claude / 判定はスクリプト」と同じ思想）。

1. **期間と案件の確認**: 対象期間（既定: 当月）・対象案件（既定: 全案件）・ソース
   （既定: worklog + カレンダー）を発話から確定。曖昧なら集計前にユーザーに確認する。
2. **ソース収集**: worklog は `worklog-data/classified/<project>/<date>.jsonl` の
   タイムスタンプから日ごとの稼働を推定 **(ASSUMPTION: 隣接ログ間隔 30 分以内を連続稼働と
   みなす推定ルール。worklog に確定稼働時間フィールドは無いため推定である旨を出力に明記)**。
   カレンダーは Google カレンダー MCP（`list_events`）でイベントの開始/終了から時間数を算出
   **(ASSUMPTION: 終日・辞退済みイベントは稼働に数えない)**。
3. **分類（Claude）**: 各エントリに案件 ID（worklog の `config/projects.yaml` の id 体系）を
   付与。**確証がなければ `unclassified`（未分類）に倒す**（誤分類より未分類優先）。
   worklog とカレンダーで時間帯が重なる分は二重計上を避けるためカレンダー優先で片方のみ採用
   **(ASSUMPTION: 開始/終了が明示的なカレンダーを worklog 推定より信頼できるとみなす)**。
4. **集計（決定論スクリプト）**: エントリ JSON を `timesheet-data/entries/<YYYY-MM>.json` に
   保存し、`scripts/aggregate.py` が案件別 / 日別 / 案件×日 / ソース別の合計、未分類時間、
   警告（完全重複・日合計 24h 超・未知ソース）を計算する。Claude は合計値を暗算しない。
5. **サマリ生成**: スクリプトの Markdown 出力を土台に `timesheet-data/summaries/<YYYY-MM>.md` を
   生成。推定/実測の別・重複除外の記録・検算手順・免責を Claude が注記する。
6. **完了判定**: 総稼働・未分類時間・警告件数を提示。未分類が残れば振り直しを提案する。

### 入力 (Inputs)

| 名前 | 型 | 必須 | 出どころ | 例 |
|---|---|---|---|---|
| period | string (YYYY-MM or 日付範囲) | yes（既定: 当月。曖昧なら確認） | ユーザー発話 | "2026-06" |
| projects | string[]（案件 ID） | no（既定: 全案件） | ユーザー発話 / worklog projects.yaml | ["climbinsight"] |
| sources | ("worklog" \| "calendar" \| "manual")[] | no（既定: worklog + calendar） | ユーザー発話 | ["worklog"] |
| round_to | number (時間) | no（既定: 0.25 = 15 分） **(ASSUMPTION: 契約単位に合わせて変更可)** | ユーザー発話 | 0.25 |
| entries | {date: string, project: string, hours: number, source: string}[] | yes（フロー内で Claude が生成） | ソース収集 + 分類 | 下記 JSON 例 |

```json
[{"date": "2026-06-01", "project": "climbinsight", "hours": 3.5, "source": "worklog"}]
```

### 出力 (Outputs)

| 名前 | 形式 | どこに置く | 例 |
|---|---|---|---|
| 分類済みエントリ | JSON（配列） | `timesheet-data/entries/<YYYY-MM>.json` | 検算・invoice-builder の入力 |
| 集計結果 | JSON（by_project / by_day / by_project_day / by_source / warnings） | `aggregate.py` stdout | `{"grand_total_hours": "42.50", ...}` |
| 稼働サマリ | Markdown（案件別表・日別×案件表・警告・注記） | `timesheet-data/summaries/<YYYY-MM>.md` | 月次報告・請求の下ごしらえ |

---

## 想定ユーザー (Who)

- 主: SES 参画中のフリーランスエンジニア本人。月次で稼働報告・請求書を出す。
- 副: 生成サマリの数字は最終的にクライアント向け成果物（稼働報告・請求書）に転記される
  → 機密（顧客名・個人名）を含めない形にしておく必要がある。

持っている知識: 自分の案件と契約の稼働単位。持っていない/省きたい作業:
複数ソースの突き合わせ・転記・合算、どこまで拾ったかの管理。

---

## 既存ツール・スキルとの差別化 (Differentiation)

| 代替 | 限界 | このスキルが上回る点 |
|---|---|---|
| 手作業（カレンダー目視 + Excel 転記） | 毎月時間がかかり、転記ミス・重複計上・拾い漏れが出る | ソース横断の自動収集 + スクリプトによる再現可能な合算 + 重複警告 |
| jarvis-worklog の digest | 作業「内容」の整理であり、時間数の集計は出ない | ログのタイムスタンプから稼働時間に落とし、案件別・日別に合算する |
| Google カレンダー単体 | 予定ベースで実作業（worklog）が反映されず、案件別合算も手動 | worklog と突合し、重なりは重複計上を避けて片方採用 |
| 汎用 LLM に「合計して」と頼む | 暗算ミス・捏造のリスク。再現性がない | 合算は決定論スクリプトのみ。入力 JSON を残し誰でも検算できる |
| 市販の勤怠/タイムトラッキング SaaS | 打刻の習慣づけが必要。既存の worklog 資産を活かせない | 既に自動収集している worklog を再利用し、追加の打刻習慣が不要 |

---

## 成功条件 (Success Criteria)

- [ ] サマリの案件別合計・日別合計・総合計が、`entries/<YYYY-MM>.json` を
      `aggregate.py` に再投入して得られる値と**完全一致**する（検算可能）。
- [ ] 全エントリに `source` が付き、各数値がどのソース由来（実測/推定）か追跡できる。
- [ ] 分類に確証がないエントリが**「未分類」行としてサマリに明示**され、勝手に案件へ
      割り当てられていない（未分類 0 件は「全部分類できた」ことの観測可能な証拠になる）。
- [ ] 重複疑い・日合計 24h 超がある場合、サマリの「警告 (要確認)」に必ず表示される。
- [ ] サマリとエントリ JSON に顧客名・個人名・イベントタイトル原文が含まれない
      （案件 ID と時間数のみ）。
- [ ] 出力（entries JSON + 案件×時間の表）が ultron-invoice-builder にそのまま渡せる。

---

## 失敗モード予測 (Failure Modes)

| 失敗 | 起きる条件 | 回避策 |
|---|---|---|
| **重複計上**（同じ稼働を二重に数える） | 同一時間帯が worklog とカレンダーの両方にある / 同じエントリを 2 回入れる / entries JSON に追記してしまう | ソース間はカレンダー優先で片方のみ採用し除外を注記。スクリプトが完全重複を警告（`--dedupe` で除去）。再集計時は entries JSON を上書き運用 |
| **案件誤分類**（別案件に時間が乗る） | カレンダーのタイトルが曖昧 / 未登録案件 | 確証がなければ `unclassified` に倒し、サマリで明示して人が振り直す（誤分類より未分類優先）。案件 ID は worklog の projects.yaml に揃える |
| 合計値の捏造・暗算ミス | LLM がサマリに直接数字を書く | 合算はスクリプトのみ。Claude はエントリ JSON の生成と転記だけ。入力を残して検算可能にする |
| worklog 推定の過大/過小 | ログが疎（放置セッション）/ 密（常時ログ） | 推定ルールを固定して明記（30 分超の空白は除外）。推定である旨をサマリに必ず注記し、日合計 24h 超は警告 |
| 機密漏れ（顧客名・個人名） | カレンダーのイベントタイトルを転記 | 出力には案件 ID と時間数のみ。タイトル・参加者の原文は転記しない。worklog のマスキングは復元しない |
| 期間の取り違え | 「今月」「先月」の解釈ズレ（月初など） | 曖昧なら集計前に必ず期間をユーザーに確認する |
| カレンダー MCP が使えない | 未接続・権限切れ | worklog のみで続行し、「カレンダー未反映」をサマリに明記（黙って欠落させない） |

---

## 必要なリソース (Resources)

- 外部 API / CLI: Google カレンダー MCP（`list_events`）。python3（標準ライブラリのみ）。
- 権限: `worklog-data/classified/` の読み取り、`timesheet-data/` への書き込み、
  カレンダーの読み取り（MCP 経由）。
- 参照すべき公開知識: 特になし（個人データの集計）。準委任契約の精算幅・稼働単位の慣行は
  ユーザーの契約条件に従う。
- ローカル前提: onclimb-industries リポジトリ内で実行。jarvis-worklog が収集・分類済みの
  `worklog-data/classified/<project>/<date>.jsonl` が存在すること
  **(ASSUMPTION: worklog の classify 済みデータを一次ソースとし、raw ログは直接読まない)**。

---

## 実装メモ (Implementation Notes)

- ディレクトリ構成:
  - `.claude/skills/ultron-timesheet-aggregator/`
    - `SKILL.md` … 役割分担・トリガー表・標準フロー・出力フォーマット・品質/安全性
    - `scripts/aggregate.py` … 決定論集計（stdlib のみ。`--file/--stdin`、
      `--format json|markdown`、`--round-to`、`--dedupe`、入力バリデーション exit 2）
- データ置き場: repo 直下 `timesheet-data/`（`entries/<YYYY-MM>.json`、`summaries/<YYYY-MM>.md`）。
  `TIMESHEET_DATA` で上書き可 **(ASSUMPTION: worklog-data / stock-data と同じ慣習。機密を
  含み得るため `.gitignore` に `/timesheet-data/` を追加して運用する)**。
- 既存スキルとの依存関係: 入力は jarvis-worklog の classified データ（読み取りのみ）。
  出力は ultron-invoice-builder の入力（案件別稼働時間）になる想定 → entries JSON は
  `{date, project, hours, source}` の安定スキーマに固定。
- scripts に切り出す処理: 合算・内訳・構成比・警告（重複 / 24h 超 / 未知ソース / 未分類）・
  Markdown 表生成。丸め（既定 15 分単位）もスクリプト側でエントリ単位に適用。
- persona (ultron) の反映: 数値は根拠（entries JSON）とともに提示・推定は推定と明示・
  再現可能な判定基準・免責（公式な勤怠記録/請求書ではない）・機密を出力に含めない。

---

## 自己進化を入れるか (Self-Evolution Scope)

- [ ] パイプラインあり
- [x] パイプラインなし — 理由: 月次の定型集計タスクで、核となる合算ロジックは決定論
  スクリプトに固定されており（請求に絡む数値のため、実行ログ由来の自動書き換えはむしろ
  リスク）、学習余地が薄い。分類精度の改善は worklog 側の `config/projects.yaml` の整備で
  賄えるため、このスキル自身にログ蓄積 → SKILL.md 自動改訂のパイプラインは組み込まない。
  推定ルール・丸め単位の変更はユーザー指定でのみ行う。

---

## 実装リンク

- スキルディレクトリ: `../.claude/skills/ultron-timesheet-aggregator/`
  - `SKILL.md` … 起動条件・標準フロー（期間確認 → ソース収集 → 分類 → 集計 → サマリ生成）・
    品質/安全性（機密・数値根拠・invoice-builder 連携）。
  - `scripts/aggregate.py` … エントリ JSON（date / project / hours / source）→ 案件別・日別・
    案件×日・ソース別合計 + 警告。`py_compile` とサンプル入力（JSON / Markdown / dedupe /
    エラー系）で動作確認済み。
- 関連 PR / commit: (このスキル追加コミットで追記)

---

## 没にした理由

(該当なし — dropped ではない)
