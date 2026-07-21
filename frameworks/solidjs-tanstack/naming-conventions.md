# 命名規則

| 対象 | 形式 | 例 |
| ---- | ---- | --- |
| 変数・関数 | camelCase | `getUserName`, `isLoading` |
| 型・インターフェース | PascalCase | `User`, `UserRepository` |
| 定数 | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT`, `API_BASE_URL` |
| ファイル名（コンポーネント） | kebab-case | `login-form.tsx`, `stats-card.tsx` |
| ファイル名（hooks） | kebab-case, `use-` prefix | `use-auth.ts` |
| ファイル名（Server Functions） | kebab-case | `login.ts` |
| シグナル | camelCase, getter/setter ペア | `count` / `setCount`, `isOpen` / `setIsOpen` |
| 真偽値 | `is` / `has` / `can` + 形容詞/過去分詞 | `isLoading`, `hasPermission`, `canEdit` |
| イベントハンドラ | `handle` + 動詞 | `handleSubmit`, `handleClick` |
| props のコールバック | `on` + 動詞 | `onSubmit`, `onClick` |

## `interface` と `type` の使い分け

- **基本は `interface` を使用する。** オブジェクト型の定義には `interface` を優先する
- `type` は `interface` で表現できない場合にのみ使用する（ユニオン型、交差型、マップ型、プリミティブのエイリアス等）

```typescript
// Good — interface で表現できるものは interface
interface LoginFormProps {
  onSuccess: () => void;
}

interface LoginResult {
  success: boolean;
  error?: string;
}

// Good — interface で表現できないものは type
type Status = "draft" | "confirmed" | "cancelled";
type ActionState = LoginResult | null;
```

## 型の命名

```typescript
// Props 型はコンポーネント名 + Props
interface LoginFormProps {
  onSuccess: () => void;
}

// Server Function の引数・戻り値
interface LoginInput {
  email: string;
  password: string;
}

interface LoginResult {
  success: boolean;
  error?: string;
}
```
