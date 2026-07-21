# 機能ベースアーキテクチャ (Feature-Based Architecture)

## 概要

UIを機能（feature）単位でモジュール化し、関連するコンポーネント・hooks・型・ユーティリティを同じディレクトリに配置するアーキテクチャ。技術的関心（components/hooks/utils）ではなくビジネス上の関心（認証/決済/ダッシュボード）でコードを分割することで、機能の追加・削除・変更の影響範囲を局所化する。

## ディレクトリ構成

```
src/
├── app/                    # ルーティング・ページ（Next.js App Router等）
│   ├── layout.tsx
│   ├── page.tsx
│   └── dashboard/
│       ├── layout.tsx
│       └── page.tsx
├── features/               # 機能モジュール（ビジネスドメイン単位）
│   ├── auth/
│   │   ├── components/
│   │   │   ├── login-form.tsx
│   │   │   └── signup-form.tsx
│   │   ├── hooks/
│   │   │   └── use-auth.ts
│   │   ├── lib/
│   │   │   └── validate-credentials.ts
│   │   └── types.ts
│   └── dashboard/
│       ├── components/
│       │   ├── stats-card.tsx
│       │   └── activity-feed.tsx
│       ├── hooks/
│       │   └── use-dashboard-data.ts
│       └── types.ts
├── components/             # 共通UIコンポーネント・レイアウト
│   ├── ui/                 # 汎用UIプリミティブ（Button, Input, Modal等）
│   │   ├── button.tsx
│   │   ├── input.tsx
│   │   └── modal.tsx
│   └── layout/             # 共通レイアウト
│       ├── header.tsx
│       ├── sidebar.tsx
│       └── footer.tsx
└── lib/                    # 共通ユーティリティ・設定
    ├── api-client.ts
    ├── constants.ts
    ├── format.ts
    └── cn.ts
```

### 各ディレクトリの責務

| ディレクトリ | 責務 | 配置基準 |
|---|---|---|
| `app/` | ルーティング定義とページの組み立て。フレームワークの規約に従う | Next.js App Routerの規約通り |
| `features/` | ビジネスロジックとそれに紐づくUI | 特定の機能ドメインに属するもの |
| `components/` | 2つ以上のfeatureから使われる共通UI・レイアウト | ドメイン非依存で再利用可能なもの |
| `lib/` | 2つ以上の場所から使われる共通関数・設定 | ドメイン非依存なユーティリティ |

## ルール

- feature間の依存は許可するが、循環依存は禁止する。依存方向に迷う場合は共通部分を `lib/` または新しいfeatureに切り出す
- `app/` のページコンポーネントはfeatureのコンポーネントを組み立てるだけに留め、ビジネスロジックを持たない
- `components/` に配置するコンポーネントはドメイン固有のpropsや型に依存してはならない
- `lib/` に配置する関数はドメイン固有のロジックを含んではならない
- バレルファイル（`index.ts`）は使用しない。各モジュールを直接importする
- featureディレクトリ内のファイルが1つしかない場合はサブディレクトリ（`components/`, `hooks/`等）を省略してよい。ファイルが増えたタイミングでサブディレクトリに分割する

## コンポーネント分割ガイド

### 分割の粒度

| レベル | 名称 | 説明 | 例 |
|---|---|---|---|
| 1 | ページ | ルートに対応。featureコンポーネントの組み立てのみ | `app/dashboard/page.tsx` |
| 2 | 機能コンポーネント | 1つのユースケースを完結させるUI。状態管理・データ取得を持つ | `features/auth/components/login-form.tsx` |
| 3 | UIパーツ | 機能コンポーネント内で再利用される表示専用の部品 | `features/dashboard/components/stats-card.tsx` |
| 4 | 共通UIプリミティブ | feature横断で使われるデザインシステムの部品 | `components/ui/button.tsx` |

### 分割の判断基準

| こういう場合 | こうする |
|---|---|
| コンポーネントが200行を超えた | 表示ロジックの塊をUIパーツとして切り出す |
| 同じfeature内で同じUI構造が2回以上出現 | feature内の `components/` に共通パーツとして切り出す |
| 2つ以上のfeatureで同じUI構造が出現 | `components/ui/` に移動する |
| hooksが複雑化して50行を超えた | 責務ごとにhooksを分割する |
| コンポーネントがpropsを5個以上受け取る | 関連するpropsをオブジェクトにまとめるか、コンポーネントの責務分割を検討する |

## 判断ガイド

| こういう場合 | こうする |
|---|---|
| あるコンポーネントが1つのfeatureでしか使われない | そのfeatureの `components/` に置く |
| 2つ以上のfeatureで使われるUIコンポーネントが出てきた | `components/ui/` に移動する |
| featureをまたぐ共通関数が必要になった | `lib/` に置く |
| feature内のユーティリティが他featureでも必要になった | `lib/` に昇格させる |
| あるfeatureが肥大化した（ファイル15個以上目安） | サブfeatureへの分割を検討する |
| ページ固有のレイアウトがある | `app/` 側の `layout.tsx` で定義する |
| 複数ページで共通のレイアウトがある | `components/layout/` に置く |
| API呼び出しのロジックをどこに置くか迷う | feature内の `hooks/` または `lib/` に置く。APIクライアント自体は `lib/api-client.ts` |

## 適用例

### Good

```
src/
├── app/
│   └── dashboard/
│       └── page.tsx          # featureの組み立てのみ
├── features/
│   └── dashboard/
│       ├── components/
│       │   ├── stats-card.tsx
│       │   └── activity-feed.tsx
│       ├── hooks/
│       │   └── use-dashboard-data.ts
│       └── types.ts
├── components/
│   └── ui/
│       └── card.tsx           # 汎用Card（ドメイン非依存）
└── lib/
    └── format.ts              # 日付・数値フォーマット等
```

```tsx
// app/dashboard/page.tsx — 組み立てのみ
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

### Bad

```
src/
├── components/           # 技術的関心で分類 → どの機能のものか不明
│   ├── StatsCard.tsx
│   ├── LoginForm.tsx
│   ├── ActivityFeed.tsx
│   └── Button.tsx
├── hooks/                # 全hooksが平置き → 依存関係が見えない
│   ├── useDashboardData.ts
│   └── useAuth.ts
└── utils/
    └── format.ts
```

```tsx
// app/dashboard/page.tsx — ページにビジネスロジックが混在
import { useDashboardData } from "@/hooks/useDashboardData";
import { StatsCard } from "@/components/StatsCard";

export default function DashboardPage() {
  const { data, isLoading } = useDashboardData();

  // ページコンポーネント内でデータ加工 → featureに寄せるべき
  const filteredStats = data?.stats.filter((s) => s.value > 0);

  return <StatsCard stats={filteredStats} isLoading={isLoading} />;
}
```
