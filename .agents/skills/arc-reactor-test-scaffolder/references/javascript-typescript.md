# JavaScript / TypeScript デフォルト流儀（既存テストが無い場合に使う）

デフォルト FW: **vitest**（`package.json` に jest があれば jest。API はほぼ共通）。
検出優先順位: devDependencies の `vitest` > `jest` > `mocha`。`scripts.test` も確認する。

## 配置・命名

- 配置: **実装ファイルと併置**。例: `src/service/user.ts` → `src/service/user.test.ts`
  （`__tests__/` や `tests/` ディレクトリが既にあるプロジェクトではそちらに従う）
- ファイル名: `<name>.test.ts`（jest 系では `.spec.ts` 併用例も多い。既存に合わせる）
- テスト名: `describe` に対象（クラス/関数名）、`it` に振る舞いを英語の文で書く。

## スタイル

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { UserService } from "./user";

describe("UserService", () => {
  describe("getUser", () => {
    it("returns the user for a valid id", async () => {
      const service = new UserService(fakeRepo);
      const user = await service.getUser("u1");
      expect(user.id).toBe("u1");
    });

    it("throws NotFoundError for an unknown id", async () => {
      const service = new UserService(fakeRepo);
      await expect(service.getUser("nope")).rejects.toThrow(NotFoundError);
    });
  });
});
```

- アサーション: `expect(...).toBe / toEqual / toThrow / rejects.toThrow`。
  オブジェクト比較は `toEqual`（参照比較の `toBe` と使い分ける）。
- パラメタライズ: `it.each([[input, expected], ...])("case %s", ...)` を境界値テストに使う。
- モック: vitest は `vi.mock` / `vi.fn` / `vi.spyOn`、jest は `jest.mock` / `jest.fn`。
  モジュールモックより依存注入（引数・コンストラクタ）でのフェイク差し替えを優先する。
- setup: `beforeEach` で状態リセット。テスト間の状態共有を作らない。
- 未確定ケース: `it.todo("...")` または `it.skip`。

## 実行

```bash
npx vitest run src/service/user.test.ts     # vitest（watch なし）
npx jest src/service/user.test.ts           # jest
```

FW 検出の手がかり: `vitest.config.*` / `jest.config.*` / `package.json` の `jest` キーと
`scripts.test`。TS プロジェクトでは tsconfig の paths エイリアスを import に反映すること。
