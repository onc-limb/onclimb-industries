# SOLID 原則

## 概要

オブジェクト指向設計の5つの基本原則。変更に強く、テストしやすく、理解しやすいコードを書くための指針。

### 原則間の関係

- SRP違反は OCP違反を誘発する（責務が混在 → 拡張時に既存コードの修正が必要になる）
- ISP違反は LSP違反を誘発する（大きすぎるインターフェース → 「未サポート」例外が生まれる）
- DIPを守ると OCPが自然に達成されやすい

### 適用スコープ

これらの原則は、チームで保守する中〜大規模なプロダクションコードに適用する。以下には過度に適用しなくてよい:

- 使い捨てのスクリプトやプロトタイプ
- 分岐や依存が少なく、今後拡張される見込みがないコード

---

## 1. 単一責任の原則 (Single Responsibility Principle)

**1つのクラス・モジュールが変更される理由は1つだけにする。**

責務が混在したクラスを変更すると、無関係な機能まで壊れる。テスト・レビュー・障害調査の範囲が広がり、変更コストが加速度的に増える。

### ルール

- 1つのクラスは1つの変更理由だけを持つ。「このクラスを変更する理由は？」と問い、理由が2つ以上あれば分割する
- 利用側ごとに「この利用側の仕様が変わったとき、このクラスに変更が必要か？」と問う。複数の利用側の仕様変更に反応するなら責務が混在している

### 検出シグナル

- クラス名・ファイル名に `And`, `Manager`, `Helper`, `Util`, `Common`, `Processor` を含む
- 1クラスのメソッド数が10を超える、または行数が200行を超える
- 変更時に無関係なテストが壊れる
- `constructor` の依存が5つ以上ある

### 判断ガイド

| こういう場合 | こうする |
|---|---|
| 1つのクラスにビジネスロジックとデータ整形が混在 | ロジック層とプレゼンテーション層に分離する |
| ユーティリティ関数が肥大化してきた | ドメインごとにモジュールを分割する |
| 変更時に無関係なテストが壊れる | 責務が混在している兆候。クラスを分割する |
| 構造が同じでもアクターや変更理由が異なる（例: 経理用と営業用の集計） | 共通化せず別クラスにする。一方の変更がもう一方を壊す原因になる |
| 利用側Aの仕様変更でこのクラスを修正→利用側Bが壊れる | 責務が混在している。利用側ごとにクラスを分ける |

### 適用例

#### Good

```typescript
class OrderValidator {
  validate(order: Order): ValidationResult {
    if (order.items.length === 0) {
      return { valid: false, reason: "Items are empty" };
    }
    return { valid: true };
  }
}

class OrderRepository {
  save(order: Order): void {
    db.insert("orders", order);
  }
}
```

#### Bad

```typescript
// 検証もDB保存もメール送信も1クラスに詰め込んでいる
// → 検証ロジックを変更したいだけなのに、メール送信のテストまで壊れる
class OrderService {
  validate(order: Order): boolean {
    return order.items.length > 0;
  }
  save(order: Order): void {
    db.insert("orders", order);
  }
  sendConfirmationEmail(order: Order): void {
    mailer.send(order.userEmail, "Order confirmed");
  }
}
```

---

## 2. 開放閉鎖の原則 (Open-Closed Principle)

**拡張に対して開き、修正に対して閉じる。既存コードを変更せずに振る舞いを追加できるようにする。**

新しい種類を追加するたびに既存コードを修正すると、修正漏れやデグレが発生しやすくなる。振る舞いの追加が既存コードの変更を伴わない設計を目指す。

### ルール

- 新しい種類・パターンの追加時に、既存のクラスや関数の `if/switch` を書き換えない
- 振る舞いの差異はインターフェースやストラテジーパターンで吸収する

### 検出シグナル

- `switch(type)` や `if/else if` による型分岐が複数箇所に散在している
- `instanceof` チェックで振る舞いを分岐している
- 新しい種類を追加するたびに既存ファイルの差分が発生する

### 判断ガイド

| こういう場合 | こうする |
|---|---|
| 新しい種類を追加するたびに既存の `if/switch` を修正している | 種類ごとの振る舞いをインターフェースで抽象化する |
| 分岐が2つ以下で今後増える見込みがない | 無理に抽象化せず `if` のままでよい |
| 設定値の変更だけで振る舞いが変わる | OCP を適用する必要はない |
| 分岐を共通メソッドにまとめただけで「抽象化した」と思っている | それは共通化であって抽象化ではない。分岐の中身が異なるアクターに属するなら、1つのクラスに複数の変更理由が生まれSRP違反になる。振る舞いごとに別クラスへ分離する |

### 適用例

#### Good

```typescript
interface PriceCalculator {
  calculate(amount: number): number;
}

class RegularPrice implements PriceCalculator {
  calculate(amount: number): number {
    return amount;
  }
}

class MemberPrice implements PriceCalculator {
  calculate(amount: number): number {
    return amount * 0.9;
  }
}

// 新しい価格体系を追加しても、この関数は変更不要
function checkout(calculator: PriceCalculator, amount: number): number {
  return calculator.calculate(amount);
}
```

#### Bad

```typescript
// 新しい会員種別が増えるたびにこの関数を修正する必要がある
function calculatePrice(userType: string, amount: number): number {
  if (userType === "regular") {
    return amount;
  } else if (userType === "member") {
    return amount * 0.9;
  } else if (userType === "vip") {
    return amount * 0.8;
  }
  return amount;
}
```

---

## 3. リスコフの置換原則 (Liskov Substitution Principle)

**サブクラスは親クラスと置き換えても正しく動作しなければならない。**

親クラスの型を受け取る関数にサブクラスを渡したとき、想定外のエラーや振る舞いの変化が起きると、型が保証する安全性が崩れる。コンパイルは通るが実行時に壊れるバグの原因になる。

### ルール

- サブクラスで親クラスのメソッドの事前条件を強めない（引数の制約を増やさない）
- サブクラスで親クラスのメソッドの事後条件を弱めない（戻り値の保証を減らさない）
- 親クラスのメソッドを `override` して例外を投げるだけの実装は違反
- 「is-a」の関係が成立しない場合は継承ではなくコンポジションを使う

### 検出シグナル

- `override` したメソッドで `throw new Error` だけを書いている
- サブクラスで `@ts-ignore` や型アサーション (`as any`) を使って親の型制約を回避している
- サブクラスに親にないバリデーションを追加して、親と同じ入力で失敗するようになっている

### 判断ガイド

**契約プログラミングの4つの基準で判定する:**

- **事前条件**（メソッドを呼ぶ側が満たすべき入力の制約）
- **事後条件**（メソッドが呼び出し側に保証する出力の制約）
- **不変条件**（処理の前後で常に成り立つべきオブジェクトの状態）
- **例外**（親が定義していない例外をサブクラスが独自に投げない）

| こういう場合 | こうする |
|---|---|
| サブクラスで引数のバリデーションを追加している（事前条件を強めている） | 親と同じかより緩い入力条件を受け入れる |
| サブクラスで `null` や例外を返す可能性を増やしている（事後条件を弱めている） | 親が保証する戻り値の型・範囲を維持する |
| サブクラスの操作後にオブジェクトの状態が親の想定と異なる（不変条件が壊れている） | 親が維持する状態の整合性をサブクラスでも保つ |
| サブクラスで親にない独自の例外を投げている | 親が定義した例外の範囲内で処理する。それができないなら継承関係が不適切 |
| サブクラスで「このメソッドは使えません」と例外を投げたくなる | 継承関係が不適切。インターフェースを分離する |
| 正方形は長方形の一種だが `setWidth` の振る舞いが異なる | 継承せず、別の型として扱う |

### 適用例

#### Good

```typescript
interface Bird {
  move(): void;
}

class Sparrow implements Bird {
  move(): void {
    console.log("Flying");
  }
}

class Penguin implements Bird {
  move(): void {
    console.log("Walking");
  }
}

// どの Bird でも安全に呼び出せる
function migrate(bird: Bird): void {
  bird.move();
}
```

#### Bad

```typescript
class Bird {
  fly(): void {
    console.log("Flying");
  }
}

class Penguin extends Bird {
  // 親クラスの契約を破っている:
  // Bird型を受け取る関数にPenguinを渡すと実行時エラーになる。
  // コンパイルは通るが、「fly()を安全に呼べる」という前提が崩れる。
  fly(): void {
    throw new Error("Penguins can't fly!");
  }
}
```

---

## 4. インターフェース分離の原則 (Interface Segregation Principle)

**使わないメソッドへの依存を強制しない。インターフェースはクライアントごとに分離する。**

大きすぎるインターフェースを実装すると、使わないメソッドのために空実装や「未サポート」例外を書くことになり、LSP違反を誘発する。

### ルール

- 1つのインターフェースのメソッド数は最大5つを目安にする
- 実装クラスが空メソッドや `throw new Error("Not implemented")` を書いていたら分割を検討する
- 利用側が必要とするメソッドだけを含む小さなインターフェースを定義する

### 検出シグナル

- 実装クラスに `throw new Error("Not supported")` や空メソッドがある
- モック作成時に大量の空メソッドを書いている
- 関数の引数にオブジェクトを受け取るが、そのプロパティの一部しか使っていない

### 判断ガイド

| こういう場合 | こうする |
|---|---|
| インターフェースの一部メソッドしか使わない実装がある | そのメソッド群を別インターフェースに切り出す |
| インターフェースが1〜2メソッドしかなく、常にセットで使う | 無理に分割しなくてよい |

### 適用例

#### Good

```typescript
interface Readable {
  read(id: string): Data;
}

interface Writable {
  write(data: Data): void;
}

// 読み取り専用のクライアントは Readable だけに依存
class ReportGenerator {
  constructor(private readonly source: Readable) {}

  generate(id: string): Report {
    const data = this.source.read(id);
    return buildReport(data);
  }
}
```

#### Bad

```typescript
interface DataStore {
  read(id: string): Data;
  write(data: Data): void;
  delete(id: string): void;
  backup(): void;
  migrate(version: number): void;
}

// 読み取りしかしないのに全メソッドの実装を強制される
class ReadOnlyCache implements DataStore {
  read(id: string): Data { return cache.get(id); }
  write(): void { throw new Error("Not supported"); }
  delete(): void { throw new Error("Not supported"); }
  backup(): void { throw new Error("Not supported"); }
  migrate(): void { throw new Error("Not supported"); }
}
```

---

## 5. 依存性逆転の原則 (Dependency Inversion Principle)

**上位モジュールは下位モジュールに依存しない。どちらも抽象に依存する。**

ビジネスロジックがインフラ実装に直接依存すると、DB変更やライブラリ移行のたびにビジネスロジック側も修正が必要になる。テスト時にDBやAPIを差し替えることもできない。

### ルール

- ビジネスロジック層が外部ライブラリやインフラ実装を直接 `import` しない
- 依存は必ずインターフェース（抽象）を経由し、コンストラクタで注入する
- インターフェースの定義場所は利用側（上位モジュール）のレイヤーに置く

### 検出シグナル

- ドメイン層・ユースケース層の `import` 文にインフラ系パッケージ（ORM, HTTPクライアント, SDK等）が含まれている
- クラス内部で `new` を使って外部サービスのクライアントを直接生成している
- テスト時にDBやAPIの差し替えができない

### 判断ガイド

| こういう場合 | こうする |
|---|---|
| サービス層が `new MySQLClient()` を直接生成している | インターフェースを定義し、DI で注入する |
| 外部APIのSDKをビジネスロジック内で直接呼んでいる | Gateway / Adapter を挟む |
| テスト時にDBやAPIの差し替えができない | 抽象への依存に切り替える |
| 小規模スクリプトや使い捨てコード | 過度な抽象化は不要。直接依存でよい |

### 適用例

#### Good

```typescript
// 上位モジュール側でインターフェースを定義
interface UserRepository {
  findById(id: string): Promise<User | null>;
}

// ビジネスロジックは抽象にのみ依存
class GetUserUseCase {
  constructor(private readonly userRepo: UserRepository) {}

  async execute(id: string): Promise<User> {
    const user = await this.userRepo.findById(id);
    if (!user) throw new Error("User not found");
    return user;
  }
}

// 下位モジュールが抽象を実装
class PostgresUserRepository implements UserRepository {
  async findById(id: string): Promise<User | null> {
    return db.query("SELECT * FROM users WHERE id = $1", [id]);
  }
}
```

#### Bad

```typescript
import { PrismaClient } from "@prisma/client";

// ビジネスロジックがインフラ実装に直接依存している
class GetUserUseCase {
  private prisma = new PrismaClient();

  async execute(id: string): Promise<User> {
    const user = await this.prisma.user.findUnique({ where: { id } });
    if (!user) throw new Error("User not found");
    return user;
  }
}
```
