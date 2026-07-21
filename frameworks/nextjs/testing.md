# テストの書き方

テスト戦略は **テスティングトロフィー** に従い、インテグレーションテストを最も厚くする。
詳細は [testing-trophy.md](../../testing/testing-trophy.md) を参照。

## ツールチェーン

| 用途 | ツール |
| --- | --- |
| テストランナー / アサーション | Vitest |
| コンポーネントテスト（DOM） | Vitest + React Testing Library |
| ビジュアルテスト / コンポーネントカタログ | Storybook |
| E2E テスト | Playwright |
| 静的解析 | TypeScript + ESLint + Prettier |

<!-- TODO: Storybook のインタラクションテストを Integration に含めるか、Component 層に留めるかはプロジェクトで決定する -->

## テスト種別と対象

| テスト種別 | 対象 | ツール |
| --- | --- | --- |
| Static Analysis | 全ソースコード | TypeScript, ESLint, Prettier |
| Unit | 純粋関数・バリデーション・データ変換 | Vitest |
| Component | 再利用可能な UI コンポーネントの描画・操作 | Vitest + React Testing Library, Storybook |
| Integration | 機能単位のユーザーフロー（フォーム送信→バリデーション→API→結果表示） | Vitest + React Testing Library |
| E2E | クリティカルパス（認証、購入、データ登録など） | Playwright |

## テストの構成

AAA（Arrange-Act-Assert）パターンで記述する。

```typescript
// features/auth/lib/validate-credentials.test.ts
describe("validateCredentials", () => {
  test("有効なメールアドレスとパスワードで true を返す", () => {
    // Arrange
    const email = "user@example.com";
    const password = "validPassword123";

    // Act
    const result = validateCredentials(email, password);

    // Assert
    expect(result).toBe(true);
  });
});
```

## テストの配置

テストファイルは対象ファイルと同じディレクトリに `*.test.ts(x)` として配置する。
Storybook のストーリーファイルも同様に `*.stories.tsx` として配置する。

```
features/auth/
├── lib/
│   ├── validate-credentials.ts
│   └── validate-credentials.test.ts      # Unit
├── actions/
│   ├── login-action.ts
│   └── login-action.test.ts              # Integration
└── components/
    ├── login-form.tsx
    ├── login-form.test.tsx               # Component / Integration
    └── login-form.stories.tsx            # Storybook
```

<!-- TODO: E2E テストの配置先（e2e/ ディレクトリ or tests/ ディレクトリ）はプロジェクトで決定する -->

## モックの作成方法

モックは**システム境界（外部 API・タイマー等）だけ**に使い、内部モジュール間のモックは避ける。

DIP に従い、Domain 層で定義したインターフェースのモック実装を注入する。テストフレームワークのモック機能よりも手動スタブを優先する。

```typescript
// テスト用の手動スタブ
import type { UserRepository } from "@/domain/repositories/user-repository";

function createMockUserRepository(overrides?: Partial<UserRepository>): UserRepository {
  return {
    findById: async () => null,
    save: async () => {},
    ...overrides,
  };
}

// 使用例
test("ユーザーが見つからない場合 null を返す", async () => {
  const repo = createMockUserRepository({
    findById: async () => null,
  });

  const result = await repo.findById("non-existent-id");
  expect(result).toBeNull();
});
```

## Integration テストの書き方

インテグレーションテストはユーザーの操作フローに沿って記述する。コンポーネント間の結合はモックしない。

```typescript
// features/auth/components/login-form.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

describe("LoginForm", () => {
  test("メールアドレスとパスワードを入力してログインできる", async () => {
    // Arrange
    const user = userEvent.setup();
    render(<LoginForm />);

    // Act
    await user.type(screen.getByLabelText("メールアドレス"), "user@example.com");
    await user.type(screen.getByLabelText("パスワード"), "password123");
    await user.click(screen.getByRole("button", { name: "ログイン" }));

    // Assert
    expect(await screen.findByText("ログインしました")).toBeInTheDocument();
  });
});
```

## Storybook の書き方

コンポーネントの Props バリエーションをストーリーとして定義し、ビジュアルの確認とドキュメント化を兼ねる。

```typescript
// features/auth/components/login-form.stories.tsx
import type { Meta, StoryObj } from "@storybook/react";
import { LoginForm } from "./login-form";

const meta = {
  component: LoginForm,
} satisfies Meta<typeof LoginForm>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const WithError: Story = {
  args: {
    error: "メールアドレスまたはパスワードが正しくありません",
  },
};
```

<!-- TODO: Storybook のビジュアルリグレッションテストツール（Chromatic 等）を導入するかはプロジェクトで決定する -->

## E2E テストの書き方

クリティカルパスに絞り、モックを使わず本番に近い環境で実行する。

```typescript
// e2e/auth.spec.ts
import { test, expect } from "@playwright/test";

test("ログインして dashboard にリダイレクトされる", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("メールアドレス").fill("user@example.com");
  await page.getByLabel("パスワード").fill("password123");
  await page.getByRole("button", { name: "ログイン" }).click();

  await expect(page).toHaveURL("/dashboard");
});
```

## テスト実行タイミング

| タイミング | 実行対象 | 目的 |
|-----------|---------|------|
| ファイル保存時 | Static Analysis + 関連 Unit | 即時フィードバック |
| PR 作成時 | Unit + Component + Integration | 変更の安全性を担保 |
| main マージ後 | 全テスト（E2E 含む） | リリース品質の確認 |

## テスト設計の原則

1. **ユーザーの使い方に沿ってテストする** — 実装詳細ではなく、ユーザーが見るもの・操作するものを検証する
2. **モックは境界だけ** — 外部 API・タイマーなどシステム境界のみモックし、内部モジュール間のモックは避ける
3. **テストがリファクタリングを妨げたら設計を見直す** — 実装に密結合したテストは負債になる
4. **1テスト1アサーションに固執しない** — 1つのユーザーフローを1テストでまとめて検証してよい
5. **カバレッジは指標であり目標ではない** — 数値を追うのではなく、ユーザーにとって重要なパスがカバーされているかを重視する

## カバレッジ目標

<!-- TODO: 目標値はプロジェクトの品質要件に応じて決定する -->

| 対象 | 目標 |
|------|------|
| 全体 | ___% |
| ビジネスロジック（utils, hooks） | ___% |
| クリティカルパス（E2E） | 主要シナリオ 100% |
