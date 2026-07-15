# スキル命名規約

このディレクトリ配下のスキルは、**分類プレフィックス + スキル名** の形式で命名する。

```
<prefix>-<skill-name>/
```

- プレフィックスはスキルの分類を表す（下表）。
- ディレクトリ名と `SKILL.md` の `name:` フロントマターは必ず一致させる。
- スキルを新規追加・分類変更するときは、まずこの表に従ってプレフィックスを決める。
- 各分類の共通ルールは [`personas/<prefix>.md`](../../personas/) にある。新規スキルは対応する persona を参照して設計する（[ルート `CLAUDE.md`](../../CLAUDE.md) 参照）。

## プレフィックス一覧

| プレフィックス | 分類 | 説明 |
|----------------|------|------|
| `jarvis` | 作業記録・一次資料系 | AI に読ませる機械的なログや、自分自身が見る一次資料的なもの（作業ログの収集・分類・整理、一次記録、ナレッジ蓄積） |
| `friday` | 共有ドキュメント系 | 上司・クライアント・チームメンバーに共有する発表資料やプロジェクトドキュメントの作成（議事録・報告スライドなど） |
| `arc-reactor` | コーディング・レビュー系 | 実装・リファクタリング・コードレビュー |
| `ultron` | 事務・金融・資産系 | 事務作業・金融・資産運用 |
| `edith` | 調査・データ収集・分析系 | リサーチ・データ収集・分析 |
| `griot` | 練習・コーチング系 | 報告説明・プレゼン・英会話など、自分が話して伝える力を鍛える個人練習・コーチング。聞き手は自分自身 |
| `karen` | 一時利用・汎用系 | 用途が固定されない汎用・一時利用 |
| `vision` | プライベート・人間関係系 | 仕事の成果物ではない私生活領域（人間関係の記録・家族・個人の暮らし）。読み手は自分だけ |
| `jocasta` | LLM 評価・検証系 | LLM を使ったアプリケーションの生成品質の検証・改善（理想/NG 回答の定義、LLM-as-a-judge による採点、壁打ちによる根本改善） |

### jarvis と friday の判断軸

同じ「文書を作る」スキルでも、**誰が読むか**で分ける。

- **jarvis** … 読み手が AI もしくは自分自身。機械的なログ、一次記録、一次資料。清書前・共有前のもの。
- **friday** … 読み手が他者（上司・クライアント・チーム）。共有・発表を前提に整えたドキュメント。

例: worklog のログから当日の作業を機械的にまとめる一次記録（`jarvis-record`）は jarvis。
それを非エンジニア向けに清書・発表資料化する `friday-daily-report` は friday。

### friday 系の 2 段構成（doc planner → 生成スキル）

自由形式の共有ドキュメント（設計書・提案書・技術記事など）は 2 段で作る。

- **Stage 0: `friday-doc-planner`** — 対話で目的（読者の行動レベルまで）× 対象読者を確定し、
  型（説明/説得/報告）と読まれ方（辞書的/読み物的）を導出、テーマの設定・分解と情報源の確定まで
  行って、ドキュメント企画書（doc brief）を `doc-briefs/` に作る。
- **Stage 1: 種類別の生成スキル**（`friday-design-doc-generator` / `friday-proposal-generator` /
  `friday-tech-article-drafter` / `friday-procedure-doc-generator`）— brief を入力に、骨組み（見出し構成）と本文を生成する。
  重複ヒアリングは省略。brief 無しの単体起動も従来どおり可。

入力・テンプレートが固定のパイプライン型（`friday-giziroku` / `friday-daily-report`）は
この 2 段構成の対象外で、従来どおり単体で起動する。

## 現在のスキル

| スキル | 分類 |
|--------|------|
| `jarvis-worklog` | 作業記録・一次資料系 |
| `jarvis-knowledge-base` | 作業記録・一次資料系 |
| `jarvis-record` | 作業記録・一次資料系 |
| `jarvis-todo-management` | 作業記録・一次資料系 |
| `jarvis-todo-prioritizer` | 作業記録・一次資料系 |
| `jarvis-issue-planner` | 作業記録・一次資料系 |
| `jarvis-reading-notes` | 作業記録・一次資料系 |
| `jarvis-capture` | 作業記録・一次資料系 |
| `friday-doc-planner` | 共有ドキュメント系 |
| `friday-daily-report` | 共有ドキュメント系 |
| `friday-giziroku` | 共有ドキュメント系 |
| `friday-proposal-generator` | 共有ドキュメント系 |
| `friday-tech-article-drafter` | 共有ドキュメント系 |
| `friday-design-doc-generator` | 共有ドキュメント系 |
| `friday-procedure-doc-generator` | 共有ドキュメント系 |
| `friday-skillset-writer` | 共有ドキュメント系 |
| `arc-reactor-code-review` | コーディング・レビュー系 |
| `arc-reactor-test-scaffolder` | コーディング・レビュー系 |
| `arc-reactor-codebase-onboarding` | コーディング・レビュー系 |
| `arc-reactor-tech-debt-auditor` | コーディング・レビュー系 |
| `arc-reactor-external-access-mapper` | コーディング・レビュー系 |
| `arc-reactor-env-doctor` | コーディング・レビュー系 |
| `arc-reactor-release-readiness-checker` | コーディング・レビュー系 |
| `arc-reactor-slow-query-hunter` | コーディング・レビュー系 |
| `arc-reactor-infra-architecture-designer` | コーディング・レビュー系 |
| `arc-reactor-pr-splitter` | コーディング・レビュー系 |
| `arc-reactor-db-migration-safety-checker` | コーディング・レビュー系 |
| `arc-reactor-sequence-diagram-generator` | コーディング・レビュー系 |
| `arc-reactor-db-schema-designer` | コーディング・レビュー系 |
| `arc-reactor-api-designer` | コーディング・レビュー系 |
| `edith-tech-selection-research` | 調査・データ収集・分析系 |
| `edith-freelance-rate-research` | 調査・データ収集・分析系 |
| `edith-competitor-market-scan` | 調査・データ収集・分析系 |
| `edith-product-discovery` | 調査・データ収集・分析系 |
| `edith-cli-command-quality` | 調査・データ収集・分析系 |
| `ultron-high-dividend-stock-screener` | 事務・金融・資産系 |
| `ultron-invoice-builder` | 事務・金融・資産系 |
| `ultron-timesheet-aggregator` | 事務・金融・資産系 |
| `ultron-tax-prep-organizer` | 事務・金融・資産系 |
| `ultron-contract-review-assistant` | 事務・金融・資産系 |
| `ultron-personal-budget-manager` | 事務・金融・資産系 |
| `ultron-family-budget-manager` | 事務・金融・資産系 |
| `ultron-dividend-recorder` | 事務・金融・資産系 |
| `griot-explain-prep` | 練習・コーチング系 |
| `griot-explain-coach` | 練習・コーチング系 |
| `griot-explain-english` | 練習・コーチング系 |
| `vision-people-memory` | プライベート・人間関係系 |
| `jocasta-eval-designer` | LLM 評価・検証系 |
| `jocasta-eval-runner` | LLM 評価・検証系 |
| `jocasta-eval-improver` | LLM 評価・検証系 |
| `jocasta-eval-autopilot` | LLM 評価・検証系 |
| `karen-problem-essence-organizer` | 一時利用・汎用系 |
| `karen-self-evolving-skill-creator` | 一時利用・汎用系 |
| `karen-learning-roadmap` | 一時利用・汎用系 |
| `karen-meeting-prep-briefer` | 一時利用・汎用系 |

## 補足

- **モデル割り当て**: スキル・作業ごとの適正モデル（haiku/sonnet/opus/fable）は
  [`personas/model-selection.md`](../../personas/model-selection.md) に従う。定型・台帳系スキルは
  frontmatter `model: sonnet` でピン留め済み。判断・設計・発想系はセッションモデルを継承する。
  新規スキル作成時はこのガイドで「ピンか継承か」を決めてから frontmatter を書く。
- **文章表現の共通ルール**: 文書を生成するスキルは、AI 感を減らす共通スタイルガイド
  [`personas/writing-style.md`](../../personas/writing-style.md) に従う（friday 系は清書パス必須、
  jarvis 系は一次情報の保全側で対応）。
- **データ出力ディレクトリ名は改名対象外**。各スキルがリポジトリ直下に生成するデータ置き場
  （例: `worklog-data/`, `knowledge-base/`, `report-record/`, `report-deck/`, `giziroku/`）や、
  スクリプト内部のモジュール名・環境変数（`worklog_lib`, `REPORT_DECK_DIR` 等）は、
  既存データとの整合を保つため旧名のまま運用する。プレフィックス規約は**スキルの識別子**
  （ディレクトリ名 / `name:`）にのみ適用する。
