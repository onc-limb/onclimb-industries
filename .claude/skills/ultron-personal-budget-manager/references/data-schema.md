# budget-data のスキーマと雛形

データはすべて git 管理外の `budget-data/`（`BUDGET_DATA` 環境変数で上書き可）に置く。
金額はすべて**円・正の整数（税込）** **(ASSUMPTION: 家計簿は支払額ベース。税抜/税込の区別はしない)**。

## entries/YYYY-MM.json（変動費の月次エントリ）

```json
{
  "month": "2026-07",
  "entries": [
    {
      "id": "e-20260701-001",
      "date": "2026-07-01",
      "store": "スーパー○○ △△店",
      "amount": 2345,
      "category": "食費",
      "payment_method": "credit",
      "source": "receipt:IMG_0123.jpg",
      "gmail_message_id": null,
      "memo": ""
    }
  ]
}
```

| フィールド | 型 | 必須 | 備考 |
|---|---|---|---|
| id | string | yes | `e-YYYYMMDD-NNN`（同日内の連番）**(ASSUMPTION: この採番規則)** |
| date | YYYY-MM-DD | yes | 購入日（レシート/メール記載の日付） |
| store | string | yes | 店舗・サービス名。会員番号等は含めない |
| amount | int（円） | yes | 支払総額（税込） |
| category | string | yes | `references/categories.md` の一覧から。迷えば `その他` |
| payment_method | string | yes | `cash` / `credit` / `e-money` / `bank_transfer` / `unknown` |
| source | string | yes | `receipt:<ファイル名>` / `gmail:<件名要約>` / `manual` |
| gmail_message_id | string \| null | no | Gmail 取り込み時のみ。二重取り込み防止キー |
| memo | string | no | 分類に迷った理由・分割時の補足など |

## config/fixed-costs.json（固定費）

```json
{
  "fixed_costs": [
    {"name": "家賃", "amount": 90000, "category": "住居"},
    {"name": "電気", "amount": 8000, "category": "水道光熱"},
    {"name": "光回線", "amount": 5500, "category": "通信"},
    {"name": "動画配信", "amount": 1490, "category": "サブスク",
     "active_from": "2025-04", "active_until": "2026-06"}
  ]
}
```

| フィールド | 型 | 必須 | 備考 |
|---|---|---|---|
| name | string | yes | 名目 |
| amount | int（円） | yes | 月額。変動する光熱費は目安額を入れ、実額管理したい月は overrides ではなく金額を更新する **(ASSUMPTION: 初版は「固定費 = 毎月同額の見なし額」で簡素に保つ)** |
| category | string | yes | categories.md の一覧から |
| active_from | YYYY-MM | no | この月から適用（含む） |
| active_until | YYYY-MM | no | この月まで適用（含む）。解約したらここに最終月を入れる |

## config/income.json（収入）

```json
{
  "default": [
    {"name": "業務委託報酬", "amount": 800000}
  ],
  "overrides": {
    "2026-07": [
      {"name": "業務委託報酬", "amount": 820000},
      {"name": "臨時収入", "amount": 30000}
    ]
  }
}
```

- `default`: 毎月の既定収入リスト。
- `overrides["YYYY-MM"]`: その月だけ収入が違う場合の**丸ごと差し替え**リスト（default とのマージはしない）
  **(ASSUMPTION: マージ規則の曖昧さを避けるため差し替え方式)**。
- 収入は手取り額（実際に入金される額）を推奨 **(ASSUMPTION: 家計の収支を実感に合わせるため。
  額面で管理したい場合は税・保険料を固定費側に載せる)**。

## inbox/ の運用

- 未処理のレシート・領収書（jpg / png / pdf 等）を直接置く。ファイル名は自由。
- 取り込みが完了したファイルはスキルが `inbox/processed/` へ移動する（再処理防止）。
- Gmail の「DL待ち」添付を手動ダウンロードした場合もここに置けば、フロー①で取り込まれる。
