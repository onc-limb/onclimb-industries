# security-review-checklist — 構成図セルフレビューの観点

infra-architecture-designer のフロー 4 で使うチェックリスト。
構成図とコンポーネント表を入力に、以下の 8 観点を**上から順に全部**見る。
指摘には重大度（High / Mid / Low）と対策案を付け、指摘が出なかった観点も
「確認済み」として列挙する（確認漏れと確認済みの区別のため）。

観点の改善（新しい確認項目・典型リソースの追加）はこのファイルへの追記で行う。

---

## 1. ネットワーク境界と公開面 (network boundary / exposure)

**確認する問い**

- インターネットに直接露出しているコンポーネントはどれか。露出が必要なものだけか。
- DB・キャッシュ・内部 API が public サブネット / パブリック IP に置かれていないか。
- 境界の入口に WAF / DDoS 対策があるか（一般公開 Web の場合）。
- 管理アクセス（SSH / DB 接続）の経路は限定されているか（踏み台 / セッション経由か、0.0.0.0/0 開放になっていないか）。

**AWS の典型**: public/private サブネットの分離、Security Group のソース制限、
ALB / CloudFront + AWS WAF、RDS の `PubliclyAccessible=false`、
SSM Session Manager（SSH ポート開放の代替）、VPC エンドポイント（S3 / DynamoDB への private 経路）。

**Google Cloud の典型**: VPC ファイアウォールルールのソース制限、Cloud Load Balancing + Cloud Armor、
Cloud SQL のプライベート IP（パブリック IP 無効）、IAP（Identity-Aware Proxy、SSH/管理画面の保護）、
Private Google Access、Cloud Run / Cloud Functions の ingress 設定（`internal-and-cloud-load-balancing` 等）。

**典型的な指摘例**: 「RDS が public サブネットに配置されている（High）→ private サブネットへ移動し、
Security Group のソースをアプリ層に限定」

## 2. IAM 最小権限 (least privilege)

**確認する問い**

- アプリ・バッチが使う実行ロールは、必要なサービス・リソースに絞られているか
  （`*` 権限・管理者権限を流用していないか）。
- 人間のアクセスとワークロードのアクセスが分離されているか。長期キー（アクセスキー直置き）を前提にしていないか。
- クロスアカウント / 外部サービス連携の権限に条件（外部 ID・リポジトリ限定等）が付いているか。

**AWS の典型**: IAM ロール + インスタンスプロファイル / IRSA（EKS）/ ECS タスクロール、
リソースレベルの絞り込み（S3 バケット ARN 単位等）、AssumeRole の外部 ID、
IAM アクセスキーの発行を避けて一時クレデンシャルを使う、S3 バケットポリシーの Public Access Block。

**Google Cloud の典型**: サービスアカウントをワークロード単位で分ける（デフォルト SA の
`Editor` ロール流用をやめる）、事前定義ロール / カスタムロールでの絞り込み、
Workload Identity（GKE）/ Workload Identity 連携（GitHub Actions 等の外部からのキーレス認証）、
サービスアカウントキー(JSON)のダウンロード禁止。

**典型的な指摘例**: 「Cloud Run のサービスアカウントがプロジェクトの Editor（High）→
必要な API（Firestore・Pub/Sub）に限定したロールへ差し替え」

## 3. 暗号化 — 転送時・保存時 (encryption in transit / at rest)

**確認する問い**

- 外部との通信（クライアント ↔ LB、外部 API）は TLS か。証明書の管理主体は決まっているか。
- 内部通信（アプリ ↔ DB 等）の TLS 要否を判断したか（コンプライアンス要件がある場合は必須）。
- データストア（DB・オブジェクトストレージ・ディスク・バックアップ）の保存時暗号化は有効か。
  鍵をマネージド任せにするか顧客管理鍵（CMK）にするかを要件と突き合わせたか。

**AWS の典型**: ACM 証明書 + ALB/CloudFront の TLS 終端、RDS / EBS / S3 の暗号化（既定 or KMS CMK）、
RDS の `rds.force_ssl`、S3 バケットの TLS 強制ポリシー（`aws:SecureTransport`）。

**Google Cloud の典型**: Google マネージド SSL 証明書 + Cloud Load Balancing、
保存時暗号化は既定で有効（要件次第で CMEK: Cloud KMS 鍵）、Cloud SQL の SSL 接続強制 /
Cloud SQL Auth Proxy、GCS バケットの CMEK 指定。

**典型的な指摘例**: 「コンプライアンス制約（個人情報）があるのに DB 暗号化がマネージド既定のみ（Mid）→
KMS CMK / CMEK の採用を検討し、鍵のローテーション方針を設計記録に残す」

## 4. シークレット管理 (secrets management)

**確認する問い**

- DB パスワード・API キー・トークンの置き場所は決まっているか
  （環境変数直書き・コードリポジトリ・平文の設定ファイルになっていないか）。
- シークレットのローテーション経路はあるか（少なくとも「手動で差し替え可能」な設計か）。
- CI/CD からシークレットへどうアクセスするかが決まっているか。

**AWS の典型**: Secrets Manager（RDS 認証情報の自動ローテーション対応）、
SSM Parameter Store（SecureString）、ECS / Lambda へのシークレット注入
（タスク定義の `secrets` / Lambda 環境変数 + KMS）。

**Google Cloud の典型**: Secret Manager + バージョニング、Cloud Run / Cloud Functions への
シークレット参照マウント（環境変数 or ボリューム）、GKE の Secret Manager アドオン
（K8s Secret 平文運用の回避）。

**典型的な指摘例**: 「DB パスワードをコンテナの環境変数に直書きする前提（High）→
Secrets Manager / Secret Manager に置き、実行ロール経由で参照」

## 5. ログ・監査証跡 (logging / audit trail)

**確認する問い**

- アプリケーションログの集約先は決まっているか（コンテナ・VM のローカルに残すだけになっていないか）。
- クラウド操作の監査ログ（誰が・いつ・何を変更したか）は有効か。
- アクセスログ（LB・オブジェクトストレージ）を取るか判断したか。保持期間は要件と合っているか。
- インシデント時に「気づける」導線（アラート通知先）があるか。

**AWS の典型**: CloudWatch Logs（+ 保持期間設定）、CloudTrail（全リージョン・改ざん防止の S3 保管）、
ALB / CloudFront / S3 のアクセスログ、CloudWatch Alarm + SNS、GuardDuty（脅威検知）。

**Google Cloud の典型**: Cloud Logging（+ ログバケットの保持期間）、Cloud Audit Logs
（管理アクティビティは既定で有効、データアクセスログは明示的に有効化）、
Cloud Load Balancing のログ、Cloud Monitoring のアラートポリシー + 通知チャネル、
Security Command Center。

**典型的な指摘例**: 「監査ログの言及がない（Mid）→ CloudTrail / Cloud Audit Logs を有効化し、
保管先と保持期間をコンポーネント表に追加」

## 6. 単一障害点 (single point of failure)

**確認する問い**

- 可用性要件に対して、単一 AZ / 単一インスタンス / 単一 NAT のコンポーネントが残っていないか。
- DB・キャッシュはフェイルオーバー手段があるか（要件が許すなら単一でもよいが、その判断を記録したか）。
- 「冗長化しない」と決めたコンポーネントは、復旧手順（再作成時間）とセットで許容されているか。

**AWS の典型**: マルチ AZ 配置（ALB + 複数 AZ のサブネット、RDS Multi-AZ、
ECS サービスの複数タスク分散）、NAT Gateway の AZ ごと配置、ElastiCache のレプリカ +
自動フェイルオーバー、Auto Scaling Group。

**Google Cloud の典型**: リージョナル MIG（マネージドインスタンスグループ）、
Cloud SQL の高可用性構成（リージョナルインスタンス）、GKE のリージョナルクラスタ、
Cloud Run / Cloud Functions（ゾーン障害はプラットフォーム側で吸収）、
Memorystore のスタンダードティア（レプリカ付き）。

**典型的な指摘例**: 「可用性要件『営業時間内は停止不可』に対し Cloud SQL が非 HA 構成（High）→
リージョナルインスタンス化、またはダウンタイム許容の合意を設計記録に残す」

## 7. バックアップ・DR (backup / disaster recovery)

**確認する問い**

- データストアごとにバックアップの取得方法・頻度・保持期間が決まっているか。
- リストア手順は現実的か（RPO / RTO を要件と突き合わせたか。厳密な数値がなくても「どこまで失ってよいか」の合意はあるか）。
- バックアップは障害ドメインの外にあるか（同一インスタンス内のみになっていないか）。
- 誤削除・ランサムウェア対策（世代管理・削除保護）を考えたか。

**AWS の典型**: RDS 自動バックアップ + スナップショット（必要ならクロスリージョンコピー）、
S3 バージョニング + ライフサイクル、AWS Backup（横断的なバックアップ計画）、
DynamoDB の PITR、EBS スナップショット。

**Google Cloud の典型**: Cloud SQL 自動バックアップ + PITR、GCS のバージョニング +
ライフサイクル / デュアルリージョンバケット、Firestore の PITR / スケジュールエクスポート、
永続ディスクのスナップショットスケジュール。

**典型的な指摘例**: 「バックアップの言及が構成図にない（Mid）→ Cloud SQL 自動バックアップの
保持期間と、リストア試験を運用タスクとして設計記録に追記」

## 8. コスト暴走リスク (cost runaway)

**確認する問い**

- 従量課金で青天井になりうるコンポーネントはどれか（サーバレスの無限スケール、
  外向きデータ転送、ログの無制限保持）。
- 予算アラートは設定する前提になっているか（金額と通知先）。
- スケール上限（同時実行数・インスタンス数上限）を明示したか。
- NAT 経由の大量転送・クロスリージョン転送など、転送料が支配的になる経路はないか。

**AWS の典型**: AWS Budgets + アラート、Cost Anomaly Detection、Lambda の同時実行数上限 /
予約同時実行、Auto Scaling の max 設定、CloudWatch Logs の保持期間設定（無期限放置の回避）、
NAT Gateway の処理量課金（VPC エンドポイントで削減）、S3 ライフサイクルによる低頻度階層化。

**Google Cloud の典型**: 予算アラート（Cloud Billing budgets）、Cloud Run の
`max-instances`、Cloud Functions の最大インスタンス数、BigQuery のカスタムクォータ /
maximum bytes billed（スキャン課金の上限）、Cloud Logging の除外フィルタと保持期間、
外向きネットワーク egress 料金の経路確認。

**典型的な指摘例**: 「Cloud Run に max-instances 未設定（Mid）→ 想定トラフィックから上限を決めて設定。
予算アラートを月額概算の 1.5 倍で設定」

---

## 出力フォーマット（フロー 4 で使う）

```markdown
### セキュリティセルフレビュー

#### 指摘
| # | 観点 | 該当コンポーネント | 重大度 | 内容 | 対策案 |
|---|---|---|---|---|---|

#### 確認した観点
- [x] 1. ネットワーク境界と公開面 — 指摘 n 件 / 問題なし
- [x] 2. IAM 最小権限 — ...
（8 観点すべてを列挙する。スキップした観点があれば「未確認」とその理由を書く）

#### 免責
このレビューは設計時の観点セルフチェックであり、専門のセキュリティ監査
（脆弱性診断・ペネトレーションテスト・第三者監査）の代替ではない。
```
