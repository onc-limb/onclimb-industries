# ドメインモデル（DDD）

## 概要

Domain-Driven Design（DDD）の戦術的パターンに基づき、ビジネスルールをドメイン層のオブジェクト（値オブジェクト・エンティティ・集約）に凝集させる。ドメインロジックがアプリケーション層やインフラ層に漏洩することを防ぎ、モデルの整合性と表現力を維持する。

## ルール

### 値オブジェクト（Value Object）

- 値オブジェクトは **不変（immutable）** である。生成後に内部状態を変更しない
- 同一性は **すべての属性値の等価性** で判定する。ID を持たない
- 生成時にバリデーションを行い、**不正な状態のインスタンスが存在できない** ようにする
- ドメイン固有の振る舞い（計算・比較・変換）は値オブジェクト自身のメソッドとして実装する
- プリミティブ型（`string`, `number`）をそのまま使わず、ドメインの意味を持つ型で包む

### エンティティ（Entity）

- エンティティは **一意の識別子（ID）** によって同一性を判定する
- 属性値が変わっても、ID が同じであれば同一のエンティティである
- エンティティの状態変更は **自身のメソッド** を通じて行い、外部から直接フィールドを書き換えない
- ビジネスルールに反する状態遷移を許可しない。不変条件（invariant）をメソッド内で強制する

### 集約（Aggregate）

- 集約は **1つの集約ルート（Aggregate Root）** を持ち、外部からのアクセスは集約ルートを経由する
- 集約内部のエンティティ・値オブジェクトへの直接参照を外部に公開しない
- 集約の境界は **トランザクション整合性の境界** と一致させる。1つのトランザクションで1つの集約だけを変更する
- 集約間の参照は **ID による間接参照** とし、オブジェクト参照を直接持たない
- 集約は可能な限り小さく保つ。大きな集約はロック競合とパフォーマンス劣化を招く

## 判断ガイド

| こういう場合 | こうする |
|---|---|
| `string` 型のメールアドレスを複数箇所でバリデーションしている | `Email` 値オブジェクトを作り、コンストラクタでバリデーションを一元化する |
| 2つのオブジェクトが「同じか」を判定したい | ID で判定するならエンティティ、全属性で判定するなら値オブジェクト |
| エンティティの状態を変更したい | setter を公開せず、ビジネス意図を表すメソッド（例: `approve()`, `cancel()`）を定義する |
| 集約が肥大化してきた | 本当に同一トランザクションで整合性を保つ必要がある範囲だけを集約に残し、それ以外はドメインイベントで結果整合性にする |
| 別の集約のデータを参照したい | ID で参照し、必要なデータはアプリケーションサービスやリードモデルで組み立てる |
| 値オブジェクトに振る舞いを持たせるか迷う | その計算・判定がドメインの関心事なら値オブジェクトのメソッドにする |

## 適用例

### 値オブジェクト

#### Good

```typescript
// 不変であり、生成時にバリデーションを行う
class Money {
  readonly amount: number;
  readonly currency: string;

  constructor(amount: number, currency: string) {
    if (amount < 0) {
      throw new Error("金額は0以上でなければなりません");
    }
    if (!["JPY", "USD", "EUR"].includes(currency)) {
      throw new Error(`未対応の通貨: ${currency}`);
    }
    this.amount = amount;
    this.currency = currency;
  }

  add(other: Money): Money {
    if (this.currency !== other.currency) {
      throw new Error("異なる通貨同士の加算はできません");
    }
    return new Money(this.amount + other.amount, this.currency);
  }

  equals(other: Money): boolean {
    return this.amount === other.amount && this.currency === other.currency;
  }
}
```

#### Bad

```typescript
// プリミティブ型をそのまま使い、バリデーションが呼び出し側に散在する
function createOrder(price: number, currency: string) {
  if (price < 0) throw new Error("invalid");
  if (currency !== "JPY") throw new Error("invalid");
  // ...
}

function applyDiscount(price: number, currency: string, rate: number) {
  if (price < 0) throw new Error("invalid"); // 同じバリデーションが重複
  // ...
}
```

### エンティティ

#### Good

```typescript
class Order {
  readonly id: string;
  private status: "draft" | "confirmed" | "cancelled";
  private items: OrderItem[];

  constructor(id: string, items: OrderItem[]) {
    if (items.length === 0) {
      throw new Error("注文には1つ以上の明細が必要です");
    }
    this.id = id;
    this.status = "draft";
    this.items = items;
  }

  // ビジネス意図を表すメソッドで状態遷移を制御する
  confirm(): void {
    if (this.status !== "draft") {
      throw new Error("下書き状態の注文のみ確定できます");
    }
    this.status = "confirmed";
  }

  cancel(): void {
    if (this.status === "cancelled") {
      throw new Error("既にキャンセル済みです");
    }
    this.status = "cancelled";
  }

  totalAmount(): Money {
    return this.items.reduce(
      (sum, item) => sum.add(item.subtotal()),
      new Money(0, "JPY"),
    );
  }
}
```

#### Bad

```typescript
// 外部から自由に状態を書き換えられ、不変条件を保証できない
class Order {
  id: string;
  status: string;       // 任意の文字列を代入可能
  items: OrderItem[];   // 外部から直接操作可能

  constructor(id: string) {
    this.id = id;
    this.status = "draft";
    this.items = [];
  }
}

// 呼び出し側でルールを管理 → ルールが散在する
function confirmOrder(order: Order) {
  order.status = "confirmed";  // draft かどうかのチェックがない
}
```

### 集約

#### Good

```typescript
// Order が集約ルート。OrderItem への操作は必ず Order を経由する
class Order {
  readonly id: string;
  private items: OrderItem[];
  private status: "draft" | "confirmed";

  addItem(product: ProductId, quantity: number, unitPrice: Money): void {
    if (this.status !== "draft") {
      throw new Error("確定済みの注文には明細を追加できません");
    }
    if (this.items.length >= 100) {
      throw new Error("明細は100件までです");
    }
    this.items.push(new OrderItem(product, quantity, unitPrice));
  }

  // 集約内部のオブジェクトを直接返さず、コピーを返す
  getItems(): readonly OrderItem[] {
    return [...this.items];
  }
}

// 集約間は ID で参照する
class OrderItem {
  constructor(
    readonly productId: ProductId,  // Product 集約への ID 参照
    readonly quantity: number,
    readonly unitPrice: Money,
  ) {}

  subtotal(): Money {
    return new Money(this.unitPrice.amount * this.quantity, this.unitPrice.currency);
  }
}
```

#### Bad

```typescript
// 集約の境界がなく、外部から内部オブジェクトを直接操作できる
class Order {
  id: string;
  items: OrderItem[];  // 外部から直接 push/splice 可能
  customer: Customer;  // 別の集約のオブジェクト参照を直接保持
}

// 集約ルートを経由せず、明細を直接操作している
order.items.push(new OrderItem(...));
order.items[0].quantity = 999;
order.customer.name = "changed";  // 別集約の状態まで変更できてしまう
```
