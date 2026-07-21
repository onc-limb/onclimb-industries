# 契約プログラミング（Design by Contract）

## 概要

関数・メソッドの呼び出しを「契約」として捉え、事前条件（precondition）・事後条件（postcondition）・不変条件（invariant）を明示的に検証することで、バグの混入を早期に検出し、責任の所在を明確にする。

## メリット

- **バグの早期検出**: 不正な入力や状態を関数の入口で即座に弾くため、問題の発生箇所と検出箇所が近くなり、デバッグコストが大幅に下がる
- **責任の明確化**: 「呼び出し側が事前条件を満たす責任」「呼び出される側が事後条件を満たす責任」が明確になり、障害発生時にどちらの問題かすぐ判断できる
- **コードの自己文書化**: 事前条件・事後条件がコード上に明示されることで、関数の使い方と保証する振る舞いが読むだけで分かる
- **不正状態の伝播防止**: コンストラクタで不変条件を強制することで、不正なオブジェクトがシステム内を流通しなくなる
- **テストの指針になる**: 契約がそのまま境界値テストやエラーケースのテスト仕様になる

## 従わない場合のリスク

- **サイレントな不整合**: 不正な値が検証なしに保存・伝播し、問題が発覚するのは遠く離れた別の処理。原因の特定に時間がかかる
- **責任の曖昧化**: 呼び出し側・呼び出される側のどちらが悪いのか分からず、防御的コードが至るところに重複する
- **デバッグの長期化**: エラーの発生箇所と根本原因が離れているため、再現・調査に時間がかかる
- **不正オブジェクトの流通**: バリデーションなしで生成されたオブジェクトがシステム内を流通し、予期しない箇所で障害を起こす
- **仕様の暗黙化**: 関数が何を期待し何を保証するかがコードから読み取れず、利用者は実装の詳細を読むか試行錯誤するしかない

## ルール

- 公開関数・メソッドの入口で事前条件を検証する。事前条件を満たさない場合はエラーを返す（不正な状態のまま処理を続行しない）
- 関数・メソッドの出口で事後条件を検証する。戻り値やオブジェクトの状態が契約通りであることを保証する
- オブジェクトが常に満たすべき不変条件は、コンストラクタおよび状態変更メソッドの完了後に成立していることを保証する
- 事前条件の検証は関数の先頭にまとめて記述する（ビジネスロジックと混在させない）
- 検証に失敗した場合のエラーメッセージには、どの条件に違反したかを明記する
- 内部関数（private）では、呼び出し元が事前条件を保証できる場合、検証を省略してよい
- 契約の検証にビジネスロジックや副作用を含めない（検証は純粋な判定のみ）

## 判断ガイド

| こういう場合 | こうする |
|---|---|
| 外部入力（API リクエスト、ユーザー入力）を受け取る関数 | 必ず事前条件を検証する |
| 内部モジュール間の呼び出し | 呼び出し元が保証できるなら省略可。ただしドメイン層の入口では検証する |
| コンストラクタ / ファクトリ関数 | 不正な状態のオブジェクトを生成させないために必ず検証する |
| 事後条件の検証コストが高い場合 | 開発・テスト環境では assert で検証し、本番では省略を許容する |
| nil / null を返す可能性がある関数 | 戻り値の事後条件として nil チェックを呼び出し元に求めるか、エラー型で返す |
| 複数の引数に跨る整合性条件がある場合 | 個別の引数検証の後にまとめて整合性を検証する |

## 適用例

### Good

```typescript
// ファクトリ関数で事前条件を検証し、不正な状態のオブジェクト生成を防ぐ
class Post {
  private constructor(
    readonly title: string,
    readonly body: string,
    readonly createdAt: Date,
  ) {}

  static create(title: string, body: string): Post {
    // 事前条件: title
    if (title === "") {
      throw new Error("title is required");
    }
    if (title.length > 50) {
      throw new Error(`title must be <= 50 chars, got ${title.length}`);
    }
    // 事前条件: body
    if (body === "") {
      throw new Error("body is required");
    }
    if (body.length > 1000) {
      throw new Error(`body must be <= 1000 chars, got ${body.length}`);
    }

    return new Post(title, body, new Date());
  }
}
```

```typescript
// 事前条件 + 事後条件 + 不変条件の例
class BankAccount {
  private _balance: number;

  constructor(initialBalance: number) {
    // 事前条件
    if (initialBalance < 0) {
      throw new Error(`initialBalance must be >= 0, got ${initialBalance}`);
    }
    this._balance = initialBalance;
    // 不変条件の確立: balance >= 0
  }

  withdraw(amount: number): number {
    // 事前条件
    if (amount <= 0) {
      throw new Error(`amount must be > 0, got ${amount}`);
    }
    if (amount > this._balance) {
      throw new Error(
        `insufficient balance: ${this._balance} < ${amount}`,
      );
    }

    this._balance -= amount;

    // 事後条件
    if (this._balance < 0) {
      throw new Error("postcondition failed: balance must not be negative after withdrawal");
    }
    return this._balance;
  }
}
```

### Bad

```typescript
// 事前条件を検証せず、不正な値がそのまま保存される
class Post {
  constructor(
    readonly title: string,
    readonly body: string,
    readonly createdAt: Date = new Date(),
  ) {}
}
```

```typescript
// 検証ロジックがビジネスロジックと混在し、責任の所在が不明確
class BankAccount {
  private _balance: number = 0;

  withdraw(amount: number): number {
    this._balance -= amount;
    if (this._balance < 0) {
      // 事後に気付いてロールバック — 契約違反の検出が遅い
      this._balance += amount;
      throw new Error("insufficient balance");
    }
    return this._balance;
  }
}
```
