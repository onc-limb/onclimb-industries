# スキル候補一覧（バックログ）

「ビジネス上あると良さそう」というスキルの**概要だけ**を並べた一覧。
詳細は未検討で、実際に作るかどうかも未定のたたき台。

- ここは軽量なバックログ。正式に検討を始めるものは [`TEMPLATE.md`](TEMPLATE.md) を複製して
  「1 アイデア = 1 ファイル」で書き起こす（[運用ルール](README.md)参照）。
- エンジニアリング作業（開発・運用・インフラ）に特化した候補は
  [`engineer-skill-candidates.md`](engineer-skill-candidates.md) に分冊している。
- 分類プレフィックスは [`../personas/`](../personas/) / [`../.claude/skills/README.md`](../.claude/skills/README.md) に準拠。

| 候補名（仮） | 分類 | 解決したい場面・課題 | 想定 入力 → 出力（概要） | メモ |
|---|---|---|---|---|
| pr-reviewer | arc-reactor | PR レビューの初動が遅い／観点が属人的 | diff → 観点別レビューコメント（バグ・可読性・規約） | 実装済み → [pr-reviewer.md](pr-reviewer.md) |
| test-scaffolder | arc-reactor | テストを書く工数が惜しく後回しになる | 対象コード → テスト雛形＋主要ケース案 | 実装済み → [test-scaffolder.md](test-scaffolder.md) |
| codebase-onboarding | arc-reactor | 参画直後に他人のコードベース把握に時間がかかる | リポジトリ → 全体地図・主要フロー・読み始めポイント | 既存 `codebase-reader` の拡張案。実装済み → [codebase-onboarding.md](codebase-onboarding.md) |
| tech-debt-auditor | arc-reactor | 技術負債が可視化されず溜まる | リポジトリ → 負債候補リスト＋優先度 | 誤検知の抑制が肝。実装済み → [tech-debt-auditor.md](tech-debt-auditor.md) |
| tech-selection-research | edith | ライブラリ/技術選定の比較が毎回ゼロから | テーマ・要件 → 出典付き比較表＋推奨 | `deep-research` の派生。実装済み → [tech-selection-research.md](tech-selection-research.md) |
| freelance-rate-research | edith | 単価・案件相場の肌感がなく交渉材料が薄い | 職種・スキル・地域 → 相場レンジ＋根拠 | 情報整理であり保証ではない旨明記。実装済み → [freelance-rate-research.md](freelance-rate-research.md) |
| competitor-market-scan | edith | 案件/自社サービスの周辺市場が見えない | ドメイン → 競合・トレンド要約 | 出典明示・鮮度注意。実装済み → [competitor-market-scan.md](competitor-market-scan.md) |
| proposal-generator | friday | 提案書・見積の作成が毎回手作業 | 要件・工数 → 提案書ドラフト（構成固定） | 見積根拠の透明性が必要。実装済み → [proposal-generator.md](proposal-generator.md) |
| tech-article-drafter | friday | 発信（ブログ/登壇）が後回しで実績が残らない | worklog/knowledge-base → 記事ドラフト | 機密マスキング必須。実装済み → [tech-article-drafter.md](tech-article-drafter.md) |
| design-doc-generator | friday | 設計書・README が整備されない | コード・会話 → 設計書/README 草案 | 事実に基づき創作しない。実装済み → [design-doc-generator.md](design-doc-generator.md) |
| invoice-builder | ultron | 請求書作成・稼働集計が毎月手間 | 稼働ログ・単価 → 請求書＋内訳 | 金額計算の検算を担保。実装済み → [invoice-builder.md](invoice-builder.md) |
| timesheet-aggregator | ultron | 稼働時間の集計が散在して面倒 | worklog/カレンダー → 案件別稼働サマリ | 個人情報・機密の扱い。実装済み → [timesheet-aggregator.md](timesheet-aggregator.md) |
| tax-prep-organizer | ultron | 確定申告用の経費・売上整理が煩雑 | 取引データ → 勘定科目別集計 | 税務助言ではなく整理。実装済み → [tax-prep-organizer.md](tax-prep-organizer.md) |
| contract-review-assistant | ultron | 契約書の要注意点を見落とす | 契約書 → 要点・リスク・確認事項の抽出 | 法的助言ではない旨明記。実装済み → [contract-review-assistant.md](contract-review-assistant.md) |
| learning-roadmap | karen | 身につけたいスキルの学習計画が立てられない | 目標・現状 → 段階的ロードマップ | 実装済み → [learning-roadmap.md](learning-roadmap.md) |
| meeting-prep-briefer | karen | 打合せ前の論点整理・下調べが不足 | 議題・関連資料 → 事前ブリーフ | giziroku（事後）と対の位置づけ。実装済み → [meeting-prep-briefer.md](meeting-prep-briefer.md) |

## 使い方メモ

- 温めたい候補が出てきたら、この表から 1 行を選んで `TEMPLATE.md` に展開する。
- 展開して着手判断まで進んだら、この表の行は残しつつ「詳細ファイルへのリンク」をメモ欄に付ける。
- 見送りが確定した候補は行を消さず、メモ欄に「見送り理由」を一言添える。
