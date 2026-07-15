---
name: jocasta-eval-runner
description: LLM アプリケーションの評価実行スキル（jocasta 系の測定担当）。jocasta-eval-designer で定義したデータセット（理想回答の要点 / NG 回答 / 決定的チェック）を入力に、アダプタ（command / http / manual）経由で対象アプリの回答を収集し、決定的チェック + LLM-as-a-judge（correctness / completeness / ng_compliance / relevancy / faithfulness の RAGAS 風メトリクス）で採点して、run 単位の評価レポート（llm-eval-data/<app>/runs/<run-id>/report.md）を生成する。run は不変で、改善後は新 run を取って compare で差分を見る。「<アプリ> の評価を回して」「eval を実行して」「回答を収集して採点して」「評価レポートを出して」「前回の run と比較して」等で起動する。データセットの作成・改訂は jocasta-eval-designer、レポートを元にした壁打ち・改善案出しは jocasta-eval-improver の領分。
metadata:
  type: skill
  data_dir: <repo>/llm-eval-data
---

# jocasta-eval-runner — LLM アプリ評価の実行

対象アプリの回答を収集し、決定的チェック + LLM-as-a-judge で採点してレポートを出す
**測定専任**のスキル。persona は [`personas/jocasta.md`](../../../personas/jocasta.md) に従う。

## 役割

- designer が定義した「理想回答 / NG 回答」に対して、アプリの現状を**再現可能な数値**にする。
- 測定するだけで判断しない。改善の議論は improver へ、データセットの修正は designer へ渡す。

## 事実ベースの原則（必須）

persona の「事実ベースの原則」に完全に従う。本スキルでの具体形:

- 結果の提示は run の実データ（summary.json / scores.jsonl / judgments.jsonl の reason /
  responses.jsonl の実文）の引用のみで行う。データに無い傾向・原因をコメントしない。
- 「なぜ低いか」の解釈を求められたら、ジャッジの reason と回答の実文を引用して示す。
  それ以上の原因分析は improver の壁打ちへ回す（このスキルで推測の原因を語らない）。

## ステップの独立実行

「検証（収集）」と「評価（採点）」は独立したステップとして単体実行できる。

- **検証のみ**: `collect` だけ実行して回答を確認し、採点は後で行う（または行わない）。
- **評価のみ**: 既存 run に対して `judge` → `score` → `report` を実行・再実行する。
  - dataset の ideal_points / ng_points を改訂した後に、**同じ回答のまま再採点**して
    ものさし側の変更の影響だけを見る、という使い方ができる（`judge` を再実行。
    既存の judgments.jsonl は上書きされるため、残したい場合は run ディレクトリごと
    コピーしてから行い、コピーであることを run.json の note に記す）。
  - weights / pass_threshold の変更だけなら `score` → `report` の再実行で反映できる（judge 不要）。

## 評価結果への壁打ち

report 提示後にユーザーから「この判定はおかしい」等の指摘があったら、次で応じる。

1. 該当ケースの質問・回答実文・ジャッジ reason を並べて提示し、**どの根拠で付いたスコアか**を示す。
2. 指摘が正しい（reason が回答の実態と食い違う）場合: ジャッジの揺らぎ・基準の曖昧さとして
   扱い、基準の明確化（designer）か再 judge を提案する。スコアの手動書き換えはしない。
3. 判定基準そのものへの不満なら improver（切り分け議論）または designer（基準改訂）へ接続する。

## 前提

- `llm-eval-data/<app>/config.json` と `dataset/cases.json` が存在すること
  （無ければ先に `jocasta-eval-designer` を起動する）。
- LLM ジャッジは `claude` CLI（`claude -p --output-format json`）で行う。モデルは
  config.json の `judge.command` で指定（既定: `claude-sonnet-5`）。

## 標準フロー

すべて [scripts/evalkit.py](scripts/evalkit.py) 経由で行う（runs 配下を手で編集しない）。

1. **検証**: `evalkit.py validate <app>` — config / cases の整合を確認。ERROR があれば
   designer へ差し戻す。
2. **収集**: `evalkit.py collect <app> --note "<何を変えた後の測定か>"` — アダプタ経由で
   全ケースの回答を取り、新しい run（`runs/<YYYYMMDD-HHMMSS>/responses.jsonl`）を作る。
   - `--note` は必ず付ける（後で run 同士を比較するときの文脈になる）。
   - `adapter.type=manual` のアプリでは collect は使えない。ユーザーから回答をもらい、
     `responses.jsonl`（`{"case_id":..., "question":..., "answer":..., "error":null}` の行形式）を
     run ディレクトリに配置してから 3 へ進む。
3. **採点（judge）**: `evalkit.py judge <app> --run latest` — ケースごとにジャッジプロンプトを
   組み立て claude CLI で採点する。
   - claude CLI が使えない環境では `--export-prompts` でプロンプトをファイル出力し、
     セッション内の Claude（Agent の並列サブエージェント）で判定して `judgments.jsonl` に
     `{"case_id":..., "metrics": {"<metric>": {"score":0.0,"reason":"..."}}, "error":null}` を書き込む。
4. **スコア確定**: `evalkit.py score <app> --run latest` — 決定的チェック
   （must_include / must_not_include / max_chars）と judge 結果を統合する。
   決定的チェックの違反は総合スコアに乗算で効く（ハードルール違反は許容しない設計）。
5. **レポート**: `evalkit.py report <app> --run latest` — `report.md` を生成し、
   サマリ（総合 / pass 率 / メトリクス平均）とワーストケースをチャットでも要約提示する。
6. **比較（2 回目以降）**: 改善後の再測定なら `evalkit.py compare <app> --runs <前> <後>` の
   結果も提示する。
7. **締め**: 「このレポートで壁打ちしますか（jocasta-eval-improver）」と一言添えて終了する。

## メトリクス

定義・スコアリング規約は [references/metrics.md](references/metrics.md) を正とする。

| メトリクス | 一言で | 判定者 |
|---|---|---|
| correctness | 内容が事実・理想の要点に照らして正しいか | LLM judge |
| completeness | ideal_points のカバー率 | LLM judge |
| ng_compliance | NG 定義に抵触していないか | LLM judge |
| relevancy | 質問への的中度 | LLM judge |
| faithfulness | 与えられたコンテキストへの忠実性（context のあるケースのみ） | LLM judge |
| 決定的チェック | 必須/禁止キーワード・文字数上限 | スクリプト |

## 品質・安全性（persona: jocasta 準拠）

- スコアは必ず根拠（reason）とセットで提示する。数字だけの報告をしない。
- run は不変。取り直しは新しい run として実施し、古い run を上書き・削除しない。
- http アダプタで外部エンドポイントを初めて叩く前に、接続先 URL をユーザーに確認する。
- ジャッジの揺らぎがあるため、境界ケース（閾値±0.1）はレポートで明示し壁打ち候補として提示する。
- 収集した回答・レポートに機密が含まれる場合はデータディレクトリの外へコピーしない。
