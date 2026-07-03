---
name: edith-cli-command-quality
description: Claude が実行した CLI コマンドのログ(jarvis-worklog の raw、または素の CLI トランスクリプト ~/.claude/projects)を集計し、(1)人間もよく使う Linux/Mac コマンドの品質チェック観点を「何を確認すべきか」の学習素材として提示し、(2)危険コマンド(rm -rf / dd / curl|sh 等)の出現をチェックする分析スキル(edith 系)。決定論スクリプトが頻度ランキング・アンチパターン検出・危険パターン照合を集計し、ダッシュボードプロダクト連携用の command-metrics.json(スキーマ固定)と、人間向けの学習レポート Markdown を cli-quality/ に出力する。「Claude がよく使う CLI コマンドをランキングにして」「コマンドの品質を確認して学習用にまとめて」「危険コマンドが使われてないかチェックして」「ダッシュボード用にコマンドメトリクスの JSON を出して」「先月分の CLI コマンド品質を分析して」等で、ユーザーが明示的に依頼したときだけ起動する(自動起動しない)。作業ログの収集・整理を行う jarvis-worklog とは別系統で、本スキルは収集済みログを入力にした二次分析に徹する(worklog には組み込まない)。
metadata:
  type: skill
  persona: edith
  data_dir: <repo>/cli-quality
  json_output: command-metrics.json
  schema_version: "1.0"
---

# cli-command-quality — CLI コマンド品質分析

Claude が実行した Bash コマンドのログを入力に、**コマンド品質の学習素材**と
**危険コマンドの出現チェック**を、出典・網羅範囲付きでまとめる分析スキル。

> persona: [`personas/edith.md`](../../../personas/edith.md) — 出典明示・事実と解釈の区別・
> 複数切り口での網羅・未カバー範囲の明示を原則とする。集計は決定論スクリプトが担い、
> LLM は合計を暗算しない。

## 目的（2 本柱）

1. **品質確認 → 人間の学習**: 人間もよく使う Linux/Mac コマンドを対象に、
   「そのコマンドを使うとき何を品質確認すべきか」（`references/command_catalog.json` の
   checkpoints）を提示し、ログ中で実際に出たアンチパターンを実例として添える。
2. **危険コマンドの出現チェック**: `rm -rf /` / `dd of=/dev/...` / `curl|sh` /
   フォークボム等（`references/dangerous_patterns.json`）の出現を重大度付きで検出する。

出力の一次消費者は**外部のダッシュボードプロダクト**（`command-metrics.json` を読む）と、
**人間の学習**（Markdown レポート）。

## データ配置

- 入力ログ: `<repo>/worklog-data/raw`（jarvis-worklog が収集済みの場合）または
  `~/.claude/projects`（素の CLI トランスクリプト。worklog 未収集でも直接分析できる）。
- 出力: `<repo>/cli-quality/<YYYY-MM-DD>/`
  - `command-metrics.json` … ダッシュボード連携用（スキーマ: [`references/json_schema.md`](references/json_schema.md)）
  - `report.md` … 人間向け学習レポート（[`templates/report.md`](templates/report.md) 準拠）
- `cli-quality/` は機密(私的パス等)を含みうるため **git 管理外**（ルート `.gitignore` で除外）。

## トリガー

| ユーザー発話の例 | 動作 |
|---|---|
| 「よく使う CLI コマンドをランキングにして」 | フル分析（ランキング + 品質 + 危険） |
| 「コマンドの品質を確認して学習用にまとめて」 | 品質観点レポートに力点 |
| 「危険コマンドが使われてないかチェックして」 | 危険コマンド出現に力点 |
| 「ダッシュボード用にメトリクス JSON を出して」 | `command-metrics.json` の生成に力点 |
| 「先月分の CLI コマンド品質を分析して」 | 期間/ソースを確認して分析 |

明示的な依頼でのみ起動する。他スキルの作業中に CLI の話題が出ても自動起動しない。

## 標準フロー

### 1. 入力の確定（分析前に確認する）

- **ソース**: `worklog-data/raw` があるか？ 無ければ `~/.claude/projects` を使う。
  どちらも無ければユーザーにパスを尋ねる（勝手に広い範囲を走査しない）。
- **範囲**: 全期間か特定期間か（現状スクリプトは全 `*.jsonl` を走査。期間で絞るなら
  対象ディレクトリ/ファイルを渡す運用にする）。
- **力点**: 品質学習 / 危険チェック / JSON 生成 のどれを主に見たいか。

### 2. 集計（決定論スクリプト）

```bash
python3 .claude/skills/edith-cli-command-quality/scripts/analyze_commands.py \
  <log-root> \
  --out <repo>/cli-quality/<YYYY-MM-DD> \
  --date <YYYY-MM-DD> \
  --top 40
```

- スクリプトが両ログフォーマット（worklog raw / CLI native）を吸収し、コマンドを
  パイプ/連結で分解 → 頻度集計 → カタログ照合（品質観点・アンチパターン）→
  危険パターン照合を行い、`command-metrics.json` を書き出す。
- 標準出力にランキングと危険コマンドの要約が出る。**この数値は転記する（暗算しない）**。

### 3. 学習レポートの作成（LLM の担当）

`command-metrics.json` と `templates/report.md` を基に、人間向け `report.md` を書く。

- ランキング上位のうち **`human_common: true`** のコマンドを主対象にする。
- 各コマンドの `quality_checkpoints`（何を確認すべきか）を学習ポイントとして提示し、
  `antipatterns_found` があれば実例付きで「自分の癖の点検材料」として添える。
- 危険コマンドは `severity` critical / high を必ず目立たせ、代表例と対処を書く。
- **事実（集計値・実例）と解釈（学習上の助言）を区別**する。集計に無い主張を足さない。
- 網羅できなかった範囲（Web 版ログ、`$(...)` 入れ子の一部）を明記する（edith 原則）。

### 4. ダッシュボード連携の確認

- `command-metrics.json` のパスと `schema_version` をユーザーに伝える。
- スキーマは [`references/json_schema.md`](references/json_schema.md) で固定。破壊的変更時のみ
  `schema_version` をメジャー更新する（ダッシュボード側の前方互換のため）。

## 固定の芯（崩さない部分）

- **集計は決定論スクリプト、解釈は LLM** の分担（LLM は合計を暗算しない）。
- **出力 JSON のスキーマは固定**（`schema_version` で管理）。勝手にフィールドを消さない。
- **危険コマンドの検出は「確認を促すシグナル」**であり、実行の是非の断定ではない。
- 機密（私的パス・トークン等）は出力に残さない。ログ側の redaction を前提としつつ、
  危険コマンドの occurrence は必要最小限（先頭 300 字・15 件まで）に留める。

## カタログの育て方（辞書資産）

品質観点・アンチパターン・危険パターンは辞書資産として外部 JSON に切り出している。
気づいた観点は 1 件でもその場で追記してよい（SKILL.md 本体の書き換えは伴わない）。

- 品質観点・アンチパターン: [`references/command_catalog.json`](references/command_catalog.json)
- 危険パターン: [`references/dangerous_patterns.json`](references/dangerous_patterns.json)

スキル本体のフロー・出力構成への不満は、その場で直さず中央インボックス
[`ideas/skill-feedback.md`](../../../ideas/skill-feedback.md) にためる（ルート CLAUDE.md の運用に従う）。

## スコープ外

- ログの**収集・分類・整理**は jarvis-worklog の責務。本スキルは収集済みログの二次分析に徹する。
- コード変更を伴うレビュー・リファクタは arc-reactor 系の責務。
- 出力は CLI 利用ログの機械的な整理であって、実行の是非の最終判断ではない。
