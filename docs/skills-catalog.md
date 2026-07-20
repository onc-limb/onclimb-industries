# スキル一覧

`.claude/skills/` 配下の全スキルの詳細一覧。各スキルの「どんな指示で起動するか」「何を入力に何ができるか」をまとめる。

## Claude Code / Codex での利用

スキルの正本は `.claude/skills/` である。Claude Code と Codex は同じ `SKILL.md` を
直接検出するため、内容の複製や実行時の変換は発生しない。

スキルを追加・変更するときは `.claude/skills/` のみを編集する。Codex が起動済みの場合は、
新規セッションを開始してスキル一覧を再読み込みする。

- 分類（プレフィックス）の意味と命名規約は [`.claude/skills/README.md`](../.claude/skills/README.md) を参照。
- 各分類の共通ルールは [`personas/`](../personas/) を参照。
- ほぼ全スキルが**明示的な依頼でのみ起動**する（自動起動しない）。例外は指示文の解釈で自然に立ち上がるもの（jarvis-worklog、jarvis-todo-management の突き合わせ等）。

## jarvis — 作業記録・一次資料系

読み手が AI もしくは自分自身。機械的なログ・一次記録・ナレッジ蓄積。

| スキル | 何をするか | 指示の例 | 成果物（出力先） |
|--------|-----------|----------|------------------|
| `jarvis-worklog` | Claude Code の会話・ツール操作ログを収集→分類→整理情報 2 形式（プロジェクト視点 / 技術者視点）に整理。生ログは zip 退避 | 「今日の作業をまとめて」「6/28 の作業を整理して」 | `worklog-data/` の digest（後段スキルの入力になる整理情報） |
| `jarvis-record` | worklog の project digest から、案件×対応日の作業記録を作成。対話の確認サイクルを必ず 1 回回す | 「今日の作業を案件ごとに記録して」 | `report-record/` の一次記録 Markdown（固定見出し） |
| `jarvis-knowledge-base` | worklog の tech digest を技術領域で横串に再編成し、Obsidian 形式の vault を生成・更新 | 「ナレッジベース作って」「vault 更新して」 | `knowledge-base/` のタグ・リンク付き Markdown ノート群 |
| `jarvis-todo-management` | プロジェクト別タスク台帳の運用。登録・分割、作業区切りでの突き合わせ、議事録等からの収穫、棚卸し、Google Tasks 同期 | 「ToDo 追加」「棚卸しして」「議事録から ToDo 拾って」 | `todo-data/todos.json` の更新（`todo.py` 経由） |
| `jarvis-todo-prioritizer` | 台帳のタスクに影響度×緊急度を根拠付きで評価・記録し、着手順の目安を提案 | 「ToDo の優先順位つけて」「どれからやるべき？」 | 台帳への priority 記録 + 着手順の提案 |
| `jarvis-issue-planner` | 既存コードを調査し、対話でゴール・スコープ・受け入れ条件を確定して開発 Issue を作成 | 「〜をやりたいので Issue 化して」「実装計画を立てて」 | Issue Markdown（希望すれば gh で GitHub Issue 登録） |
| `jarvis-reading-notes` | 読書の気づき・疑問と回答を 1 冊 = 1 ノートに時系列で記録。再開サポート・読了時まとめ | 「この本のここ気になるからメモして」「この本どこまで読んだっけ」 | `reading-notes/books/<slug>.md` |

## friday — 共有ドキュメント系

読み手が他者（上司・クライアント・チーム）。共有・発表前提に整えたドキュメント。

自由形式ドキュメント（設計書・提案書・技術記事・手順書）は `friday-doc-planner`（Stage 0）→ 生成スキル（Stage 1）の 2 段構成。固定パイプライン型（`friday-giziroku` / `friday-daily-report`）は単体起動。

| スキル | 何をするか | 指示の例 | 成果物（出力先） |
|--------|-----------|----------|------------------|
| `friday-doc-planner` | ドキュメント作成の事前準備（Stage 0）。目的×読者を対話で確定し、型・構成・情報源まで固めた企画書を作る | 「どんなドキュメントにするか壁打ちして」 | `doc-briefs/<日付>-<slug>.md`（doc brief） |
| `friday-design-doc-generator` | コードベースを調査し、出典パス付きの事実だけで設計書 / README / ADR の草案を生成。不明点は TBD 明示 | 「このプロジェクトの README 作って」「この技術選定を ADR にして」 | 対象プロジェクト配下の Markdown |
| `friday-procedure-doc-generator` | CI/CD 設定・スクリプト等から採取した実在コマンドだけで、運用手順書（deploy / rollback 等）と開発環境構築ガイドを生成。各ステップは「操作→期待結果」ペア、ロールバック手順の有無を必ず検査 | 「デプロイ手順書を作って」「開発環境構築の README を書いて」 | 対象プロジェクト配下の `docs/runbooks/<作業名>.md` / `docs/setup.md` |
| `friday-proposal-generator` | 要件からタスク分解×工数×単価の内訳表付き提案書・見積ドラフトを生成。金額はユーザー承認必須 | 「この要件で提案書を作って」「見積もり出したいからドラフト作って」 | 提案書ドラフト Markdown（固定構成） |
| `friday-tech-article-drafter` | tech digest / vault をネタに、機密マスキング・清書パス・公開前チェック付きの技術記事ドラフトを生成 | 「ブログ記事のドラフト書いて」「Terraform のノートを Zenn 記事にして」 | `articles/` の記事ドラフト Markdown |
| `friday-giziroku` | 音声文字起こし（Plaud / Teams 等）から、決定事項・保留・TODO を抽出した共有用議事録を生成 | 「この transcript を議事録化して」 | `giziroku/` の議事録 Markdown |
| `friday-daily-report` | jarvis-record の作業記録から、非エンジニア向けに専門用語を排した日次報告スライドを生成 | 「今日の報告スライド作って」「6/27 を報告資料に」 | `report-deck/` の自己完結 HTML スライド |

## arc-reactor — コーディング・レビュー系

実装・レビュー・設計支援。対象は主に `projects/` 配下の実プロジェクト。

| スキル | 何をするか | 指示の例 | 成果物（出力先） |
|--------|-----------|----------|------------------|
| `arc-reactor-code-review` | 機能 / セキュリティ / パフォーマンス / アーキテクチャの 4 観点レビュー。重要度ラベル + file:line 付き | 「このプロジェクト全体をレビューして」「認証機能をセキュリティ観点で見て」 | レビュー指摘リスト |
| `arc-reactor-test-scaffolder` | 既存テストの流儀を検出してテスト雛形と主要ケース案を生成。ランナーで実行確認まで | 「このファイルのテスト書いて」「この変更にテスト足して」 | テストコード（実行確認済み） |
| `arc-reactor-codebase-onboarding` | 初見コードベースの全体地図・主要ユースケースのフロー追跡・読み始めポイントの 3 部構成資料 | 「オンボーディング資料を作って」「どこから読み始めればいい？」 | `projects/<project>/onboarding/` の Markdown（差分更新可） |
| `arc-reactor-tech-debt-auditor` | 技術負債をカテゴリ別にスキャンし、根拠 2 つ以上で「確定」、P1〜P4 の優先度付きリスト化 | 「技術負債を洗い出して優先度を付けて」 | 負債監査レポート Markdown |
| `arc-reactor-external-access-mapper` | 外部アクセス箇所（DB / 外部 API / SaaS / キュー等）を静的走査し、根拠付き台帳 + 呼び出し経路マップ化 | 「このリポジトリの外部アクセスを洗い出して」 | `<repo>/external-access-map/<日付>.md` |
| `arc-reactor-env-doctor` | 環境構築エラーの診断・修復と、再発防止のセットアップ手順書修正 diff 案 | 「npm install がコケるので直して」 | 修復 + README/setup の修正案 + 対応記録 |
| `arc-reactor-release-readiness-checker` | リリース文脈をヒアリングし、9 カテゴリのチェックリストで不足を Blocker/Should/Nice に分類 | 「このアプリ、リリースできる状態か確認して」 | `projects/<project>/release-readiness/` のレポート |
| `arc-reactor-slow-query-hunter` | スロークエリログ解析 or コードからのクエリ抽出で遅いクエリを特定し、EXPLAIN 根拠付き改善案を提示 | 「スロークエリを洗い出して」「N+1 になってる箇所を探して」 | スロークエリレポート Markdown |
| `arc-reactor-infra-architecture-designer` | インフラ構成の壁打ち。2〜3 案比較→構成図 + セキュリティセルフレビュー + 設計記録 | 「この要件で AWS の構成図を描いて」 | `projects/<project>/infra-design/` の構成図・設計記録 |
| `arc-reactor-pr-splitter` | 肥大化した diff・ブランチ・PR を意味単位の PR 列に分割。元は無傷、差分ゼロを検証 | 「この diff、大きすぎるから PR 分割して」 | 分割ブランチ列（希望すれば PR 作成まで） |
| `arc-reactor-db-migration-safety-checker` | マイグレーションの危険操作（ロック・データ破壊・非互換）を静的検出し、安全な代替手順を提示 | 「このマイグレーション、本番に流して大丈夫か見て」 | 危険度付き安全性レポート |
| `arc-reactor-sequence-diagram-generator` | エントリポイントから実コードを追跡し、Mermaid シーケンス図 1 枚を生成。外部 I/O を強調 | 「POST /orders がどう処理されるか図にして」 | Mermaid 図 + 補足（保存時は `docs/flows/` 等） |
| `arc-reactor-db-schema-designer` | テーブル設計の壁打ち。ER 図・DDL・マイグレーション案・設計判断の記録 + チェックリストでセルフレビュー | 「この機能の DB スキーマを設計して」「正規化するか迷ってるので壁打ちして」 | `docs/db-design/` 等の ER 図・DDL・設計記録 |
| `arc-reactor-api-designer` | REST / GraphQL API の設計壁打ち。既存 API の規約を抽出して一貫性を揃え、スキーマまで出す | 「この機能の API を設計して」「OpenAPI のスキーマを書いて」 | OpenAPI YAML / GraphQL SDL + 設計記録 + 一貫性セルフレビュー |

## edith — 調査・データ収集・分析系

Web 探索を伴うリサーチ。すべての事実主張に出典 URL・取得日を付ける。

| スキル | 何をするか | 指示の例 | 成果物（出力先） |
|--------|-----------|----------|------------------|
| `edith-tech-selection-research` | 技術選定調査。固定 7 軸（成熟度 / メンテ / ライセンス等）で候補を比較し推奨 + 次点を出す | 「Next.js と Remix を比較して技術選定して」 | `tech-selection/` の比較表 + 選定記録 |
| `edith-freelance-rate-research` | フリーランス（SES・準委任）の単価相場を複数ソース横断で調査。交渉材料づくり | 「Go + AWS で経験 5 年、東京だと単価いくら？」 | 相場レンジ + 根拠付きレポート（免責付き） |
| `edith-competitor-market-scan` | 対象ドメインの競合・機能・価格・トレンドをスキャン | 「この案件の周辺市場をスキャンして」 | `market-scan/` の競合一覧 + トレンド要約レポート |
| `edith-product-discovery` | プロジェクトを調査し、要件定義前の機能案・課題仮説を 5 つの発想レンズで出して壁打ち・選別 | 「このプロダクトの改善アイデアを提案して」 | `projects/<project>/discovery/` のアイデアバックログ |

## ultron — 事務・金融・資産系

金額計算は必ず決定論的スクリプトが行い、Claude は暗算しない。出力は情報整理であって助言ではない。

| スキル | 何をするか | 指示の例 | 成果物（出力先） |
|--------|-----------|----------|------------------|
| `ultron-invoice-builder` | 稼働時間・単価から適格請求書（インボイス）要件を満たす月次請求書を作成。税・源泉はスクリプト検算 | 「今月の請求書を作って」「6 月分の稼働 160.5 時間で請求書にして」 | `invoice-data/invoices/` の請求書 + 内訳表 |
| `ultron-timesheet-aggregator` | worklog・Google カレンダーから案件別・日別の稼働時間サマリを集計（請求書の入力になる） | 「今月の稼働時間を集計して」 | `timesheet-data/` の月次 JSON + 稼働サマリ |
| `ultron-tax-prep-organizer` | 銀行 / クレカ明細等を勘定科目別集計 + 要確認リストに整理（青色申告の準備） | 「確定申告用に経費を整理して」 | `tax-data/` の科目別サマリ（Markdown + JSON） |
| `ultron-contract-review-assistant` | 業務委託・SES 契約書の要注意条項洗い出しと先方への確認事項整理（法的助言ではない） | 「この契約書をレビューして」 | 要注意条項表 + 確認文例のレポート |
| `ultron-personal-budget-manager` | 個人の家計管理。レシート画像・Gmail の領収書メールから明細を取り込み、月次収支を集計 | 「今月の家計をまとめて」「このレシート読み込んで」 | `budget-data/` の月次エントリ + 収支集計 |
| `ultron-family-budget-manager` | 夫婦の共同支出（食費中心）のレシートを記録し、割り勘精算用の月次集計を作る | 「レシート集計して」「割り勘用の集計出して」 | `shared-expense-data/` の transactions.jsonl + summary.md |
| `ultron-dividend-recorder` | 配当金計算書の画像から配当実績を抽出し、台帳へ記録・集計（personal-dashboard が参照） | 「この配当金計算書を記録して」「今年の配当いくら？」 | `dividend-data/records.json` の配当台帳 |
| `ultron-high-dividend-stock-screener` | 日本の高配当株（利回り 4% 以上 + 健全性フィルタ）をスクリーニングし候補リスト化。続きから再開可 | 「高配当株のおすすめをリストにして」 | 候補リスト + 調査台帳（免責・レビュー付き） |

## griot — 練習・コーチング系

自分が話して伝える力を鍛える個人練習・コーチング。聞き手は自分自身。
説明練習は prep（Step 1: 準備）→ 自分で口頭説明・録音（Step 2）→ coach（Step 3: 添削）→
english（Step 4: 英語化）のパイプラインで回す。データはすべて `explain-practice-data/`（git 管理外）。

| スキル | 何をするか | 指示の例 | 成果物（出力先） |
|--------|-----------|----------|------------------|
| `griot-explain-prep` | その日学んだことを壁打ちで言語化（Claude は代筆せず不足・曖昧を指摘）し、固定テンプレのノートと「見ながら話す」1 枚 HTML 資料を生成 | 「今日の説明練習の準備」「学んだことを言語化したい」 | `explain-practice-data/sessions/<日付>-<slug>/` の note.md + deck.html |
| `griot-explain-coach` | 口頭説明の文字起こしを、毎回インプットする想定聞き手（ペルソナ）に伝わるかの観点で添削。指摘は固定カテゴリで台帳に蓄積し、定期的に苦手傾向を分析 | 「この説明を添削して」「苦手分析して」 | review.md + `review-log.jsonl`（指摘台帳）+ 月次分析レポート |
| `griot-explain-english` | 練習した説明の英語版資料と音読用の口語スクリプト（対訳・キーフレーズ・発音注意付き）を生成。英語学習を兼ねる | 「これを英語でも練習したい」 | 同セッション `en/` の deck-en.html + script-en.md |

## karen — 一時利用・汎用系

| スキル | 何をするか | 指示の例 | 成果物（出力先） |
|--------|-----------|----------|------------------|
| `karen-problem-essence-organizer` | 課題発見→整理→解決定義→手段検討の 4 フェーズで思考整理。手段先行を批判的に指摘 | 「思考を整理したい」「目的ってなんだっけ」 | 自分用 Markdown + クライアント向け HTML |
| `karen-learning-roadmap` | 学習ロードマップの設計と進捗レビュー。達成基準付きマイルストーン + 週次計画 | 「AWS SAA を 3 ヶ月で取りたい、学習計画を立てて」 | `learning-roadmaps/` のロードマップ Markdown |
| `karen-meeting-prep-briefer` | 会議「前」の事前ブリーフ。過去議事録・記録を横断し、論点・スタンス案・想定質問を整理 | 「明日の打合せのブリーフ作って」 | 論点整理済み事前ブリーフ（固定フォーマット） |
| `karen-self-evolving-skill-creator` | 自己進化パイプライン（実行ログ蓄積→SKILL.md 自己書き換え）付きの新スキルを生成するメタスキル | 「使うほど賢くなるスキルを作って」 | 新スキル一式（`.claude/skills/` 配下） |

## vision — プライベート・人間関係系

| スキル | 何をするか | 指示の例 | 成果物（出力先） |
|--------|-----------|----------|------------------|
| `vision-people-memory` | 雑談・家族との会話の文字起こしから、人物ごとの話題・近況・好みを 1 人 = 1 ノートに蓄積 | 「この雑談を〇〇さんのメモに追記して」「〇〇さんノート見せて」 | 人物ノート（読み手は自分だけ） |

## 典型的なスキルの連携

単体でも動くが、次のパイプラインで繋がるものがある。

- **日次報告**: `jarvis-worklog`（ログ整理）→ `jarvis-record`（一次記録）→ `friday-daily-report`（報告スライド）
- **ナレッジ・記事化**: `jarvis-worklog`（tech digest）→ `jarvis-knowledge-base`（vault）→ `friday-tech-article-drafter`（公開記事）
- **自由形式ドキュメント**: `friday-doc-planner`（企画）→ `friday-design-doc-generator` / `friday-proposal-generator` / `friday-tech-article-drafter` / `friday-procedure-doc-generator`（生成）
- **請求**: `ultron-timesheet-aggregator`（稼働集計）→ `ultron-invoice-builder`（請求書）
- **開発ループ**: `edith-product-discovery`（アイデア出し）→ `jarvis-issue-planner`（Issue 化）
- **ToDo**: 各スキル・議事録・調査から `jarvis-todo-management` が収穫 → `jarvis-todo-prioritizer` が優先度付け
- **説明練習**: `griot-explain-prep`（言語化 + 資料）→ 口頭説明・録音（自分）→ `griot-explain-coach`（添削・苦手分析）→ `griot-explain-english`（英語化）
