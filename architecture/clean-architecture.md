# Clean Architecture

## 概要

ビジネスルールと技術的関心事をレイヤーで分離し、依存の方向を「外側 → 内側」に統一することで、ビジネスロジックがフレームワーク・DB・UI などの技術要素に依存しない構造を作る。

> **注意:** 原著で示されている4重の同心円は一例であり、著者自身が「レイヤーは4つである必要はない」と明言している。重要なのはレイヤーの数ではなく、**依存性の方向が常に内側（ビジネスルール）に向かうこと**である。

## ルール

- ビジネスルール（Domain）と技術的関心事（Infrastructure）を別レイヤーに分離する
- 依存の方向は常に外側から内側へ向かう。内側のレイヤーは外側のレイヤーを知らない
- 内側のレイヤーが外側の機能を利用する場合は、内側でインターフェース（Port）を定義し、外側で実装（Adapter）を提供する（依存性逆転の原則）
- Domain レイヤーはフレームワーク・ライブラリ・DB クライアントなどの技術要素を import しない
- レイヤー境界を越えるデータの受け渡しには、受け取り側のレイヤーで定義した型（DTO / Domain Model）を使用する
- レイヤーの数やネーミングはプロジェクトの規模と複雑度に合わせて決定する。最小構成は Domain / UseCase / Infrastructure の3層

## 判断ガイド

| こういう場合 | こうする |
|---|---|
| 小規模で CRUD のみのアプリ | レイヤー分離のコストが上回るため、無理に適用しない |
| 外部 API のレスポンス型を Domain で使いたい | Domain 側に独自の型を定義し、Infrastructure 層で変換する |
| バリデーションを Domain と UI の両方で行いたい | Domain 層にバリデーションロジックを置き、UI 層はそれを呼び出す |
| UseCase が単なるパススルーになっている | 現時点でロジックが薄くても、将来の拡張ポイントとして維持するか、プロジェクト規模に応じて省略する |
| テスト時に DB 接続を避けたい | Domain 層で定義した Repository インターフェースのモック実装を注入する |

## 適用例

### Good

依存性逆転により Domain が Infrastructure を知らない構成。

```ts
// domain/user.ts — Domain層: 技術要素に依存しない
interface User {
  id: string;
  name: string;
  email: string;
}

// domain/user-repository.ts — Domain層: インターフェースのみ定義
interface UserRepository {
  findById(id: string): Promise<User | null>;
  save(user: User): Promise<void>;
}

// use-case/get-user.ts — UseCase層: Domainにのみ依存
class GetUser {
  constructor(private readonly userRepository: UserRepository) {}

  async execute(id: string): Promise<User | null> {
    return this.userRepository.findById(id);
  }
}

// infrastructure/prisma-user-repository.ts — Infrastructure層: Domainのインターフェースを実装
import { PrismaClient } from "@prisma/client";

class PrismaUserRepository implements UserRepository {
  constructor(private readonly prisma: PrismaClient) {}

  async findById(id: string): Promise<User | null> {
    const record = await this.prisma.user.findUnique({ where: { id } });
    if (!record) return null;
    // Infrastructure の型を Domain の型に変換
    return { id: record.id, name: record.name, email: record.email };
  }

  async save(user: User): Promise<void> {
    await this.prisma.user.upsert({
      where: { id: user.id },
      create: user,
      update: user,
    });
  }
}
```

### Bad

Domain 層が技術要素に直接依存している。

```ts
// domain/get-user.ts — NG: Domain層がPrisma（技術要素）に直接依存
import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

async function getUser(id: string) {
  // DBクライアントと密結合しており、テスト・差し替えが困難
  return prisma.user.findUnique({ where: { id } });
  // 戻り値がPrismaの型であり、Domain Modelではない
}
```
