# 開発環境構築セット

## エディタ設定

<!-- ASSUMPTION: VS Code を主要エディタとして想定 -->

### EditorConfig

プロジェクトルートに `.editorconfig` を配置し、エディタ間の差異を吸収する。

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
indent_style = space
indent_size = 2
insert_final_newline = true
trim_trailing_whitespace = true

[*.md]
trim_trailing_whitespace = false

[Makefile]
indent_style = tab
```

### VS Code 推奨拡張

`.vscode/extensions.json` で共有する。

```json
{
  "recommendations": [
    "editorconfig.editorconfig",
    "dbaeumer.vscode-eslint",
    "esbenp.prettier-vscode"
  ]
}
```

## Linter / Formatter

<!-- ASSUMPTION: TypeScript/JavaScript プロジェクトを主な対象として想定。他言語の場合は適宜読み替え -->

| ツール | 用途 | 設定ファイル |
|--------|------|-------------|
| ESLint | 静的解析 | `eslint.config.js` |
| Prettier | コードフォーマット | `.prettierrc` |
| lint-staged | コミット時の自動チェック | `package.json` or `.lintstagedrc` |
| husky | Git hook 管理 | `.husky/` |

### 基本方針

- フォーマットは Prettier に任せ、ESLint はロジックの問題検出に集中する
- コミット前に lint-staged + husky で自動チェックする
- CI でも同じルールを実行し、ローカルとの差異をなくす

## Docker 構成

<!-- ASSUMPTION: Docker Compose で開発環境を構築する想定 -->

### ディレクトリ構成

```
docker/
├── Dockerfile          # アプリケーション用
├── Dockerfile.dev      # 開発用（ホットリロード対応）
└── compose.yaml        # Docker Compose 定義
```

### 方針

- 開発用と本番用の Dockerfile を分離する
- `compose.yaml` でローカル開発に必要なサービス（DB、キャッシュ等）をまとめる
- ボリュームマウントでソースコードを共有し、ホットリロードを有効にする
- 環境変数は `.env.example` をテンプレートとして管理する（`.env` は `.gitignore` に追加）

### compose.yaml の例

```yaml
services:
  app:
    build:
      context: .
      dockerfile: docker/Dockerfile.dev
    volumes:
      - .:/app
    ports:
      - "3000:3000"
    env_file:
      - .env

  db:
    image: postgres:16
    environment:
      POSTGRES_DB: myapp_dev
      POSTGRES_USER: dev
      POSTGRES_PASSWORD: dev
    ports:
      - "5432:5432"
    volumes:
      - db_data:/var/lib/postgresql/data

volumes:
  db_data:
```

## 環境変数管理

| ファイル | Git 管理 | 用途 |
|----------|:--------:|------|
| `.env.example` | ✅ | テンプレート（値は空またはダミー） |
| `.env` | ❌ | ローカル開発用の実値 |
| `.env.test` | ✅ | テスト用（機密情報を含まない） |

## セットアップ手順テンプレート

新規メンバーが迷わないよう、以下を README に記載する。

```bash
# 1. リポジトリをクローン
git clone <repo-url> && cd <repo-name>

# 2. 環境変数を設定
cp .env.example .env
# .env を編集して必要な値を設定

# 3. 依存関係をインストール
npm install  # or yarn / pnpm

# 4. Docker で開発環境を起動
docker compose up -d

# 5. 開発サーバーを起動
npm run dev
```
