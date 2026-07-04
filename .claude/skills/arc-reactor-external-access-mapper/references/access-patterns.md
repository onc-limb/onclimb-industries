# 外部アクセスの検出パターン

external-access-mapper がスキャンする 7 カテゴリの定義。カテゴリごとに
**シグナル（何を検出するか）/ 検索パターン例 / 接続先・認証方式の読み取り方 / 注意点** を定める。

共通ルール:

- 検出の入口は 3 系統を併用する。単一の入口では見落とすため。
  1. **依存マニフェスト**: `package.json` / `go.mod` / `requirements.txt` / `pyproject.toml` /
     `Gemfile` / `pom.xml` / `build.gradle` / `Cargo.toml` に外部クライアントライブラリが
     あれば、その import・初期化箇所を追う。
  2. **設定・環境変数**: `.env.example`, `.env.sample`, `config/`, `docker-compose.yml`,
     Kubernetes マニフェスト, Terraform 等の IaC から接続系の変数名
     （`*_URL`, `*_HOST`, `*_ENDPOINT`, `*_KEY`, `*_SECRET`, `*_TOKEN`, `*_DSN`）を拾い、
     コード側の参照箇所（`process.env.X`, `os.getenv`, `os.Getenv`, `ENV[...]` 等）を突き合わせる。
  3. **コード直接検索**: 下記カテゴリ別の `rg` パターン。
- 全項目に `file:line` を添える。行を特定できない項目は台帳に載せない。
- 接続先・認証方式をコードから断定できないときは「(推測)」または「不明」と書く。
- **値（接続文字列・キー・トークン）は読んでも転記しない。** ハードコードを見つけたら
  場所だけを記録し、値を伏せて最優先で報告する。

## 1. database — データベース

- **シグナル**: ORM の設定ファイル・スキーマ定義、DB クライアントの初期化、生 SQL ドライバ、
  接続文字列の参照。
- **検索パターン例**:
  - ORM / クライアント: `prisma` (`schema.prisma`), `typeorm` (`DataSource`, `ormconfig`),
    `sequelize`, `knex`, `sqlalchemy` (`create_engine`), `django` (`DATABASES`),
    `gorm.Open`, `database/sql` (`sql.Open`), `ActiveRecord` (`database.yml`),
    `mongoose.connect`, `MongoClient`, `redis.createClient` / `redis.NewClient`
  - 生ドライバ: `pg`, `mysql2`, `psycopg2`, `pymysql`, `jdbc:`, `go-sql-driver`
  - 接続文字列参照: `rg -n "postgres(ql)?://|mysql://|mongodb(\+srv)?://|redis://|DATABASE_URL|_DSN"`
- **接続先の読み取り**: 接続文字列の環境変数名、ORM 設定の `host` / `dialect` / `provider`。
  スキーマ定義（`schema.prisma` の `provider` 等）から DB 種別が確定できる。
- **認証方式**: 接続文字列内クレデンシャル / IAM 認証（RDS IAM auth 等）/ シークレットマネージャ参照。
- **注意点**: Redis はキャッシュ・pub/sub・キューのどれに使われているかで
  カテゴリが変わる（pub/sub・ジョブキューなら 5 に分類し、相互参照を書く）。
  SQLite 等のローカル埋め込み DB は外部アクセスではないので台帳に載せない（免責に一言書く）。

## 2. auth-saas — 認証・認可 SaaS

- **シグナル**: 認証 SaaS の SDK・ミドルウェア・JWT 検証の JWKS エンドポイント参照。
- **検索パターン例**:
  - `auth0`, `@auth0/`, `firebase-admin` / `firebase/auth`, `amazon-cognito` /
    `CognitoIdentityProvider`, `@clerk/`, `@supabase/supabase-js`（`auth` 利用）,
    `next-auth` / `authjs`（プロバイダ設定に外部 IdP）, `passport-*`（OAuth 系 strategy）,
    `okta`, `keycloak`
  - JWKS / issuer: `rg -n "jwks|\.well-known/openid-configuration|issuer.*https?://"`
- **接続先の読み取り**: SDK 初期化の `domain` / `issuer` / `projectId` / `userPoolId`（環境変数名で記録）。
- **認証方式**: SaaS への管理 API はクライアントシークレット / サービスアカウントキー、
  トークン検証のみなら公開鍵取得（外部アクセスは JWKS フェッチ）。
- **注意点**: 「検証のみ（JWKS 取得だけ）」と「管理 API 呼び出しあり（ユーザー作成等）」を
  区別して台帳に書く。障害影響が全く違うため。

## 3. external-api — 外部 API・SaaS

- **シグナル**: HTTP クライアントで外部ホストを呼ぶ箇所、SaaS 専用 SDK。
- **検索パターン例**:
  - HTTP クライアント: `fetch(`, `axios`, `got`, `ky`, `undici`, `requests.`（Python）,
    `httpx`, `urllib`, `http.NewRequest`（Go）, `Net::HTTP`, `Faraday`, `RestTemplate`,
    `WebClient`, `HttpClient`
  - 外部 URL: `rg -n "https?://" --type-not md` して自ホスト・ドキュメント URL を除外
  - 決済: `stripe`, `Stripe(`, `paypal`, `pay.jp`, `komoju`
  - メール: `@sendgrid/`, `sendgrid`, `SESClient` / `ses.send`, `mailgun`, `postmark`, `resend`
  - 通知: `slack` (`chat.postMessage`, webhook URL), `@line/bot-sdk`, `twilio`, `firebase-admin`(FCM)
  - AI / 地図等: `openai`, `@anthropic-ai/`, `googlemaps`, `@google/maps`
- **接続先の読み取り**: SDK 名でサービスが確定。素の HTTP はベース URL 定数・環境変数名から。
  URL が実行時に組み立てられている場合は判る範囲 + 「動的組み立てのため一部不明」と書く。
- **認証方式**: API キー（ヘッダ名 `Authorization: Bearer` / `X-API-Key` 等）/ OAuth /
  Webhook 署名検証（受信側なら「受信」と明記）。
- **注意点**: 外部 API の**受信**（Webhook エンドポイント）は台帳の「利用場面」欄に
  受信である旨を書く。送信と受信で障害調査の向きが逆になる。

## 4. cloud-sdk — クラウド SDK

- **シグナル**: AWS / GCP / Azure SDK のクライアント初期化と API 呼び出し。
- **検索パターン例**:
  - AWS: `@aws-sdk/client-*`, `aws-sdk`, `boto3.client`, `boto3.resource`,
    `aws-sdk-go(-v2)?`, `S3Client`, `SQSClient`, `SNSClient`, `DynamoDBClient`,
    `LambdaClient`, `SecretsManager`, `ssm`
  - GCP: `@google-cloud/*`（`storage`, `pubsub`, `firestore`, `bigquery`）,
    `google-cloud-*`（Python）, `cloud.google.com/go/*`
  - Azure: `@azure/*`（`storage-blob`, `service-bus`, `cosmos`）, `azure-*`（Python）
- **接続先の読み取り**: クライアント種別 + バケット名 / キュー URL / テーブル名の
  環境変数名・定数名。リージョン設定も判れば添える。
- **認証方式**: IAM ロール（実行環境に委譲。明示クレデンシャルなしなら「IAM ロール(推測)」）/
  アクセスキーの環境変数 / サービスアカウント JSON（`GOOGLE_APPLICATION_CREDENTIALS`）。
- **注意点**: S3 / GCS / Blob は 6 (storage)、SQS / PubSub / Service Bus は
  5 (queue-messaging) と重なる。**台帳の分類はサービスの役割側（5 / 6）を優先**し、
  SDK 経由である事実を接続先欄に書く。SecretsManager / SSM 参照は「他の接続の認証情報の
  取得元」なので、該当する接続の認証方式欄にも反映する。

## 5. queue-messaging — キュー・メッセージング

- **シグナル**: メッセージブローカーのクライアント、producer / consumer の定義。
- **検索パターン例**:
  - Kafka: `kafkajs`, `confluent`, `sarama`, `kafka-python`, `spring-kafka`
  - RabbitMQ / AMQP: `amqplib`, `pika`, `amqp091-go`, `bunny`
  - Redis 系: `bull`, `bullmq`, `sidekiq`, `celery`（broker URL）, `resque`,
    `redis` の `publish` / `subscribe` / `xadd`
  - クラウド: `SQSClient`, `@google-cloud/pubsub`, `@azure/service-bus`（分類はこちら優先）
  - NATS / その他: `nats`, `zeromq`, `mqtt`
- **接続先の読み取り**: broker URL の環境変数名、トピック名 / キュー名の定数。
- **認証方式**: SASL / 接続文字列内クレデンシャル / IAM。
- **注意点**: **produce（送る）と consume（受けて処理する）を必ず区別**する。
  consumer はそれ自体がエントリポイント（イベントハンドラ）なので、
  利用場面マップではエントリポイント側にも載せる。

## 6. storage — ストレージ・ファイル

- **シグナル**: オブジェクトストレージ操作、外部ファイルシステムのマウント・転送。
- **検索パターン例**:
  - オブジェクトストレージ: `S3Client` + `PutObject|GetObject`, `@google-cloud/storage`,
    `@azure/storage-blob`, `minio`, `boto3` の `s3`
  - 署名付き URL: `getSignedUrl`, `generate_presigned_url`, `presign`
  - 外部 FS / 転送: `ssh2-sftp`, `paramiko`, `ftp`, NFS / SMB のマウント設定（IaC 側）
- **接続先の読み取り**: バケット名・コンテナ名（環境変数名または定数）、エンドポイント上書き
  （MinIO / 互換ストレージの `endpoint` 設定）。
- **認証方式**: IAM ロール / アクセスキー / SAS トークン / SSH 鍵。
- **注意点**: 署名付き URL の発行は「サーバーは発行のみ・実転送はクライアント直」なので、
  利用場面欄にその旨を書く（帯域・障害の影響先が変わる）。

## 7. network-io — その他ネットワーク I/O

- **シグナル**: 上記に該当しない外部通信。
- **検索パターン例**:
  - gRPC: `grpc`, `@grpc/grpc-js`, `.proto` ファイル + クライアント stub の初期化
  - WebSocket: `ws`, `socket.io-client`, `websockets`（Python）— **クライアント側**の接続
  - SMTP 直接続: `nodemailer`（SMTP transport）, `smtplib`, `net/smtp`
  - DNS / 低レベル: `dns.resolve`, `net.Dial`, `socket.connect` で外部ホスト指定
  - 監視・計測の送信: `sentry`, `datadog`, `newrelic`, `prometheus` の remote write,
    OpenTelemetry exporter（`OTEL_EXPORTER_*`）
- **接続先の読み取り**: 接続先ホストの環境変数名・定数。gRPC は `.proto` の
  サービス名も添えると調査に効く。
- **注意点**: 監視 SDK は起動時に自動で外部送信するものが多く、呼び出し箇所が
  初期化 1 行しかない。それでも台帳に載せる（障害時の「知らない外部通信」の典型のため）。
  WebSocket のサーバー側 listen は外部アクセスではない（受信エンドポイントとして
  エントリポイント一覧に回す）。

## エントリポイントの検出パターン（利用場面マップ用）

呼び出し経路の起点を列挙するためのパターン。

- **HTTP ルート**: `app.get|post|put|delete`（Express / Fastify）, `@Get|@Post`（NestJS）,
  `@app.route|@router.get`（Flask / FastAPI）, `urls.py`（Django）, `routes.rb`（Rails）,
  `http.HandleFunc` / ルーターの `GET(`（Go）, `@GetMapping`（Spring）
- **ジョブ・スケジューラ**: `cron`, `node-cron`, `@Scheduled`, `celery.task` / `@shared_task`,
  `sidekiq` の `perform`, `Rakefile`, IaC 側の EventBridge / Cloud Scheduler 定義
- **CLI**: `commander`, `yargs`, `click`, `argparse`, `cobra`, `bin/` 配下のエントリ,
  `package.json` の `scripts`（外部アクセスを含むものだけ）
- **イベント・メッセージハンドラ**: カテゴリ 5 の consumer 定義, Lambda / Cloud Functions の
  ハンドラ（`handler` エクスポート + IaC のトリガー定義）, Webhook 受信ルート

経路追跡の限界（レポートの免責に使う）: DI コンテナによる解決、文字列ベースの
動的ディスパッチ、リフレクション、実行時に読み込まれるプラグインは静的には追いきれない。
該当箇所は「経路不明・要確認」とし、確認方法（実行時ログの仕込み先、grep の起点）を添える。

## パターンの育て方

実際のスキャンで「このライブラリ・書き方を見落とした」が見つかったら、
該当カテゴリの検索パターン例に追記する。SKILL.md 本体は変更しない。
