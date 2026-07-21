# SolidJS + TanStack Start 固有の実装パターン

## リアクティビティの基本

SolidJS はシグナルベースの細粒度リアクティビティシステムを採用しており、仮想 DOM を使用しない。コンポーネントは一度だけ実行され、シグナルの変更時に必要な DOM 箇所のみが更新される。

**原則: JSX 内でシグナルを参照する際は関数呼び出し（`count()`）とし、分割代入やローカル変数への展開を避ける。**

```tsx
// Good — シグナルを直接 JSX 内で呼び出す
function Counter() {
  const [count, setCount] = createSignal(0);

  return <p>{count()}</p>;
}

// Bad — 分割代入するとリアクティビティが失われる
function Counter() {
  const [count, setCount] = createSignal(0);
  const value = count(); // この時点で値が固定される

  return <p>{value}</p>;
}
```

## コンポーネント設計

SolidJS ではすべてのコンポーネントがクライアントで実行される。Server Components の概念はない。データ取得はルートの `loader` や `createServerFn` で行い、コンポーネントはその結果を受け取って表示する。

| 判断基準 | 使うもの |
| --- | --- |
| データ取得が必要 | ルートの `loader` + `createServerFn` |
| ユーザーインタラクション | `createSignal` / `createStore` で状態管理 |
| フォーム送信・ミューテーション | Server Function + TanStack Query の `createMutation` |

```tsx
// features/dashboard/components/stats-card.tsx
import type { DashboardStats } from "~/features/dashboard/types";

interface StatsCardProps {
  stats: DashboardStats;
}

export function StatsCard(props: StatsCardProps) {
  return (
    <div>
      <p>{props.stats.totalUsers}</p>
      <p>{props.stats.totalRevenue}</p>
    </div>
  );
}
```

```tsx
// features/auth/components/login-form.tsx
import { createSignal } from "solid-js";
import { loginFn } from "~/features/auth/server/login";

export function LoginForm() {
  const [error, setError] = createSignal<string | undefined>();
  const [isPending, setIsPending] = createSignal(false);

  async function handleSubmit(e: SubmitEvent) {
    e.preventDefault();
    setIsPending(true);
    setError(undefined);

    const formData = new FormData(e.currentTarget as HTMLFormElement);
    const result = await loginFn({ data: {
      email: formData.get("email") as string,
      password: formData.get("password") as string,
    }});

    setIsPending(false);
    if (!result.success) {
      setError(result.error);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <input name="email" type="email" />
      <input name="password" type="password" />
      <button type="submit" disabled={isPending()}>
        ログイン
      </button>
      {error() && <p>{error()}</p>}
    </form>
  );
}
```

## Server Functions

Server Functions は `createServerFn` を使用して定義する。feature 内の `server/` ディレクトリに配置する。[contract-programming.md](../../architecture/contract-programming.md) に従い、入力の事前条件を検証する。

```typescript
// features/auth/server/login.ts
import { createServerFn } from "@tanstack/start";
import { Type, type Static } from "@sinclair/typebox";
import { Value } from "@sinclair/typebox/value";

const LoginSchema = Type.Object({
  email: Type.String({ format: "email" }),
  password: Type.String({ minLength: 8 }),
});

type LoginInput = Static<typeof LoginSchema>;

interface LoginResult {
  success: boolean;
  error?: string;
}

export const loginFn = createServerFn({ method: "POST" })
  .validator((input: unknown): LoginInput => {
    if (!Value.Check(LoginSchema, input)) {
      const errors = [...Value.Errors(LoginSchema, input)];
      throw new Error(errors[0]?.message ?? "入力が不正です");
    }
    return input as LoginInput;
  })
  .handler(async ({ data }): Promise<LoginResult> => {
    // ビジネスロジックの実行
    // ...

    return { success: true };
  });
```

## データ取得パターン

| パターン | 実装方法 | 使い分け |
| --- | --- | --- |
| ルートローダーでの取得 | `createServerFn` + ルートの `loader` | 初回表示に必要なデータ |
| クライアントサイド取得 | TanStack Query (`createQuery`) | リアルタイム更新・ポーリングが必要な場合 |
| ミューテーション | Server Functions + `createMutation` | フォーム送信・データ変更 |

- ルートの `loader` で `createServerFn` を呼び出し、サーバーサイドでデータを取得する
- クライアントサイドで追加のデータ取得が必要な場合は TanStack Query を使用する
- API Routes は「外部サービスからの Webhook 受信」等、限定的な用途にのみ使用する

```tsx
// features/dashboard/server/get-dashboard-stats.ts
import { createServerFn } from "@tanstack/start";
import { getDashboardStats } from "~/features/dashboard/lib/get-dashboard-stats";
import { getSession } from "~/features/auth/lib/get-session";

export const getDashboardStatsFn = createServerFn({ method: "GET" })
  .handler(async () => {
    const session = await getSession();
    if (!session) {
      throw new Error("Unauthorized");
    }
    return getDashboardStats();
  });
```

```tsx
// routes/dashboard/index.tsx — ルートローダーでデータ取得
import { createFileRoute } from "@tanstack/react-router";
import { getDashboardStatsFn } from "~/features/dashboard/server/get-dashboard-stats";
import { StatsCard } from "~/features/dashboard/components/stats-card";
import { ActivityFeed } from "~/features/dashboard/components/activity-feed";

export const Route = createFileRoute("/dashboard/")({
  loader: async () => {
    const stats = await getDashboardStatsFn();
    return { stats };
  },
  component: DashboardPage,
});

function DashboardPage() {
  const { stats } = Route.useLoaderData();

  return (
    <div>
      <StatsCard stats={stats} />
      <ActivityFeed />
    </div>
  );
}
```

```tsx
// features/dashboard/hooks/use-dashboard-stats.ts — TanStack Query でクライアントサイド取得
import { createQuery } from "@tanstack/solid-query";
import { getDashboardStatsFn } from "~/features/dashboard/server/get-dashboard-stats";
import type { DashboardStats } from "~/features/dashboard/types";

export function useDashboardStats() {
  return createQuery<DashboardStats>(() => ({
    queryKey: ["dashboard", "stats"],
    queryFn: () => getDashboardStatsFn(),
  }));
}
```

## ルートローダーの認証チェック

認証チェックはルートの `beforeLoad` で個別に実施する。ミドルウェアによる一括制御ではなく、各ルートで明示的にチェックすることで、認証要否がコードから読み取れるようにする。

```typescript
// routes/dashboard/route.tsx — レイアウトルートで認証チェック
import { createFileRoute, redirect } from "@tanstack/react-router";
import { getSession } from "~/features/auth/lib/get-session";

export const Route = createFileRoute("/dashboard")({
  beforeLoad: async () => {
    const session = await getSession();
    if (!session) {
      throw redirect({ to: "/login" });
    }
  },
});
```

## TanStack Query の Provider 設定

`QueryClientProvider` は `components/elements/query-provider.tsx` に配置し、ルートレイアウトから使用する。

```tsx
// components/elements/query-provider.tsx
import { QueryClient, QueryClientProvider } from "@tanstack/solid-query";
import type { JSX } from "solid-js";

const queryClient = new QueryClient();

interface QueryProviderProps {
  children: JSX.Element;
}

export function QueryProvider(props: QueryProviderProps) {
  return (
    <QueryClientProvider client={queryClient}>
      {props.children}
    </QueryClientProvider>
  );
}
```

```tsx
// routes/__root.tsx — ルートレイアウトで Provider を適用
import { createRootRoute, Outlet } from "@tanstack/react-router";
import { QueryProvider } from "~/components/elements/query-provider";

export const Route = createRootRoute({
  component: RootLayout,
});

function RootLayout() {
  return (
    <html lang="ja">
      <body>
        <QueryProvider>
          <Outlet />
        </QueryProvider>
      </body>
    </html>
  );
}
```

## DI（依存性の注入）

[clean-architecture.md](../../architecture/clean-architecture.md) / [solid-principle.md](../../architecture/solid-principle.md)（DIP）に従い、Domain 層で定義したインターフェースを Infrastructure 層で実装する。関数ベースの注入を採用する。

```typescript
// features/auth/repositories/user-repository.ts — feature 内の Repository インターフェース（Port）
import type { User } from "~/features/auth/models/user";

export interface UserRepository {
  findById(id: string): Promise<User | null>;
  save(user: User): Promise<void>;
}
```

```typescript
// lib/repositories/drizzle-user-repository.ts — Infrastructure 層: 実装（Adapter）
import type { UserRepository } from "~/features/auth/repositories/user-repository";
import type { User } from "~/features/auth/models/user";
import { eq } from "drizzle-orm";
import { users } from "~/lib/db/schema";
import type { DbClient } from "~/lib/db";

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
// features/auth/lib/get-user.ts — Server Function から利用する取得関数
import { createDrizzleUserRepository } from "~/lib/repositories/drizzle-user-repository";
import { db } from "~/lib/db";

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
  VITE_APP_URL: Type.String({ minLength: 1 }),
  // 必要に応じて追加
});

type Env = Static<typeof EnvSchema>;

function validateEnv(): Env {
  const env = {
    DATABASE_URL: process.env.DATABASE_URL,
    VITE_APP_URL: import.meta.env.VITE_APP_URL,
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
import { env } from "~/lib/env";
const dbUrl = env.DATABASE_URL;

// Bad — process.env を直接参照
const dbUrl = process.env.DATABASE_URL;
```

## エラーハンドリング

[contract-programming.md](../../architecture/contract-programming.md) に従い、以下の方針で実装する。

| レイヤー | 方針 |
| --- | --- |
| Domain 層 | 事前条件違反は例外を throw する（不正な状態のオブジェクトを生成させない） |
| Server Functions | バリデーションエラーは Result 型（`{ success, error }`）で返す。予期しないエラーは catch して汎用メッセージを返す |
| ルートエラー | `errorComponent` でキャッチし、ユーザーにフォールバック UI を表示する |
| コンポーネント | `ErrorBoundary` でキャッチし、フォールバック UI を表示する |

```tsx
// routes/dashboard/index.tsx — TanStack Router のエラーコンポーネント
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/dashboard/")({
  errorComponent: DashboardError,
  // ...
});

function DashboardError({ error }: { error: Error }) {
  return (
    <div>
      <h2>エラーが発生しました</h2>
      <button onClick={() => window.location.reload()}>再試行</button>
    </div>
  );
}
```

```tsx
// SolidJS の ErrorBoundary によるエラーキャッチ
import { ErrorBoundary } from "solid-js";

function DashboardPage() {
  return (
    <ErrorBoundary fallback={(err) => <p>エラー: {err.message}</p>}>
      <StatsCard />
    </ErrorBoundary>
  );
}
```

## ドメインモデルの実装

[domain-model.md](../../architecture/domain-model.md) に従い、値オブジェクトとエンティティを実装する。SolidJS ではすべてがクライアントで実行されるが、**ドメインモデルはリアクティブシステムに依存しない純粋なクラスとして実装する**。コンポーネントへ渡す際はプレーンオブジェクトに変換する。

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

  // コンポーネントに渡す際はプレーンオブジェクトに変換
  toPlain() {
    return {
      id: this.id,
      name: this._name,
      email: this._email.value,
    };
  }
}
```
