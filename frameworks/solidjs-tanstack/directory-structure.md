# ディレクトリ構成

[feature-based.md](../../architecture/feature-based.md) のディレクトリ構成を TanStack Start のファイルベースルーティングに適用する。

```
src/
├── routes/                        # TanStack Router — ファイルベースルーティング
│   ├── __root.tsx                 # ルートレイアウト
│   ├── index.tsx                  # / ページ
│   ├── _auth/                     # レイアウトルート — 認証系ページをグルーピング
│   │   ├── login.tsx
│   │   └── signup.tsx
│   ├── dashboard/
│   │   ├── route.tsx              # /dashboard レイアウト
│   │   └── index.tsx              # /dashboard ページ
│   └── api/                       # API Routes（クライアントサイド取得用 GET / Webhook 受信用）
│       ├── dashboard.stats.ts
│       └── webhooks.ts
├── features/                      # 機能モジュール（ビジネスドメイン単位）
│   ├── auth/
│   │   ├── components/
│   │   │   ├── login-form.tsx
│   │   │   └── signup-form.tsx
│   │   ├── hooks/
│   │   │   └── use-auth.ts
│   │   ├── server/                # Server Functions（サーバーサイド処理）
│   │   │   └── login.ts
│   │   ├── lib/
│   │   │   └── validate-credentials.ts
│   │   ├── models/                # ドメインモデル（エンティティ・値オブジェクト）
│   │   │   └── user.ts
│   │   ├── repositories/          # Repository インターフェース（Port）
│   │   │   └── user-repository.ts
│   │   └── types.ts
│   └── dashboard/
│       ├── components/
│       │   ├── stats-card.tsx
│       │   └── activity-feed.tsx
│       ├── hooks/
│       │   └── use-dashboard-stats.ts
│       └── types.ts
├── components/                    # 共通 UI コンポーネント
│   ├── ui/                        # 汎用 UI プリミティブ（Button, Input, Modal 等）
│   │   ├── button.tsx
│   │   ├── input.tsx
│   │   └── modal.tsx
│   ├── elements/                  # アプリ全体の Provider・ラッパー等
│   │   └── query-provider.tsx
│   └── layout/                    # 共通レイアウト部品
│       ├── header.tsx
│       ├── sidebar.tsx
│       └── footer.tsx
├── lib/                           # 共通ユーティリティ・設定
│   ├── db/                        # Drizzle クライアント・スキーマ定義
│   │   ├── index.ts               # DB クライアントの生成・エクスポート
│   │   ├── schema.ts              # Drizzle スキーマ定義
│   │   └── migrations/            # マイグレーションファイル
│   ├── repositories/              # Repository 実装（Adapter）
│   │   └── drizzle-user-repository.ts
│   ├── env.ts                     # 環境変数の一元管理・バリデーション
│   ├── api-client.ts
│   ├── constants.ts
│   ├── format.ts
│   └── cn.ts
```

## 各ディレクトリの責務（feature-based.md に加えた TanStack Start 固有の拡張）

| ディレクトリ | 責務 | 配置基準 |
| --- | --- | --- |
| `routes/` | ルーティング定義とページの組み立て。ビジネスロジックを持たない | TanStack Router のファイルベースルーティング規約通り |
| `features/` | ビジネスロジックとそれに紐づく UI・Server Functions・ドメインモデル | 特定の機能ドメインに属するもの |
| `features/*/server/` | Server Functions（`createServerFn`）。サーバーサイドで実行されるミューテーション・取得処理 | feature に紐づくサーバー側処理 |
| `features/*/models/` | エンティティ・値オブジェクト（[domain-model.md](../../architecture/domain-model.md) に従う） | その feature 固有のドメインモデル |
| `features/*/repositories/` | Repository インターフェース（Port） | そのドメインモデルの永続化契約 |
| `components/` | 2つ以上の feature から使われる共通 UI | ドメイン非依存で再利用可能なもの |
| `components/elements/` | アプリ全体の Provider・ラッパー等 | 横断的な関心事のコンポーネント |
| `lib/` | 2つ以上の場所から使われる共通関数・設定 | ドメイン非依存なユーティリティ |
| `lib/db/` | Drizzle クライアント・スキーマ・マイグレーション | DB 接続とスキーマ定義 |
| `lib/repositories/` | Repository 実装（Adapter）。Drizzle 等の技術要素に依存 | [clean-architecture.md](../../architecture/clean-architecture.md) の Infrastructure 層 |

## バレルファイルの禁止

`index.ts` によるバレルファイルは使用しない。各モジュールを直接 import する。

```tsx
// Good
import { LoginForm } from "~/features/auth/components/login-form";

// Bad
import { LoginForm } from "~/features/auth";
```
