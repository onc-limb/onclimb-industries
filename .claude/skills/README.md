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
| `karen` | 一時利用・汎用系 | 用途が固定されない汎用・一時利用 |
| `vision` | （未定） | 名称案。分類は未確定 |

### jarvis と friday の判断軸

同じ「文書を作る」スキルでも、**誰が読むか**で分ける。

- **jarvis** … 読み手が AI もしくは自分自身。機械的なログ、一次記録、一次資料。清書前・共有前のもの。
- **friday** … 読み手が他者（上司・クライアント・チーム）。共有・発表を前提に整えたドキュメント。

例: worklog のログから当日の作業を機械的にまとめる一次記録（`jarvis-record`）は jarvis。
それを非エンジニア向けに清書・発表資料化する `friday-daily-report` は friday。

## 現在のスキル

| スキル | 分類 |
|--------|------|
| `jarvis-worklog` | 作業記録・一次資料系 |
| `jarvis-knowledge-base` | 作業記録・一次資料系 |
| `jarvis-record` | 作業記録・一次資料系 |
| `jarvis-todo-management` | 作業記録・一次資料系 |
| `jarvis-issue-planner` | 作業記録・一次資料系 |
| `friday-daily-report` | 共有ドキュメント系 |
| `friday-giziroku` | 共有ドキュメント系 |
| `friday-proposal-generator` | 共有ドキュメント系 |
| `friday-tech-article-drafter` | 共有ドキュメント系 |
| `friday-design-doc-generator` | 共有ドキュメント系 |
| `arc-reactor-code-review` | コーディング・レビュー系 |
| `arc-reactor-test-scaffolder` | コーディング・レビュー系 |
| `arc-reactor-codebase-onboarding` | コーディング・レビュー系 |
| `arc-reactor-tech-debt-auditor` | コーディング・レビュー系 |
| `edith-tech-selection-research` | 調査・データ収集・分析系 |
| `edith-freelance-rate-research` | 調査・データ収集・分析系 |
| `edith-competitor-market-scan` | 調査・データ収集・分析系 |
| `ultron-high-dividend-stock-screener` | 事務・金融・資産系 |
| `ultron-invoice-builder` | 事務・金融・資産系 |
| `ultron-timesheet-aggregator` | 事務・金融・資産系 |
| `ultron-tax-prep-organizer` | 事務・金融・資産系 |
| `ultron-contract-review-assistant` | 事務・金融・資産系 |
| `ultron-household-budget-manager` | 事務・金融・資産系 |
| `karen-problem-essence-organizer` | 一時利用・汎用系 |
| `karen-self-evolving-skill-creator` | 一時利用・汎用系 |
| `karen-learning-roadmap` | 一時利用・汎用系 |
| `karen-meeting-prep-briefer` | 一時利用・汎用系 |

## 補足

- **データ出力ディレクトリ名は改名対象外**。各スキルがリポジトリ直下に生成するデータ置き場
  （例: `worklog-data/`, `knowledge-base/`, `report-record/`, `report-deck/`, `giziroku/`）や、
  スクリプト内部のモジュール名・環境変数（`worklog_lib`, `REPORT_DECK_DIR` 等）は、
  既存データとの整合を保つため旧名のまま運用する。プレフィックス規約は**スキルの識別子**
  （ディレクトリ名 / `name:`）にのみ適用する。
