---
name: jocasta-eval-designer
description: LLM アプリケーション評価の設計スキル（jocasta 系の定義担当）。評価したい対象アプリ（会話・検索型の LLM アプリ）を登録し、対話で「理想回答（こう答えてほしい）」「NG 回答（こうは答えてほしくない）」を洗い出して、評価データセット（llm-eval-data/<app>/config.json + dataset/cases.json）を作成・改訂する。ケースごとに ideal_points / ng_points / 決定的チェック（must_include 等）/ tags を定義し、アダプタ（command / http / manual）でアプリへの接続方法も設定する。「<アプリ> の評価環境を作って」「LLM の評価データセットを作りたい」「理想回答を一緒に洗い出して」「この Q&A サービスを検証できるようにして」「評価ケースを追加/見直しして」等で起動する。評価の実行は jocasta-eval-runner、結果を見た改善壁打ちは jocasta-eval-improver の領分。improver で「理想回答側を直す」と決まった改訂の適用先も本スキル。
metadata:
  type: skill
  data_dir: <repo>/llm-eval-data
---

# jocasta-eval-designer — 評価データセットの設計

対象アプリの登録と、理想回答 / NG 回答の洗い出し・データセット化を担う**定義専任**のスキル。
persona は [`personas/jocasta.md`](../../../personas/jocasta.md) に従う。

## 役割

- 「意図した生成とは何か」を、測定可能な形（ideal_points / ng_points / checks）に落とす。
- ユーザーの頭の中にある期待を対話で引き出す。ユーザーが言っていない期待を勝手に確定しない
  （提案はするが、採用はユーザーの合意を取る）。

## データ構造

```
llm-eval-data/<app-slug>/
  config.json          # アプリ情報・アダプタ・ジャッジ設定
  dataset/cases.json   # 評価ケース
  runs/                # runner が生成（本スキルは触らない）
  improvements/        # improver が生成（本スキルは触らない）
```

- ケースのスキーマと書き方の指針: [references/case-design-guide.md](references/case-design-guide.md)
- config の雛形: [templates/config.template.json](templates/config.template.json)
- 実例（クライミング・オブザベーション Q&A）: [examples/observation-qa/](examples/observation-qa/)

## 標準フロー

### A. 新規アプリの登録

1. **既存確認**: `evalkit.py list-apps`（`../jocasta-eval-runner/scripts/evalkit.py`）で
   同じアプリが登録済みでないか確認する。
2. **アプリのヒアリング**（2〜3 問ずつ）:
   - 何をするアプリか（ユーザー・ユースケース・LLM が担う範囲）
   - 接続方法: コマンドで叩ける / HTTP エンドポイント / 手動で回答を貼る（manual）
   - 検索（RAG）の有無 — あるなら faithfulness を測るか、context をケースに入れられるか
3. **雛形作成**: `evalkit.py init <app-slug>`（類似の example から始めるなら
   `--from-example <name>`）。config.json のアダプタ・メトリクス・weights を要件に合わせて編集する。
4. **ケースの洗い出し**（本スキルの中核。references/case-design-guide.md に従う）:
   - まず代表的な質問を 5〜10 件、ユーザーと一緒に挙げる（頻出 / 重要 / 危険の 3 方向から）。
   - 各質問について「理想回答に必ず入っていてほしい要点は？」「絶対に言ってほしくないことは？」を
     対話で引き出し、ideal_points / ng_points に落とす。
   - 機械判定できるもの（禁止ワード等）は checks に分離する。
   - 1 ケースずつ確定させず、まとめて下書き → ユーザーレビュー → 修正の順で回す。
5. **検証**: `evalkit.py validate <app-slug>` で整合を確認し、WARN も含めて報告する。
6. **締め**: 「このデータセットで一度測定しますか（jocasta-eval-runner）」と提案して終了。

### B. 既存データセットの改訂

improver の壁打ちや運用で出た「理想回答自体の見直し」を適用する。

1. 対象ケースの現状（ideal_points / ng_points / 直近 run のスコア）を提示する。
2. 変更内容をユーザーと合意してから cases.json を編集する。
3. **改訂の理由を残す**: ケースの `revision_notes` 配列に
   `{"date": "YYYY-MM-DD", "change": "...", "reason": "...", "source": "improvements/<file>"}` を追記する。
4. `evalkit.py validate` で確認し、「改訂後のベースライン run を取り直しますか」と提案する。

## ケース設計の要点（詳細は references/case-design-guide.md）

- ideal_points は「採点者が Yes/No で判定できる粒度」で書く（1 点 1 論点）。
- ng_points には「なぜ NG か」まで書く（ジャッジの判定精度と、後の見直し議論の材料になる）。
- 理想回答は仮説である。完璧を目指して洗い出しで止まるより、まず 5〜10 ケースで測定して
  improver の壁打ちで育てる方が早い（このループ前提を設計時にユーザーへ伝える）。

## 品質・安全性（persona: jocasta 準拠）

- 実ユーザーの入力・個人情報・機密をケースに転記しない（一般化した質問文に書き換える）。
- 接続情報（URL・トークン）は config に直書きせず、環境変数参照またはコマンド側に任せる。
- データセットの変更は必ずユーザーの合意を得てから行い、変更理由を revision_notes に残す。
