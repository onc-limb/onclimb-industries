---
name: griot-explain-coach
description: >-
  説明練習の添削スキル(griot 説明練習パイプラインの Step 3。パイプラインの核)。
  griot-explain-prep で作った説明資料を見ながらユーザーが口頭説明した内容の文字起こしを入力に、
  「どのような相手に説明したか(ペルソナ)」を毎回確認した上で、そのペルソナに伝わるかの観点で
  添削する(結論先出し・構成・聞き手適合・具体性・抜け等)。指摘は固定カテゴリで構造化して
  指摘台帳(review-log.jsonl)に蓄積し、定期的な苦手分析(フロー B)に使う。
  「この説明を添削して」「今日の説明練習の文字起こしを見て」で添削、
  「苦手分析して」「説明練習の振り返りして」で定期分析を起動。
metadata:
  type: skill
  stage: 3
  pairs_with: griot-explain-prep, griot-explain-english
  data_dir: <repo>/explain-practice-data
---

# griot-explain-coach — 説明の添削と苦手分析（Step 3・パイプラインの核）

[griot-explain-prep](../griot-explain-prep/) の資料を見ながらユーザーが行った口頭説明の
文字起こしを、**想定聞き手（ペルソナ）に伝わるか**の観点で添削する。指摘は構造化して蓄積し、
定期的に苦手傾向を分析する。persona は [`personas/griot.md`](../../../personas/griot.md)。

## データ配置

- 入力: `<repo>/explain-practice-data/sessions/<YYYY-MM-DD>-<slug>/`（note.md / deck.html）
  ＋ ユーザーが渡す文字起こしテキスト
- 出力:
  - `sessions/<dir>/transcript.md` — 文字起こしの保全（原文のまま。削除・書き換えしない）
  - `sessions/<dir>/review.md` — 添削レポート（テンプレ: [`templates/review.md`](templates/review.md)）
  - `review-log.jsonl` — 指摘台帳（追記のみ。`scripts/review_log.py` 経由で操作。直接編集しない）
  - `analysis/<YYYY-MM>-review.md` — 定期分析レポート（フロー B）
- 上書き: `EXPLAIN_PRACTICE_DATA_DIR` 環境変数

## トリガー

| ユーザー発話の例 | 動作 |
|---|---|
| 「この説明を添削して」「説明練習の文字起こしを見て」 | フロー A（添削） |
| 「苦手分析して」「説明練習の振り返りして」「今月のまとめ」 | フロー B（定期分析） |

入力は**文字起こしテキスト**（貼り付け or ファイルパス）。音声ファイルの文字起こしは
本スキルの対象外（Plaud・Whisper 等で起こしてから渡してもらう）。

## フロー A: 添削

### 1. 対象セッションとペルソナの確定

- 対象セッションを特定（既定 = 当日。`sessions/` を ls して候補提示）。note.md・deck.html を Read。
- **ペルソナを毎回確認する**: note.md の `audience` を既定として提示し、
  「今回は誰に説明するつもりで話したか」を確認（当日変えていることがあるため。変更可）。
  ペルソナが添削全体の判定基準になるので、前提知識レベルまで具体化する。

### 2. 文字起こしの保全

- 受け取った文字起こしを `transcript.md` に原文のまま保存（先頭に date / persona / 入力元のメタを付ける）。
  フィラーや言い直しも消さない（delivery の添削材料）。

### 3. 添削（★このスキルの核）

「もし自分がこのペルソナだったら、どこで理解が止まるか」を軸に添削する。
persona 原則どおり **良かった点 → 改善点 → 具体的な直し方（言い直し例）** の順、
指摘には必ず文字起こしからの**引用**を付ける。お世辞で水増ししない。

検査観点（= 指摘カテゴリ。台帳記録に使う固定語彙）:

| カテゴリ | 観点 |
|---|---|
| `conclusion-first` | 結論・要点が冒頭に出ているか（最後まで結論が出てこない説明になっていないか） |
| `structure` | 話の順序・まとまり。資料の「話す順番」と実際の説明が噛み合っているか |
| `audience-fit` | ペルソナの前提知識で通じるか（専門用語・略語・文脈の飛躍） |
| `concreteness` | 抽象論で終わっていないか。具体例・数字が口頭でも出たか |
| `logic` | 因果・理由のつながり。「なぜ」が説明されているか |
| `completeness` | note.md にある重要な内容が説明から抜け落ちていないか（★ノートと必ず突き合わせる） |
| `brevity` | 冗長・脱線・同じ話の繰り返し。話量の配分 |
| `clarity` | 一文の長さ・言葉選び・指示語の多用 |
| `delivery` | フィラー・言い直し・文の途中放棄（文字起こしから分かる範囲のみ） |

- 全カテゴリを機械的に埋めない。**その回の説明で実際に問題だった点だけ**指摘する
  （目安: major 1〜3 件 + minor 数件。重要な順）。
- 締めに**改善版の例**（冒頭 30 秒の言い直しモデル等）を 1 つ示す。
- **次回の重点は 1 つだけ**提示する（後述の台帳 stats で直近の頻出カテゴリを確認し、
  「前回も structure だった」のような連続性を踏まえて選ぶ）。

### 4. レポート保存と台帳記録

- 添削結果を `templates/review.md` の書式で `review.md` に保存。
- 指摘（major / minor とも）を台帳に記録する:

```bash
SKILL=/Users/satoshi-onga/Documents/onclimb-industries/.claude/skills/griot-explain-coach
# entries.json: [{"date","session","persona","category","severity","summary","advice"}, ...]
python3 "$SKILL/scripts/review_log.py" add --file /path/to/entries.json
```

- category は上表の固定語彙のみ（スクリプトが検証する）。severity は `major` / `minor`。
- 記録したら**一言通知する**（「指摘 n 件を台帳に記録しました」）。

## フロー B: 定期分析（苦手の可視化）

1. 期間を確認（既定 = 直近 1 ヶ月。「全期間」も可）。
2. 集計はスクリプトで行う（モデルで数えない）:

```bash
python3 "$SKILL/scripts/review_log.py" stats --from 2026-06-01 --to 2026-06-30
python3 "$SKILL/scripts/review_log.py" list --category structure   # 実例の引き出し
```

3. 頻出カテゴリ上位 2〜3 件について、該当セッションの review.md から実例を引用し、
   **傾向（どういう状況でその癖が出るか）**を分析する。件数の列挙で終わらせない。
   前月の分析レポートがあれば比較し、改善したカテゴリも明示する（上達を可視化する）。
4. `analysis/<YYYY-MM>-review.md` に保存し、次の期間の重点（1〜2 個）と
   具体的な練習方法（例: 「最初の 1 文で結論を言ってから背景に入る縛りで 1 週間」）を提案する。

## 注意

- ユーザーが言っていないことを「言った」ことにしない。指摘・分析は必ず transcript の引用に基づく。
- 指摘は説明・構成・表現に向ける。人格への評価はしない（persona 原則）。
- 過去の review.md・台帳エントリは書き換えない（訂正は新しいエントリで）。
- transcript に業務情報が含まれてよい（git 管理外）。review.md にも API キー等の機密は書かない。
- 添削後、英語でも練習したい場合は [griot-explain-english](../griot-explain-english/) を案内する。
