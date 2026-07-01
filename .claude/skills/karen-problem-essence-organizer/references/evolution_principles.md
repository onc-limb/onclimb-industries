# 自己進化の原則

「何を / どう改善するか」 を判断するための原則集。`evolve.py` と進化レビュー時の人間判断の両方で参照する。

---

## 原則 1: 頻度と一般性の両方を満たすときだけ改善する

- **頻度 (frequency)**: 直近 N 件 (既定 N=10) のサイクルで、同種の指摘・修正・失敗が **3 回以上** 再発しているか?
  - 1 回限りの逸脱は記憶せず、3 回目以降を改善候補とする (`pipeline.config.json.recurrence_window` で調整)。
- **一般性 (generality)**: その改善は他のプロジェクトでも妥当か?
  - 「特定のリポジトリ名」「特定の API キー名」のような固有名詞しか出てこないなら **保留**。
  - 「テストを必ず TDD で書く」「PR description は Why-Centric にする」のような **再利用可能なルール** に翻訳できるなら **採用候補**。

両方クリアしたものだけ EVOLUTION.md に「提案」として書く。片方しか満たさないものは `references/user_preferences.md` か `logs/notes` に逃がす。

---

## 原則 2: 公的ベストプラクティス優先

ユーザー個別の好みが公的知識と衝突する場合、原則として **公的知識を優先**。
ただし、ユーザーが明示的に「これは私たちの環境固有のルール」と申告したものは `references/user_preferences.md` に分離して両立させる。

### 参照すべき公的知識のリスト (ドメイン別)

#### ソフトウェア工学全般
- *A Philosophy of Software Design* (John Ousterhout) — モジュール深さ、認知負荷
- *The Pragmatic Programmer* — DRY、直交性、トレーサビリティ
- IEEE Std 1016 (SDD)、ISO/IEC/IEEE 24765 (SEVOCAB)

#### 開発手法・プロセス
- *Accelerate* (Forsgren et al.) — 4 つの DORA メトリクス
- *The DevOps Handbook* — 3 つの道 (Flow / Feedback / Continual Learning)
- Trunk-Based Development、Continuous Delivery (Humble & Farley)

#### タスク管理
- GTD (Getting Things Done; David Allen)
- Kanban (David J. Anderson)
- *Personal Kanban*

#### テスト
- *xUnit Test Patterns* (Gerard Meszaros)
- *Working Effectively with Legacy Code* (Michael Feathers)
- Test Pyramid (Mike Cohn)

#### コードレビュー / PR
- Google Engineering Practices ("The Standard of Code Review")
- *What to Look for in a Code Review* (Trisha Gee)

#### プロンプト・LLM 関連 (このスキルが扱うドメイン)
- arXiv: *Reflexion: Language Agents with Verbal Reinforcement Learning* (2303.11366)
- arXiv: *Self-Refine: Iterative Refinement with Self-Feedback* (2303.17651)
- arXiv: *Voyager: An Open-Ended Embodied Agent with Large Language Models* (2305.16291) — 「skill library」概念
- Anthropic: prompt engineering ガイド / skill ベストプラクティス

`evolve.py` は改善候補に対し「上記のどの原則・出典と整合 / 矛盾するか」を 1 行付記することを義務付ける。出典なしの改善は不採用。

---

## 原則 3: ロールバック可能性

進化は常にロールバック可能であること。

- 適用前のスナップショットを `logs/evolutions/<timestamp>/before/` に保存。
- 差分は `logs/evolutions/<timestamp>/diff.patch` で保管。
- 既定は `auto_apply=true`。`SKILL.md` / `references/` / ドメイン固有 `scripts/` は人手承認なしで自動適用する (ユーザーの明示的な指示)。
- 唯一の例外は `scripts/pipeline.py` (および `scripts/evolve.py`)。これらは自己破壊防止のため自動進化の対象外。改変が必要なら `EVOLUTION.md` に提案だけ書き、人手で適用する。

---

## 原則 4: 自分の盲点を疑う

自己進化エージェントは「自分が見たログ」だけで判断するため、サンプルバイアスに陥りやすい。

- 同じ user_turn が極端に多く現れている場合は重み付けを下げる (1 人のヘビーユーザーに過剰適応しない)。
- `unknown` / `error` ばかり溜まっている領域は、ルール改善より「観測を増やす」アクション (assumption_notes をより詳しく書く、ユーザーに確認を増やす) を優先。

---

## 原則 5: スキルは小さく / 明示的に

- SKILL.md が 500 行に近付いたら、新規ルールは references に切り出す。
- 「MUST / NEVER」の濫用は避け、**なぜそのルールが必要か** を必ず添える (Claude のセオリーオブマインドを活かす)。
- 改善提案で「ALWAYS」「NEVER」を多用していたら、原則 4 のバイアス警戒。

---

## 原則 6: ユーザー個別の好みは別レイヤに

`references/user_preferences.md` は「公的ベストプラクティスと衝突するが、このユーザー / このリポジトリでは採用する」ルールを記録する。
SKILL.md 本体には混ぜず、子スキルが利用するときも `user_preferences.md` の参照は明示的に行う (匿名で適用しない)。

---

## 進化レビューのフォーマット (`EVOLUTION.md` への書き出し)

```markdown
## 2026-05-19T12:30:00Z — review #4

### 改善提案 (採用候補)

1. **SKILL.md L42-58**: 「完了条件 `unknown` の判定基準」を具体化
   - 頻度: 直近 10 件中 4 件で `unknown` のまま閉じられている
   - 一般性: 他リポジトリでも妥当 (判定基準の明文化)
   - 出典: `A Philosophy of Software Design` (Definitions of "Done")、Self-Refine 論文

### 保留 (頻度 OK / 一般性 NG)

1. プロジェクト X 特有の命名規則 → `references/user_preferences.md` に追記

### 適用結果

- 採用: 提案 #1
- ロールバック手順: `logs/evolutions/2026-05-19T12-30-00Z/`
```
