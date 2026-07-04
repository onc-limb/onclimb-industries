# エンジニアリング向けスキル候補一覧（バックログ）

エンジニアとしての開発・運用作業で「自動化できたら効率が上がる」場面のスキル候補を並べた一覧。
[`skill-candidates.md`](skill-candidates.md)（ビジネス・事務寄り）のエンジニアリング版で、運用ルールは同じ。

- ここは軽量なバックログ。正式に検討を始めるものは [`TEMPLATE.md`](TEMPLATE.md) を複製して 1 アイデア 1 ファイルに展開する（[運用ルール](README.md)参照）。
- 分類プレフィックスは [`../.claude/skills/README.md`](../.claude/skills/README.md) に準拠。技術系はほぼ `arc-reactor`（コーディング・レビュー）か `edith`（調査・分析）に落ちる。
- **実行モード**の凡例:
  - `壁打ち` … 対話しながら一緒に作る（設計・選定など判断が絡むもの）
  - `半自動` … 一回指示すれば最後まで走るが、確定前に確認を挟む
  - `完全自動` … 一度仕込んだら定期実行 or トリガー実行で勝手に動き、レポート/PR を残す

## 1. インフラ・クラウド系

| # | 候補名（仮） | 分類 | モード | 解決したい場面・課題 | 想定 入力 → 出力 |
|---|---|---|---|---|---|
| 1 | infra-architecture-designer | arc-reactor | 壁打ち | インフラ構成をゼロから考えるとき、観点漏れ（可用性・コスト・セキュリティ）が出る | 要件（トラフィック・予算・制約）→ 構成図（Mermaid/draw.io XML）＋設計判断の根拠＋セキュリティ懸念リスト |
| 2 | diagram-to-terraform | arc-reactor | 半自動 | 構成図から IaC に落とす作業が単純作業のわりに重い | 構成図（#1 の出力 or 既存図）→ Terraform コード一式＋`terraform validate`/`plan` 通過確認 |
| 3 | cloud-cost-auditor | edith | 完全自動 | 使っていないリソース・過剰スペックに気づかず課金が続く | AWS/GCP の請求・リソースデータ → 無駄リソース一覧＋削減額見積レポート（定期実行） |
| 4 | iac-drift-detector | arc-reactor | 完全自動 | コンソールでの手動変更が IaC と乖離していく | Terraform state × 実環境 → ドリフト検出レポート＋取り込み用コード差分案 |
| 5 | cloud-security-posture-scanner | arc-reactor | 完全自動 | IAM の過剰権限・公開 S3・緩い SG に気づかない | クラウドアカウント設定 → リスク別（Critical〜Info）指摘一覧＋修正 Terraform 差分案 |
| 6 | cloud-resource-inventory | ultron | 完全自動 | 複数アカウント/プロジェクトのリソース全容が誰にも分からない | アカウント一覧 → リソース棚卸し表（タグ・作成者・最終利用日）＋孤児リソース候補 |
| 7 | dr-backup-verifier | arc-reactor | 半自動 | バックアップは取っているが「戻せるか」を誰も検証していない | バックアップ設定 → 復元手順の実地検証結果＋RTO/RPO の実測レポート |

## 2. 運用・監視系（任せたら勝手に動く系）

| # | 候補名（仮） | 分類 | モード | 解決したい場面・課題 | 想定 入力 → 出力 |
|---|---|---|---|---|---|
| 8 | log-anomaly-reporter | arc-reactor | 完全自動 | CloudWatch/Sentry/Datadog のエラー・警告を毎日見に行くのが続かない | 監視ツールのログ・イベント → 異常の要約＋原因仮説＋解決案つき日次/週次レポート |
| 9 | incident-postmortem-writer | friday | 半自動 | 障害後、対応に追われてポストモーテムが書かれない | 障害時のログ・Slack・作業記録 → タイムライン＋根本原因＋再発防止策のポストモーテム草案 |
| 10 | ci-failure-triager | arc-reactor | 完全自動 | CI が落ちたとき、flaky なのか本物なのかの切り分けに時間を取られる | CI 失敗ログ → flaky/実バグ/環境起因の判定＋再実行 or 修正 PR |
| 11 | alert-rule-tuner | arc-reactor | 半自動 | アラートが鳴りすぎて重要な通知が埋もれる（アラート疲れ） | アラート発報履歴 → ノイズ源ランキング＋閾値・条件の調整案 |
| 12 | uptime-sla-reporter | friday | 完全自動 | 稼働率・SLA 実績の報告資料を毎月手で作っている | 監視データ → 月次 SLA レポート（稼働率・障害一覧・傾向） |
| 13 | dependency-update-pilot | arc-reactor | 完全自動 | 依存ライブラリの更新が放置され、まとめて上げると壊れる | リポジトリ → 定期的に少量ずつ依存更新＋テスト実行＋変更点要約つき PR（セキュリティ修正は既存 `fix-dependabot` の領分） |
| 14 | nightly-repo-gardener | arc-reactor | 完全自動 | lint 警告・型エラー・小さな TODO が溜まり続ける | リポジトリ → 夜間に小粒の修正 PR を自動作成（1 PR 1 テーマ、テスト通過必須） |

## 3. 開発環境・ローカル作業系

| # | 候補名（仮） | 分類 | モード | 解決したい場面・課題 | 想定 入力 → 出力 |
|---|---|---|---|---|---|
| 15 | env-doctor | arc-reactor | 半自動 | 環境構築・ローカル実行のエラー解決に毎回時間が溶ける | エラーメッセージ＋環境情報 → 原因調査＋自動修復＋**手順書（README 等）の修正 PR** まで |
| 16 | setup-doc-verifier | arc-reactor | 完全自動 | README の環境構築手順が古く、新規参画者が毎回ハマる | README/セットアップ手順 → クリーンな環境で実際に実行して検証＋古くなった箇所の修正案 |
| 17 | docker-image-slimmer | arc-reactor | 半自動 | イメージが肥大化してビルド・デプロイが遅い | Dockerfile → レイヤ・キャッシュ・ベースイメージ最適化案＋サイズ/ビルド時間の before/after |
| 18 | dev-tooling-auditor | edith | 半自動 | エディタ設定・linter・formatter・pre-commit がプロジェクト間でバラバラ | 手元の複数リポジトリ → ツール設定の棚卸し表＋標準化提案 |
| 19 | makefile-task-consolidator | arc-reactor | 半自動 | よく打つコマンド列が頭の中にしかなく、毎回タイプしている | シェル履歴・CI 設定 → 頻出操作の Makefile/justfile タスク化提案 |

## 4. コード品質・テスト系

| # | 候補名（仮） | 分類 | モード | 解決したい場面・課題 | 想定 入力 → 出力 |
|---|---|---|---|---|---|
| 20 | release-readiness-checker | arc-reactor | 半自動 | 「リリースまであと何が要るか」が感覚頼みで漏れる | リポジトリ＋リリース要件 → 不足項目チェックリスト（監視・ログ・エラー処理・ドキュメント・法務系表記等）＋優先度 |
| 21 | quality-scorecard | arc-reactor | 半自動 | 「品質」が曖昧で、良し悪しを説明できない | リポジトリ → テストカバレッジ・複雑度・依存健全性・ドキュメント率などの多面スコアカード＋改善の費用対効果順リスト |
| 22 | flaky-test-hunter | arc-reactor | 完全自動 | たまに落ちるテストが放置され CI の信頼が下がる | テストスイート → 反復実行による flaky 特定＋原因分類（時刻依存・並列競合等）＋修正案 |
| 23 | performance-regression-profiler | arc-reactor | 完全自動 | 性能劣化がリリース後にユーザー経由で発覚する | ベンチマーク/プロファイル → コミット間の性能比較＋劣化コミットの特定レポート |
| 24 | n-plus-one-detector | arc-reactor | 半自動 | ORM の N+1 が本番の負荷で初めて見つかる | コード＋クエリログ → N+1・重いクエリの検出＋eager load 等の修正案 |
| 25 | error-handling-auditor | arc-reactor | 半自動 | 握りつぶし・雑な catch・不親切なエラーメッセージが散在する | リポジトリ → エラー処理の問題箇所一覧（握りつぶし/情報欠落/ユーザー向け文言）＋修正案 |
| 26 | accessibility-auditor | arc-reactor | 半自動 | Web の a11y 対応が後回しになり、どこが駄目かも分からない | 稼働中の Web アプリ（ブラウザ自動操作）→ WCAG 観点の指摘一覧＋修正コード案 |
| 27 | i18n-consistency-checker | arc-reactor | 完全自動 | 翻訳キーの欠落・未使用・言語間の不整合が溜まる | リポジトリ → 欠落/未使用/プレースホルダ不整合の一覧＋修正 PR |
| 28 | test-gap-analyzer | arc-reactor | 半自動 | カバレッジ数値はあるが「重要なのにテストが無い場所」が分からない | カバレッジ×変更頻度×複雑度 → リスク加重のテスト欠落ランキング（雛形生成は既存 `arc-reactor-test-scaffolder` に接続） |

## 5. 設計・ドキュメント系

| # | 候補名（仮） | 分類 | モード | 解決したい場面・課題 | 想定 入力 → 出力 |
|---|---|---|---|---|---|
| 29 | db-schema-designer | arc-reactor | 壁打ち | テーブル設計の正規化・インデックス・将来の拡張を一人で悩む | 要件 → ER 図＋DDL/マイグレーション＋設計判断の根拠（トレードオフ明記） |
| 30 | api-designer | arc-reactor | 壁打ち | API 設計の一貫性（命名・エラー形式・ページネーション）が保てない | 要件＋既存 API → OpenAPI/GraphQL スキーマ案＋既存規約との整合チェック |
| 31 | api-contract-guardian | arc-reactor | 完全自動 | OpenAPI 定義と実装がいつの間にか乖離する | スキーマ×実装/実トラフィック → 乖離一覧＋どちらを直すかの判断材料 |
| 32 | sequence-diagram-generator | arc-reactor | 半自動 | 「この処理どう流れてる？」を毎回コードを追って説明している | エントリポイント指定 → コード追跡によるシーケンス図/フロー図（Mermaid） |
| 33 | migration-planner | arc-reactor | 壁打ち | 大規模リファクタ・移行（DB 移行、フレームワーク更新等）の段取りが立てられない | 現状＋ゴール → 段階的移行計画（各段階でロールバック可能な単位に分割）＋リスク表 |
| 34 | runbook-generator | friday | 半自動 | 障害時・定期作業の運用手順書が無く、対応が属人化する | コード・インフラ設定・過去の対応ログ → Runbook（症状→確認→対処の形式） |
| 35 | changelog-writer | friday | 完全自動 | リリースノート・CHANGELOG が書かれない/雑になる | コミット・PR 履歴 → 読者別（開発者向け/ユーザー向け）の CHANGELOG 草案 |
| 36 | adr-drift-checker | arc-reactor | 完全自動 | 過去の設計判断（ADR）と現状コードがずれても誰も気づかない | ADR × コード → 乖離検出レポート（ADR 更新 or コード修正の提案） |
| 53 | external-access-mapper | arc-reactor | 半自動 | DB・認証系 SaaS・外部 API・ストレージ・キューなど、外部にアクセスしている箇所と「いつ使われるか」が把握できない | リポジトリ → 外部アクセス台帳（種類・接続先・認証方式・該当コード file:line）＋各アクセスの利用場面マップ（どのユースケース/エンドポイントからどういう経路で呼ばれるか） |

## 6. Git・PR・レビュー系

| # | 候補名（仮） | 分類 | モード | 解決したい場面・課題 | 想定 入力 → 出力 |
|---|---|---|---|---|---|
| 37 | pr-splitter | arc-reactor | 半自動 | 差分が大きくなりすぎてレビューされない/できない | 大きな working diff → 意味単位に分割したブランチ/PR 列（依存順つき） |
| 38 | review-comment-responder | arc-reactor | 半自動 | レビュー指摘への対応と返信が溜まって PR が停滞する | PR のレビューコメント → 対応コミット＋返信ドラフト（対応しない場合の理由案含む） |
| 39 | stale-branch-reaper | arc-reactor | 完全自動 | マージ済み・放置ブランチが溜まりリポジトリが見通せない | リポジトリ → ブランチ棚卸し表（マージ済/放置/救出価値あり）＋削除候補リスト |
| 40 | conflict-resolver | arc-reactor | 半自動 | rebase/merge のコンフリクト解消が怖くて時間がかかる | コンフリクト状態 → 両ブランチの意図を調べた解消案＋根拠説明（機械的に潰さない） |
| 41 | dead-code-reaper | arc-reactor | 半自動 | 使われていないコード・フィーチャーフラグ・設定が消せずに残る | リポジトリ＋（あれば）本番の実行ログ → 削除候補＋安全性根拠つき削除 PR（検出のみは既存 `arc-reactor-tech-debt-auditor` と連携） |

## 7. セキュリティ系

| # | 候補名（仮） | 分類 | モード | 解決したい場面・課題 | 想定 入力 → 出力 |
|---|---|---|---|---|---|
| 42 | secret-leak-scanner | arc-reactor | 完全自動 | API キー等の混入に、コミット履歴の深部まで含めて気づけない | リポジトリ（履歴含む）→ 検出一覧＋ローテーション手順＋履歴からの除去手順 |
| 43 | threat-modeler | arc-reactor | 壁打ち | 新機能のセキュリティ検討が「なんとなく大丈夫そう」で終わる | 機能設計・構成図 → STRIDE 等に基づく脅威一覧＋対策の優先度 |
| 44 | vuln-reachability-triager | arc-reactor | 半自動 | 脆弱性アラートが大量に来て、本当に危ないものが分からない | SCA アラート → 実際に到達可能か（該当コードパスを使っているか）の判定つき優先度リスト（修正 PR は既存 `fix-dependabot` へ） |
| 45 | web-security-header-checker | arc-reactor | 完全自動 | CSP・Cookie 属性・CORS などの設定不備に気づかない | 稼働中の Web アプリ → ヘッダ/Cookie/CORS 監査レポート＋設定修正案 |
| 46 | license-compliance-checker | ultron | 完全自動 | 依存ライブラリのライセンス違反リスクを把握していない | 依存一覧 → ライセンス棚卸し表＋コピーレフト等の要注意依存＋対応案 |

## 8. データ・DB 系

| # | 候補名（仮） | 分類 | モード | 解決したい場面・課題 | 想定 入力 → 出力 |
|---|---|---|---|---|---|
| 47 | slow-query-optimizer | arc-reactor | 半自動 | スロークエリの解析と改善が後回しになる | スロークエリログ＋スキーマ → EXPLAIN 解析＋インデックス/書き換え案＋効果見積 |
| 48 | data-migration-verifier | arc-reactor | 半自動 | データ移行の「本当に全部正しく移ったか」の検証が手薄になる | 移行元×移行先 → 件数/サンプル/集計値の整合性検証スクリプト＋検証結果レポート |
| 49 | seed-data-generator | arc-reactor | 半自動 | 開発・デモ用の現実的なテストデータを作るのが面倒 | スキーマ＋制約 → 外部キー整合・現実的な分布のシードデータ生成スクリプト |
| 50 | db-migration-safety-checker | arc-reactor | 完全自動 | 本番でロック・ダウンタイムを引き起こすマイグレーションを事前に検知できない | マイグレーションファイル → 危険操作（テーブルロック・非互換変更）の検出＋安全な代替手順 |
| 54 | query-latency-profiler | arc-reactor | 半自動 | ORM・生 SQL のどのクエリが遅いかを、スロークエリログが無い環境では把握できない | リポジトリ（＋実行可能な DB 環境）→ コードからクエリ発行箇所（ORM 呼び出し・生 SQL）を抽出し、実際に発行される SQL を実測/EXPLAIN してレイテンシ一覧＋スロークエリランキング（改善案の深掘りは #47 に接続） |

## 9. デプロイ・E2E 系

| # | 候補名（仮） | 分類 | モード | 解決したい場面・課題 | 想定 入力 → 出力 |
|---|---|---|---|---|---|
| 51 | post-deploy-smoke-runner | arc-reactor | 完全自動 | デプロイ後の動作確認が手動で、忘れると事故になる | デプロイ完了トリガー → ブラウザ自動操作で主要導線のスモークテスト実行＋結果レポート（失敗時はロールバック提案） |
| 52 | issue-to-pr-pilot | arc-reactor | 完全自動 | 小粒の Issue が「やれば終わるのに」溜まっていく | GitHub Issue（`jarvis-issue-planner` の出力想定）→ 実装＋テスト＋PR 作成まで完全自動、判断に迷った点は PR 本文に明記 |

## 優先順位（2026-07-03 採点）

3 観点を各 5 点満点で採点し、合計点で優先順位を付けた（同点内の順序はユーザー明示要望 > 特異性 > 実現可能性で決定）。

- **実現可能性（F）**: 精度として実務に耐えうるか。LLM の得意領域（コード読解・チェックリスト駆動・対話設計）は高く、外部環境の足回り（監視 SaaS 連携・クリーン環境・ベンチ基盤）に依存するものは低い。
- **ビジネス有用性（B）**: 仕事の効率・収益に直結するか。使用頻度 × 1 回あたりの時間削減で判断。
- **特異性（U）**: 既製ツールやクラウド標準機能で代替できず、スキル化する意味があるか。

| 優先 | # | 候補名 | F | B | U | 計 | 判断の要点 |
|---|---|---|---|---|---|---|---|
| 1 | 53 | external-access-mapper | 4 | 5 | 5 | 14 | SES 参画・影響調査で頻用。既製ツール無し。静的なコード追跡は精度が出る |
| 2 | 15 | env-doctor | 4 | 5 | 4 | 13 | 環境エラーの時間損失は大きく高頻度。手順書修正まで戻す設計が独自 |
| 3 | 20 | release-readiness-checker | 4 | 4 | 5 | 13 | チェックリスト駆動で精度が出る。この観点を横断する既製ツールが無い |
| 4 | 54 | query-latency-profiler | 3 | 5 | 4 | 12 | 明示要望。DB 実行環境への依存はあるが効果が直接的（#47 を吸収して実装） |
| 5 | 1 | infra-architecture-designer | 4 | 4 | 4 | 12 | 設計壁打ちは LLM の得意領域。セキュリティ観点の型化に価値 |
| 6 | 37 | pr-splitter | 3 | 4 | 5 | 12 | git 操作の正確性が課題だが既製手段が皆無。レビュー効率に直結 |
| 7 | 50 | db-migration-safety-checker | 4 | 4 | 4 | 12 | 静的検出で精度が出しやすく、事故 1 回防げば元が取れる（squawk は PG 限定） |
| 8 | 32 | sequence-diagram-generator | 4 | 4 | 4 | 12 | コード追跡は Claude 向き。説明・引き継ぎ・調査で頻用 |
| 9 | 29 | db-schema-designer | 4 | 4 | 4 | 12 | 設計判断の根拠を残す壁打ちの型化。頻度も高い |
| 10 | 30 | api-designer | 4 | 4 | 4 | 12 | 既存 API 規約との整合チェックが独自価値 |
| 11 | 38 | review-comment-responder | 4 | 4 | 4 | 12 | 有用だが人のレビュー文脈の解釈を誤るリスクがやや高い |
| 12 | 47 | slow-query-optimizer | 4 | 4 | 4 | 12 | 単独では作らず #54 のスキルに統合（ログ有り時の入力モードとして実装） |
| 13 | 21 | quality-scorecard | 3 | 4 | 4 | 11 | 言語ごとの計測ツール整備が重く、初版の精度担保が難しい |
| 14 | 24 | n-plus-one-detector | 3 | 4 | 4 | 11 | 実クエリログが無いと確度が落ちる。#54 の派生として後日検討 |
| 15 | 40 | conflict-resolver | 3 | 4 | 4 | 11 | 双方の意図理解を誤ると危険。確認フロー設計が肝 |
| 16 | 2 | diagram-to-terraform | 3 | 4 | 4 | 11 | plan 検証環境まで揃えないと精度が出ない。#1 の後続として実装 |
| 17 | 25 | error-handling-auditor | 4 | 3 | 4 | 11 | 精度は出るが緊急性が低め |
| 18 | 33 | migration-planner | 4 | 3 | 4 | 11 | 価値は高いが使用頻度が低い |
| 19 | 34 | runbook-generator | 4 | 3 | 4 | 11 | 運用フェーズの案件でのみ効く |
| 20 | 43 | threat-modeler | 4 | 3 | 4 | 11 | 型化の価値ありだが頻度低め。#1 に一部観点を内蔵済み |
| 21 | 9 | incident-postmortem-writer | 4 | 3 | 4 | 11 | 障害発生時のみ使用。頻度が読めない |
| 22 | 8 | log-anomaly-reporter | 3 | 4 | 3 | 10 | 明示要望だが監視 SaaS の API・認証・定期実行の足回りに依存。接続整備後に再評価 |
| 23 | 10 | ci-failure-triager | 3 | 4 | 3 | 10 | CI 連携の足回り依存。オンデマンド版なら早期に作れる |
| 24 | 16 | setup-doc-verifier | 3 | 3 | 4 | 10 | クリーン環境（Docker 等）の用意が重い。env-doctor の実績を見て判断 |
| 25 | 28 | test-gap-analyzer | 3 | 3 | 4 | 10 | カバレッジ計測の言語依存が重い |
| 26 | 31 | api-contract-guardian | 3 | 3 | 4 | 10 | スキーマ運用がある案件でのみ効く |
| 27 | 44 | vuln-reachability-triager | 3 | 3 | 4 | 10 | 到達可能性判定の精度検証が難しい |
| 28 | 48 | data-migration-verifier | 3 | 3 | 4 | 10 | 移行案件のときだけ。単発需要 |
| 29 | 17 | docker-image-slimmer | 4 | 3 | 3 | 10 | dive 等の既存ツールあり。修正案生成に差分価値 |
| 30 | 35 | changelog-writer | 4 | 3 | 3 | 10 | release-drafter 等で一部代替可 |
| 31 | 49 | seed-data-generator | 4 | 3 | 3 | 10 | faker 系で一部代替可。整合性重視の生成に差分価値 |
| 32 | 14 | nightly-repo-gardener | 3 | 3 | 3 | 9 | 定期実行と権限設計が先。自動系の型ができてから |
| 33 | 22 | flaky-test-hunter | 3 | 3 | 3 | 9 | 反復実行のコストが高い |
| 34 | 41 | dead-code-reaper | 3 | 3 | 3 | 9 | 検出は tech-debt-auditor が既にカバー。削除 PR 部分のみ差分 |
| 35 | 51 | post-deploy-smoke-runner | 3 | 3 | 3 | 9 | デプロイフックの足回り依存 |
| 36 | 52 | issue-to-pr-pilot | 3 | 4 | 2 | 9 | Claude Code 本体・cloud agent でかなり代替可能 |
| 37 | 11 | alert-rule-tuner | 3 | 3 | 3 | 9 | 監視 SaaS 連携が前提。#8 と同じ足回り待ち |
| 38 | 7 | dr-backup-verifier | 2 | 3 | 4 | 9 | 実復元の検証は環境依存とリスクが大きい |
| 39 | 42 | secret-leak-scanner | 4 | 3 | 2 | 9 | gitleaks 等で代替可。後処理（ローテ手順）のみ差分価値 |
| 40 | 36 | adr-drift-checker | 3 | 2 | 4 | 9 | ADR 運用がある案件が少ない |
| 41 | 18 | dev-tooling-auditor | 4 | 2 | 3 | 9 | 効くのは年数回 |
| 42 | 19 | makefile-task-consolidator | 4 | 2 | 3 | 9 | 効果が小粒 |
| 43 | 27 | i18n-consistency-checker | 4 | 2 | 3 | 9 | i18n lint 既存あり。多言語案件のときだけ |
| 44 | 39 | stale-branch-reaper | 4 | 2 | 3 | 9 | 効果が小粒。単発のシェル作業でも足りる |
| 45 | 3 | cloud-cost-auditor | 3 | 3 | 2 | 8 | Cost Explorer / Trusted Advisor と重複が大きい |
| 46 | 5 | cloud-security-posture-scanner | 3 | 3 | 2 | 8 | Security Hub / Prowler 等と重複が大きい |
| 47 | 4 | iac-drift-detector | 3 | 3 | 2 | 8 | terraform plan / driftctl と重複 |
| 48 | 23 | performance-regression-profiler | 2 | 3 | 3 | 8 | ベンチマーク基盤が前提で足回りが最重量級 |
| 49 | 26 | accessibility-auditor | 3 | 2 | 3 | 8 | axe 等既存あり。現案件での需要も低め |
| 50 | 45 | web-security-header-checker | 4 | 2 | 2 | 8 | Mozilla Observatory 等で代替可 |
| 51 | 46 | license-compliance-checker | 4 | 2 | 2 | 8 | 既存ツールが豊富 |
| 52 | 6 | cloud-resource-inventory | 3 | 2 | 2 | 7 | クラウド標準のリソースエクスプローラで大半代替可 |
| 53 | 12 | uptime-sla-reporter | 3 | 2 | 2 | 7 | 監視 SaaS のレポート機能と重複 |
| 54 | 13 | dependency-update-pilot | 3 | 3 | 1 | 7 | Renovate / Dependabot でほぼ代替可 |

**実装対象（優先 1〜10）**: #53, #15, #20, #54(+#47), #1, #37, #50, #32, #29, #30。
優先 11 の #38 は次点、優先 12 の #47 は #54 のスキルに統合するため単独実装しない。

**2026-07-03 実装済み**（詳細は各アイデアファイル参照）:

| # | スキル | アイデアファイル |
|---|---|---|
| 53 | `arc-reactor-external-access-mapper` | [external-access-mapper.md](external-access-mapper.md) |
| 15 | `arc-reactor-env-doctor` | [env-doctor.md](env-doctor.md) |
| 20 | `arc-reactor-release-readiness-checker` | [release-readiness-checker.md](release-readiness-checker.md) |
| 54+47 | `arc-reactor-slow-query-hunter` | [slow-query-hunter.md](slow-query-hunter.md) |
| 1 | `arc-reactor-infra-architecture-designer` | [infra-architecture-designer.md](infra-architecture-designer.md) |
| 37 | `arc-reactor-pr-splitter` | [pr-splitter.md](pr-splitter.md) |
| 50 | `arc-reactor-db-migration-safety-checker` | [db-migration-safety-checker.md](db-migration-safety-checker.md) |
| 32 | `arc-reactor-sequence-diagram-generator` | [sequence-diagram-generator.md](sequence-diagram-generator.md) |
| 29 | `arc-reactor-db-schema-designer` | [db-schema-designer.md](db-schema-designer.md) |
| 30 | `arc-reactor-api-designer` | [api-designer.md](api-designer.md) |

## 既存スキルでカバー済みの領域（重複防止メモ)

| 場面 | 既存スキル |
|---|---|
| 技術選定の比較調査（類似技術の一覧化・メリデメ） | `edith-tech-selection-research` |
| 観点別コードレビュー | `arc-reactor-code-review` |
| テスト雛形生成 | `arc-reactor-test-scaffolder` |
| 技術負債の棚卸し | `arc-reactor-tech-debt-auditor` |
| 初見コードベースの把握 | `arc-reactor-codebase-onboarding` |
| 設計書/README/ADR の草案生成 | `friday-design-doc-generator` |
| Dependabot アラートの修正 PR | `fix-dependabot`（グローバルスキル） |

## 使い方メモ

- 温めたい候補はこの表から選び、`TEMPLATE.md` を複製して 1 ファイルに展開する（[運用ルール](README.md)参照）。
- 展開したらメモ欄相当としてこの表の行に詳細ファイルへのリンクを付ける。見送りは行を残して理由を一言添える。
- `完全自動` 系は共通して「実行権限の範囲」「失敗時に人へ引き継ぐ条件」「レポートの置き場所」の設計が肝になる。
  最初の 1 本（#8 log-anomaly-reporter か #15 env-doctor が有力）でこの型を作ると、以降の自動系に流用できる。
