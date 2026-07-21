# プログラミング基礎原則

## 概要

ソフトウェア設計における普遍的な原則（DRY・YAGNI・KISS 等）を定義する。これらは特定のアーキテクチャに依存せず、あらゆるコードベースに適用される判断基準である。

## ルール

### DRY — Don't Repeat Yourself

> "Every piece of **knowledge** must have a single, unambiguous, authoritative representation within a system."
> — *The Pragmatic Programmer* (Andrew Hunt & David Thomas)

- DRY が禁じているのは **知識（knowledge）の重複** であり、コードの文字列的な重複ではない
- 同じビジネスルール・同じ判断ロジック・同じ定義が複数箇所に存在し、片方を変更したらもう片方も変更しなければならない状態が DRY 違反である
- 見た目が同じでも、変更理由が異なるコードは重複ではない。それぞれ独立に進化する可能性があるため、無理に共通化しない
- DRY の適用先はコードだけでなく、スキーマ定義・ドキュメント・設定値なども含む

### YAGNI — You Aren't Gonna Need It

- 現時点で必要とされていない機能・抽象化・設定項目を先回りして実装しない
- 「将来必要になるかもしれない」は実装の正当な理由にならない
- 拡張ポイントは、実際に2つ目のユースケースが発生した時点で初めて導入する

### KISS — Keep It Simple, Stupid

- 同じ要件を満たす実装が複数ある場合、最も単純な方法を選ぶ
- 抽象化の層を増やす前に、その層が本当に必要かを問う
- 「賢い」コードより「明快な」コードを優先する

### 早すぎる最適化の回避

- パフォーマンス最適化は、計測結果に基づいて行う
- 推測でホットパスを決めない。プロファイラの結果を根拠にする
- 可読性とパフォーマンスがトレードオフになる場合、まず可読性を取り、計測で問題が確認されてから最適化する

### 関心の分離 — Separation of Concerns

- 1つのモジュール・関数・クラスは、1つの責務だけを持つ
- 異なる変更理由を持つロジックは、異なる場所に置く
- 「何をするか（What）」と「どうやるか（How）」を分離する

## 判断ガイド

| こういう場合 | こうする |
|---|---|
| 2箇所で同じコードがあるが、変更理由が異なる | 共通化しない。それぞれが独立して変化できる状態を保つ |
| 2箇所で同じビジネスルールを表現している | 1箇所に集約し、両方からそれを参照する（DRY 適用） |
| 3行の重複コードを共通関数に切り出すか迷う | 変更理由が同じか確認する。同じなら切り出す。違うなら重複を許容する |
| 「後で使うかも」で引数やオプションを追加したい | 追加しない（YAGNI）。必要になった時点で追加する |
| デザインパターンを適用すべきか迷う | 現在の要件をパターンなしで満たせるなら不要（KISS） |
| パフォーマンスが心配なコードがある | まず計測する。推測で最適化しない |

## 適用例

### DRY — 正しい適用

#### Good

```typescript
// 税率の「知識」は1箇所だけに存在する
const TAX_RATE = 0.10;

function calcPriceWithTax(price: number): number {
  return Math.floor(price * (1 + TAX_RATE));
}

function calcTaxAmount(price: number): number {
  return Math.floor(price * TAX_RATE);
}
```

#### Bad

```typescript
// 同じビジネスルール（税率10%）が複数箇所にハードコードされている
function calcPriceWithTax(price: number): number {
  return Math.floor(price * 1.10);
}

function calcTaxAmount(price: number): number {
  return Math.floor(price * 0.10);
}
```

### DRY — 誤った適用（過度な共通化）

#### Good

```typescript
// 注文バリデーションと在庫バリデーションは見た目が似ているが、
// 変更理由が異なるため別々に定義する
function validateOrder(order: Order): boolean {
  return order.total > 0 && order.items.length > 0;
}

function validateInventory(entry: InventoryEntry): boolean {
  return entry.quantity > 0 && entry.items.length > 0;
}
```

#### Bad

```typescript
// 「コードが似ている」だけで無理に共通化すると、
// 一方の仕様変更がもう一方に波及する
function validatePositiveWithItems(obj: { amount: number; items: unknown[] }): boolean {
  return obj.amount > 0 && obj.items.length > 0;
}
```

### YAGNI

#### Good

```typescript
// 現在の要件: JSON でエクスポートする
function exportReport(data: Report): string {
  return JSON.stringify(data.toObject());
}
```

#### Bad

```typescript
// 「将来 CSV や XML も必要になるかも」で過剰な抽象化
interface ReportExporter {
  export(data: Report): string;
}

class JsonExporter implements ReportExporter {
  export(data: Report): string {
    return JSON.stringify(data.toObject());
  }
}

class CsvExporter implements ReportExporter { // まだ誰も使わない
  export(data: Report): string { ... }
}
```
