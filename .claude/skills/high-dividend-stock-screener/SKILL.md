---
name: high-dividend-stock-screener
description: 日本の高配当株を screening して「おすすめ候補リスト」を作るスキル。公開情報(Yahoo!ファイナンス/IR BANK 等)から配当利回り4%以上の日本株を拾い、配当が右肩上がり・配当性向50%未満・営業利益に赤字なしの健全性で篩い、REIT/投資法人/インフラFを除外する。調べた会社は法人番号で台帳に記録し、回を分けて積み増す(続きから再開可)。最後に Claude のレビュー(偏り/要再確認/免責)を添える。「高配当株のおすすめをリストにして」「配当利回り4%以上の日本株を screening して」「増配が続いて配当性向50%未満の銘柄を探して」「前回の続きから高配当株を調べて」「この候補リストに Claude の評価コメント入れて」等で、ユーザーが意図的に起動したときだけ動く(自動起動しない)。投資助言ではなく情報整理。一般的な投資相談・worklog とは別系統。
metadata:
  type: skill
  data_dir: <repo>/stock-data
---

# high-dividend-stock-screener — 日本の高配当株 調査・選出スキル

公開情報から**配当利回り 4% 以上**の日本株を拾い、**増配傾向・低配当性向・営業黒字継続**の
健全性条件で篩って**おすすめ候補リスト**を作る。一度に全銘柄は調べきれないため、
**調べた会社を法人番号で台帳に記録**して回を分けて積み増し、最後に **Claude のレビュー**を添える。

> **スタンス（毎回明示）**: 出力は**公開情報の整理であって投資助言ではない**。最終判断は自己責任。
> 「おすすめ」は条件合致の「候補」の意味で、特定銘柄の売買を勧めるものではない（詳細は §免責）。

## 場所（コードとデータは分離されている）

- ツール本体・設定: このスキルディレクトリ `.claude/skills/high-dividend-stock-screener/`（`bin/` `config/` `references/` `templates/`）
- 設定: `config/screener.yaml`（しきい値・除外パターン・batch_size）
- **データ**: スキルが属する git リポジトリ直下の `stock-data/`
  （`registry/screened.jsonl` 台帳、`lists/<date>.md` リスト、`edinet/` 法人番号コードリストのキャッシュ）。
  `STOCK_DATA` 環境変数で上書き可。
- 実行はスキルディレクトリの絶対パスを `SKILL` に入れて bin を呼ぶ。スクリプトが配置場所から
  config を解決し、データ置き場（`stock-data/`）も自動算出する。

## 役割分担（重要）

数値の捏造を構造的に防ぐため、**取得・名寄せ・レビューは Claude、判定はスクリプト**に分ける。

- **Claude（あなた）**: サイトから現在値を取得（利回り/配当性向/配当推移/営業利益推移）、JSON 整形、レビュー講評。
- **スクリプト（決定論）**: `judge.py` が合否判定、`resolve_corp.py` が法人番号解決、`registry.py` が台帳の重複排除。

→ Claude は記憶から数値を書かない。取れない値は「未取得」とし、`judge.py` が insufficient として扱う。

## トリガーと対応フロー

| ユーザー発話の例 | 実行する標準フロー |
|---|---|
| 「高配当株のおすすめをリストにして」「高配当ポートフォリオ候補を出して」 | 標準フロー（continue: 台帳の続きから batch_size 社を調査） |
| 「配当利回り4%以上の日本株を screening して」「減配リスクの低い高配当株を選んで」 | 標準フロー（条件を発話から反映） |
| 「前回の続きから高配当株を調べて」 | 標準フロー（mode=continue を明示） |
| 「最初から / 新しく調べ直して」 | 標準フロー（mode=new。台帳は消さず、フィルタを使わず上位から） |
| 「このリストの銘柄、健全性をもう一回チェックして」 | 再検証フロー（対象銘柄のデータを取り直して judge.py） |
| 「この候補リストに Claude の評価コメント入れて」 | レビューのみ（既存リストに §Claude レビューを追記） |

## 標準フロー（「高配当株のおすすめをリストにして」の一声で）

```bash
SKILL=/Users/satoshi-onga/Documents/onclimb-industries/.claude/skills/high-dividend-stock-screener
TODAY=$(python3 -c "import datetime,zoneinfo;print(datetime.datetime.now(zoneinfo.ZoneInfo('Asia/Tokyo')).date())")
python3 "$SKILL/bin/registry.py" status     # 0) 台帳の累計を確認（続きの起点）
```

1. **入力を確定**: 利回り閾値（既定 4.0%）、除外区分（既定 REIT/投資法人/インフラF）、今回件数 `batch_size`（既定 20）、
   `mode`（既定 continue）。発話に条件があれば優先。`config/screener.yaml` の既定を上書きしたい場合は judge.py の引数で渡す。
2. **スクリーニング（母集団取得）**: `references/site_structure.md` に従い、Yahoo!ファイナンス等の高配当利回りランキングから
   **利回り ≧ 閾値**の銘柄（証券コード・社名・利回り）を `WebFetch`/`WebSearch` で取得。
   この時点で **REIT・投資法人・インフラF・ETF/ETN を除外**（`references/screening_rules.md` の除外ルール）。
3. **調査済みを除外**: 取得した証券コードを `registry.py filter` に渡し、**未調査(new)** だけに絞る。
   ```bash
   echo "7203
   8058
   9433" | python3 "$SKILL/bin/registry.py" filter --stdin   # → {"new":[...], "known":[...]}
   ```
   `new` の上位 `batch_size` 社を今回の対象にする（continue なら台帳済みは自動でスキップされる）。
4. **1 社ずつ健全性データを取得**: 各社について IR BANK 等から **配当推移 / 営業利益推移 / 配当性向 / 利回り**を取得し、
   1 社 = 1 JSON（古い→新しいの時系列、出所 `sources`）に整形して配列にまとめる。取れない値は null（未取得）。
   ```json
   [{"ticker":"7203","name":"トヨタ自動車","yield":4.2,"payout_ratio":30.5,
     "dividend_history":[52,60,75,75],"op_profit_history":[24000,29000,30000,53000],
     "sources":["https://...yahoo...","https://...irbank..."]}]
   ```
5. **判定（決定論）**: 上記 JSON を `judge.py` に渡し合否を得る。
   ```bash
   python3 "$SKILL/bin/judge.py" --file /path/to/companies.json
   # 発話で閾値を変える場合: --yield-min 4.0 --payout-max 50 --min-periods 3
   ```
6. **法人番号を解決**: 調べた**全銘柄（合否に関わらず）**の証券コードを `resolve_corp.py` で法人番号に変換。
   ```bash
   python3 "$SKILL/bin/resolve_corp.py" --stdin <<< "7203
   8058"          # 初回は EDINET コードリストを自動 DL。--refresh で再取得
   ```
   EDINET で引けない例外のみ国税庁 Web-API で社名照合（曖昧なら台帳に candidate として残し人手確認）。
7. **台帳へ記録**: 調べた**全銘柄**を `registry.py add` で台帳に追記（次回スキップのため。合否・指標・法人番号・sources を含める）。
   ```bash
   echo '{"ticker":"7203","corp_number":"...","name":"トヨタ自動車","yield":4.2,
   "payout_ratio":30.5,"op_profit_all_positive":true,"dividend_trend":"increasing",
   "passed":true,"sources":["..."]}' | python3 "$SKILL/bin/registry.py" add --stdin
   ```
8. **おすすめリスト生成**: `templates/list.md` を雛形に、合格銘柄を表へ。不合格は参考として理由付きで。
   出力は `stock-data/lists/<date>.md`。各値に**出所 URL と取得日**を付け、未取得は「未取得」と明記。
9. **Claude レビューを追記**: `references/review_checklist.md` の観点（偏り / 要再確認 / 鮮度・出所 / 免責）で
   リスト末尾の §Claude レビューを埋める。**断定的推奨を避け「候補」「要確認」の語彙**で書く。
10. **完了提示**: 「今回 N 社調査 / 合格 M 社 / 台帳 累計 K 社」を要約し、リストのパスと続きの回し方を案内する。

## 個別実行

- **台帳の状態**: `python3 "$SKILL/bin/registry.py" status`
- **未調査の抽出**: `python3 "$SKILL/bin/registry.py" filter --stdin <<< "<証券コード改行区切り>"`
- **台帳へ追記**: `python3 "$SKILL/bin/registry.py" add --stdin`（or `--file <json>`。配列で複数件可）
- **判定**: `python3 "$SKILL/bin/judge.py" --stdin`（or `--file`。`--yield-min/--payout-max/--min-periods/--allow-cuts` で上書き）
- **法人番号解決**: `python3 "$SKILL/bin/resolve_corp.py" [--refresh] [--stdin] <証券コード...>`

## バッチで打ち切り、続きは次回

1 回の起動は `batch_size`（既定 20）件で打ち切る。サイトへの過度な連続アクセスを避け、1 セッションのトークン量も抑えるため。
続きは「前回の続きから」で台帳（法人番号）を起点にレジュームする。**同じ会社は二度調べない**（`registry.py filter` が効く）。

## 免責（出力に毎回明記）

- 本スキルの出力は**公開情報の整理であって投資助言ではない**。最終判断は利用者の自己責任。
- 数値は**取得時点のもの**で将来を保証しない。発注前に**一次情報（IR・有報）で再確認**を推奨。
- 「おすすめ」は条件合致の意味であり、特定銘柄の売買を勧めるものではない。
- 取得対象サイトの**利用規約・robots.txt を尊重**し、商用再配布等はしない。`batch_size` で連続アクセスを抑える。

## 自己進化（軽め）

運用で磨くのは **取得メモ（`references/site_structure.md`）/ 除外ルール（`config/screener.yaml` + `references/screening_rules.md`）/
レビュー観点（`references/review_checklist.md`）**。取得失敗・REIT 誤混入・レビューの見落としが出たら該当ファイルに追記する。
**固定（勝手に変えない）**: コア4条件のしきい値（利回り4% / 配当性向50% / 営業黒字 / 増配）。変更はユーザー指定でのみ。

## 注意

- `judge.py` の `dividend_history` / `op_profit_history` は **古い→新しい**の順で渡す（順序を間違えると増配判定が逆になる）。
- 証券コードは Yahoo の 4 桁、EDINET は末尾 0 付き 5 桁。突合は `hdss_lib.normalize_ticker` が吸収する。
- 台帳の一意キーは**法人番号**（コード変更・社名変更に強い）。証券コードでも名寄せして重複追記を防ぐ。
