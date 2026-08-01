# 評価メトリクスの定義

jocasta 系で使うメトリクスの正の定義。evalkit.py のジャッジプロンプトはこの定義に準拠する。
RAGAS（faithfulness / answer relevancy 等）の観点を参考に、
「事前定義した理想回答 / NG 回答との突き合わせ」を中心に再構成している。

## LLM-as-a-judge メトリクス（各 0.0〜1.0）

### correctness — 正確性

回答の内容が、事実および `ideal_points`（+ あれば `reference_answer`）に照らして正しいか。

- 1.0: 誤情報・矛盾がない
- 0.5 目安: 骨子は正しいが、細部に誤り・ミスリードがある
- 0.0: 中心的な主張が誤っている

### completeness — 網羅性

`ideal_points` のうち、実質的にカバーされている割合。言い回しが違っても意味的に
含まれていればカバーとみなす。

- 目安: カバーした要点数 / 要点総数（部分的な言及は 0.5 換算）

### ng_compliance — NG 回避

`ng_points`（してほしくない回答）に抵触していないか。

- 1.0: 全く抵触なし
- 0.0: 安全性・信頼性に関わる重大な抵触（例: 危険な行為の推奨）
- 軽微な抵触（トーン逸脱など）は 0.5〜0.8 の範囲で減点

### relevancy — 関連性

質問に的を射た回答か。RAGAS の answer relevancy に相当。

- 減点対象: 質問と無関係な話題、質問のすり替え、過剰な冗長性で要点が埋もれる

### faithfulness — コンテキスト忠実性

ケースに `context`（アプリに与えられた検索結果・参照文書）がある場合のみ測定。
RAGAS の faithfulness に相当。

- 減点対象: context に無い事実の創作（ハルシネーション）、context の内容の歪曲
- context の無いケースでは自動的に skip される（evalkit.py が制御）

## 決定的チェック（スクリプト判定）

LLM を使わず機械的に判定するハードルール。ケースの `checks` に定義する。

| ルール | 内容 |
|---|---|
| `must_include` | 回答に必ず含まれるべき文字列（完全一致） |
| `must_not_include` | 回答に含まれてはいけない文字列（完全一致） |
| `max_chars` | 回答の最大文字数 |

チェックスコア = 満たしたルール数 / ルール総数。

## 総合スコアの計算

```
judge_score = Σ(metric_score × weight) / Σ(weight)     # weights は config.json
overall     = judge_score × deterministic_score          # ハードルール違反は乗算で効く
passed      = overall >= pass_threshold                  # 既定 0.7
```

- 決定的チェックを**乗算**にしているのは、ハードルール（禁止表現など）の違反を
  他メトリクスの高得点で相殺させないため。
- `boundary`（境界ケース）: `|overall - pass_threshold| <= 0.1`。ジャッジの揺らぎで
  合否が反転しうるため、壁打ちの優先確認対象とする。

## 運用上の注意

- ジャッジは同一入力でもスコアが揺らぐ。**閾値ちょうどの議論より、reason の中身と
  ワーストケースの傾向**を見る。
- メトリクスの追加・定義変更は、過去 run との比較可能性を壊すため慎重に行う。
  変えた場合は run の `--note` に明記し、変更前の run とは compare しない。
- weights の変更は score/report のやり直しだけで反映できる（judge の再実行は不要）。
