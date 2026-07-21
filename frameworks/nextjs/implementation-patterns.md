# Next.js 固有の実装パターン

## Server Components と Client Components の使い分け

React 19 + Next.js v16 では、デフォルトで Server Component となる。

| 判断基準 | 使うもの |
| --- | --- |
| データ取得・表示のみ | Server Component（デフォルト） |
| `useState` / `useEffect` / ブラウザ API を使う | `"use client"` を付けて Client Component |
| イベントハンドラ（`onClick` 等）を使う | Client Component |
| Server Action を呼ぶフォーム | Client Component（`useActionState` を使用） |

**原則: `"use client"` は必要最小限のコンポーネントにのみ付与し、Server Component をデフォルトとする。**

```tsx
// features/dashboard/components/stats-card.tsx
// Server Component — データ取得と表示のみ
import { getDashboardStats } from "@/features/dashboard/lib/get-dashboard-stats";

export async function StatsCard() {
  const stats = await getDashboardStats();

  return (
    <div>
      <p>{stats.totalUsers}</p>
      <p>{stats.totalRevenue}</p>
    </div>
  );
}
```

```tsx
// features/auth/components/login-form.tsx
// Client Component — ユーザーインタラクションが必要
"use client";

import { useActionState } from "react";
import { loginAction } from "@/features/auth/actions/login-action";

export function LoginForm() {
  const [state, action, isPending] = useActionState(loginAction, null);

  return (
    <form action={action}>
      <input name="email" type="email" />
      <input name="password" type="password" />
      <button type="submit" disabled={isPending}>
        ログイン
      </button>
      {state?.error && <p>{state.error}</p>}
    </form>
  );
}
```

## Server Actions

Server Actions は feature 内の `actions/` ディレクトリに配置する。[contract-programming.md](../../architecture/contract-programming.md) に従い、入力の事前条件を検証する。

```typescript
// features/auth/actions/login-action.ts
"use server";

import { Type, type Static } from "@sinclair/typebox";
import { Value } from "@sinclair/typebox/value";

const LoginSchema = Type.Object({
  email: Type.String({ format: "email" }),
  password: Type.String({ minLength: 8 }),
});

type LoginInput = Static<typeof LoginSchema>;

type LoginState = {
  success: boolean;
  error?: string;
} | null;

export async function loginAction(
  _prevState: LoginState,
  formData: FormData,
): Promise<LoginState> {
  // 事前条件の検証（contract-programming.md）
  const input = {
    email: formData.get("email"),
    password: formData.get("password"),
  };

  if (!Value.Check(LoginSchema, input)) {
    const errors = [...Value.Errors(LoginSchema, input)];
    return {
      success: false,
      error: errors[0]?.message ?? "入力が不正です",
    };
  }

  // ビジネスロジックの実行
  // ...

  return { success: true };
}
```

## データ取得パターン

| パターン | 実装方法 | 使い分け |
| --- | --- | --- |
| サーバーサイド取得 | Server Component 内で `async/await` | 初回表示に必要なデータ |
| クライアントサイド取得 | TanStack Query + Route Handler | リアルタイム更新・ポーリングが必要な場合 |
| ミューテーション | Server Actions + `useActionState` | フォーム送信・データ変更 |

- **Server Actions は取得（GET 相当）に使用しない。** Server Actions は POST リクエストとして実行されるため、意味的にもキャッシュの観点からもミューテーション専用とする
- クライアントサイドから取得する場合は、Route Handler で GET エンドポイントを定義し、TanStack Query の `queryFn` から呼び出す
- Route Handler の用途は「クライアントサイド取得の GET エンドポイント」と「外部サービスからの Webhook 受信」に限定する

```tsx
// app/dashboard/page.tsx — ページは組み立てのみ（feature-based.md）
import { StatsCard } from "@/features/dashboard/components/stats-card";
import { ActivityFeed } from "@/features/dashboard/components/activity-feed";

export default function DashboardPage() {
  return (
    <div>
      <StatsCard />
      <ActivityFeed />
    </div>
  );
}
```

```typescript
// app/api/dashboard/stats/route.ts — クライアントサイド取得用の Route Handler
import { NextResponse } from "next/server";
import { getSession } from "@/features/auth/lib/get-session";
import { getDashboardStats } from "@/features/dashboard/lib/get-dashboard-stats";

export async function GET() {
  // 認証チェックは Route Handler ごとに実施する
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const stats = await getDashboardStats();
  return NextResponse.json(stats);
}
```

```tsx
// features/dashboard/hooks/use-dashboard-stats.ts — TanStack Query で取得
import { useQuery } from "@tanstack/react-query";
import type { DashboardStats } from "@/features/dashboard/types";

export function useDashboardStats() {
  return useQuery<DashboardStats>({
    queryKey: ["dashboard", "stats"],
    queryFn: async () => {
      const res = await fetch("/api/dashboard/stats");
      if (!res.ok) throw new Error("Failed to fetch dashboard stats");
      return res.json();
    },
  });
}
```

## Route Handler の認証チェック

認証チェックは Route Handler ごとに個別に実施する。Middleware による一括制御ではなく、各エンドポイントで明示的にチェックすることで、認証要否がコードから読み取れるようにする。

```typescript
// 認証が必要な Route Handler
export async function GET() {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  // ...
}

// 認証不要な Route Handler（Webhook 等）
export async function POST(request: Request) {
  // Webhook 署名の検証等、エンドポイント固有のチェックを実施
  // ...
}
```

## TanStack Query の Provider 設定

`QueryClientProvider` は `components/elements/query-provider.tsx` に配置し、ルートレイアウトから使用する。

```tsx
// components/elements/query-provider.tsx
"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
```

```tsx
// app/layout.tsx — ルートレイアウトで Provider を適用
import { QueryProvider } from "@/components/elements/query-provider";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body>
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
```

## DI（依存性の注入）

[clean-architecture.md](../../architecture/clean-architecture.md) / [solid-principle.md](../../architecture/solid-principle.md)（DIP）に従い、Domain 層で定義したインターフェースを Infrastructure 層で実装する。Next.js ではクラスベースの DI コンテナではなく、関数ベースの注入を採用する。

```typescript
// features/auth/repositories/user-repository.ts — feature 内の Repository インターフェース（Port）
import type { User } from "@/features/auth/models/user";

export interface UserRepository {
  findById(id: string): Promise<User | null>;
  save(user: User): Promise<void>;
}
```

```typescript
// lib/repositories/drizzle-user-repository.ts — Infrastructure 層: 実装（Adapter）
import type { UserRepository } from "@/features/auth/repositories/user-repository";
import type { User } from "@/features/auth/models/user";
import { eq } from "drizzle-orm";
import { users } from "@/lib/db/schema";
import type { DbClient } from "@/lib/db";

export function createDrizzleUserRepository(db: DbClient): UserRepository {
  return {
    async findById(id: string): Promise<User | null> {
      const record = await db.query.users.findFirst({
        where: eq(users.id, id),
      });
      if (!record) return null;
      // Infrastructure の型を Domain の型に変換
      return { id: record.id, name: record.name, email: record.email };
    },
    async save(user: User): Promise<void> {
      await db
        .insert(users)
        .values(user)
        .onConflictDoUpdate({ target: users.id, set: user });
    },
  };
}
```

```typescript
// features/auth/lib/get-user.ts — Server Component から利用する取得関数
import { createDrizzleUserRepository } from "@/lib/repositories/drizzle-user-repository";
import { db } from "@/lib/db";

export async function getUser(id: string) {
  const userRepo = createDrizzleUserRepository(db);
  return userRepo.findById(id);
}
```

## 環境変数の管理

環境変数は `lib/env.ts` で一元管理する。`process.env` を直接参照せず、`env.ts` からインポートして使用する。[contract-programming.md](../../architecture/contract-programming.md) に従い、起動時にバリデーションを行い不正な値の混入を防ぐ。

```typescript
// lib/env.ts — 環境変数の一元管理・バリデーション
import { Type, type Static } from "@sinclair/typebox";
import { Value } from "@sinclair/typebox/value";

const EnvSchema = Type.Object({
  DATABASE_URL: Type.String({ minLength: 1 }),
  NEXT_PUBLIC_APP_URL: Type.String({ minLength: 1 }),
  // 必要に応じて追加
});

type Env = Static<typeof EnvSchema>;

function validateEnv(): Env {
  const env = {
    DATABASE_URL: process.env.DATABASE_URL,
    NEXT_PUBLIC_APP_URL: process.env.NEXT_PUBLIC_APP_URL,
  };

  if (!Value.Check(EnvSchema, env)) {
    const errors = [...Value.Errors(EnvSchema, env)];
    throw new Error(
      `Environment variable validation failed:\n${errors.map((e) => `  ${e.path}: ${e.message}`).join("\n")}`,
    );
  }

  return env;
}

export const env = validateEnv();
```

```typescript
// Good — env.ts 経由で参照
import { env } from "@/lib/env";
const dbUrl = env.DATABASE_URL;

// Bad — process.env を直接参照
const dbUrl = process.env.DATABASE_URL;
```

## エラーハンドリング

[contract-programming.md](../../architecture/contract-programming.md) に従い、以下の方針で実装する。

| レイヤー | 方針 |
| --- | --- |
| Domain 層 | 事前条件違反は例外を throw する（不正な状態のオブジェクトを生成させない） |
| Server Actions | バリデーションエラーは Result 型（`{ success, error }`）で返す。予期しないエラーは catch して汎用メッセージを返す |
| Server Components | `error.tsx` でキャッチし、ユーザーにフォールバック UI を表示する |
| Client Components | `useActionState` の戻り値でエラー状態を管理する |

```tsx
// app/dashboard/error.tsx — Next.js のエラーバウンダリ
"use client";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div>
      <h2>エラーが発生しました</h2>
      <button onClick={reset}>再試行</button>
    </div>
  );
}
```

## ドメインモデルの実装

[domain-model.md](../../architecture/domain-model.md) に従い、値オブジェクトとエンティティを実装する。Next.js ではクラスインスタンスの Server → Client 受け渡しに制約があるため、**Server Component 内でのみ使用するか、プレーンオブジェクトに変換してから Client に渡す**。

```typescript
// features/auth/models/user.ts
// 値オブジェクト: Email
export class Email {
  readonly value: string;

  constructor(value: string) {
    // 事前条件（contract-programming.md）
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
      throw new Error(`Invalid email format: ${value}`);
    }
    this.value = value;
  }

  equals(other: Email): boolean {
    return this.value === other.value;
  }
}

// エンティティ: User
export class User {
  constructor(
    readonly id: string,
    private _name: string,
    private _email: Email,
  ) {
    // 事前条件
    if (_name.trim() === "") {
      throw new Error("name is required");
    }
  }

  get name(): string {
    return this._name;
  }

  get email(): Email {
    return this._email;
  }

  // ビジネス意図を表すメソッドで状態を変更する
  changeName(newName: string): void {
    if (newName.trim() === "") {
      throw new Error("name is required");
    }
    this._name = newName;
  }

  // Client Component に渡す際はプレーンオブジェクトに変換
  toPlain() {
    return {
      id: this.id,
      name: this._name,
      email: this._email.value,
    };
  }
}
```
