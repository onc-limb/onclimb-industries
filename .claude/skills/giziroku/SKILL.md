---
name: giziroku
description: 音声文字起こし（Plaud / Teams 等）から、社内共有できる議事録を 1 本生成するスキル。ユーザーが文字起こしファイルを指して「議事録にして」「決定事項と TODO を抜いてまとめて」「この transcript を議事録化して」等と明示的に依頼したときだけ起動する（自動起動しない）。対話で参加者・会議種別・公開範囲・目的を確定してから、目的 / 会話の流れ / 全体要約 / 決定事項 / 保留 / TODO を抽出する。会議録音が主だが AI エージェントとの電話・同僚との雑談も同じ流儀で扱う。話者が匿名（Speaker N）でも、話者分離が無いベタ書きでも、対話で確定してから生成する。worklog（作業ログ整理）とは別系統。
metadata:
  type: skill
  data_dir: <repo>/giziroku
---

# giziroku — 議事録生成スキル

Plaud / Teams 等の音声文字起こしファイルを入力に、**対話で前提を固めてから**、
そのまま社内共有できる議事録（目的 / 会話の流れ / 全体要約 / 決定事項 / 保留 / TODO）を
1 本生成する。設計の出典: [`ideas/giziroku.md`](../../../ideas/giziroku.md)。

> **起動条件（重要）**: このスキルは **ユーザーが意図的に起動する**。文字起こしファイルを指して
> 議事録化を依頼されたときだけ走る。ログ収集・作業整理系の [worklog](../worklog/SKILL.md) とは
> **別系統**で、パイプラインを共有しない。「作業ログまとめて」では起動しない。

## 場所（コードとデータは分離）

- ツール・設定: このスキルディレクトリ `.claude/skills/giziroku/`
  （`scripts/` `templates/` `references/` `config/`）
- **入力（文字起こし）**: リポジトリ直下 `giziroku/transcripts/` に置く。ユーザーが他の場所を
  指定した場合はそのパスを使う。
- **出力（議事録）**: リポジトリ直下 `giziroku/minutes/`。**1 ファイル = 1 議事録**。
  ファイル名は `YYYY-MM-DD_<会議タイトル>_議事録.md`。
- **処理済みの入力**: 議事録生成に成功したら、入力ファイルを `giziroku/transcripts/` から
  `giziroku/processed/` へ**移動して退避**する（削除はしない＝原文を残す）。これで
  `transcripts/` には未処理分だけが残り、処理済み/未処理が区別できる。
- `giziroku/` は機密を含みうるため **git 管理外**（`.gitignore` 済み）。
- 自己進化資産（誤変換辞書・参加者名簿）は **2 層**で持つ:
  - 同梱の雛形（git 追跡・機密なし）: `config/glossary.example.yaml` / `config/roster.example.yaml`（汎用シード）
  - 実データ（**git 管理外**・蓄積先）: `giziroku/config/glossary.yaml` / `giziroku/config/roster.yaml`
    （顧客名・人名など機密を含みうるため `giziroku/` 配下に置く。無ければ雛形をコピーして初期化）。
  - 読み込みは雛形＋実データをマージし、**追記（自己進化）は必ず実データ側 `giziroku/config/`** に行う。
  - ★プロジェクト横断で共有・蓄積（使うほど誤変換補正と話者推定が当たるようになる）。

## トリガーと非トリガー

| 起動する発話の例 | 起動しない（誤起動を避ける）|
|---|---|
| 「この文字起こしから議事録作って」 | 「今日の作業まとめて」→ worklog |
| 「`...-transcript.txt` を議事録にして」 | 「技術整理して」→ worklog / knowledge-base |
| 「Plaud の書き起こし、決定事項と TODO 抜いて」 | 「進捗報告して」→ worklog |
| 「エージェントとの電話の文字起こし、要点まとめて」 | （ファイル指定の無い雑な要約依頼）|
| 「雑談ログだけど決まったことだけ拾って」 | |
| 「Teams の文字起こし、参加者だけ確認してから議事録化」 | |

---

## 4 段フロー（この順序は固定。崩さない）

「**対話で前提を固める → 機械的に下処理 → 構造抽出 → 議事録生成**」。
最初の対話を必須にして、匿名話者・誤変換・会議種別の不確実性を入口で潰す。

### Phase A. 一次パース（機械処理）

1. 対象ファイルパスを受け取る（未指定なら `giziroku/transcripts/` の中身を `ls` で提示し選ばせる）。
2. 解析スクリプトを実行して素材（話者集計・抜粋・タイムライン・分離有無）を得る:
   ```bash
   python3 .claude/skills/giziroku/scripts/parse_transcript.py "<transcript_path>" --json
   ```
   - `diarization: labeled` → 話者ラベルあり（`Speaker N` 等）。
   - `diarization: estimated` → 話者分離なし。スクリプトが暫定話者（`推定話者A/B…`）を割った。
     **推定であることを必ず Phase B で確認**する。
3. 各話者の `excerpts`（特徴的発言）と発言量から、役割の当たりを付ける（確定はしない）。
   例: BM 脆弱性診断・CloudFront 設定に言及 → 実装担当らしい。

### Phase B. 対話で前提確定（このスキルの核）★

[`references/dialogue_flow.md`](references/dialogue_flow.md) の確認 4 点を `AskUserQuestion` で確認する。
**確認は 4 点に絞る**（質問過多での離脱を防ぐ）。推定値を初期選択にする。

1. **会議種別**: 会議 / AI エージェントとの電話 / 雑談（出力テンプレを切り替える）。
2. **参加者マッピング**: 話者ごとに「発言量＋抜粋」を提示し、`giziroku/config/roster.yaml` の候補＋自由入力で
   「Speaker 1 はどなた？役割は？」を確認。匿名のままで良い話者は「匿名のまま」を許可。
   話者分離を推定した場合は「この切り分けで合っているか」も併せて確認する。
3. **公開範囲**: internal / external / unknown。**unknown は安全側で external 扱い**（マスキング ON）。
4. **会議の目的**: 文字起こしから推定した目的案を提示し、補正してもらう。

### Phase C. 下処理（機械処理 + 推測痕跡）

1. **誤変換の正規化**: `giziroku/config/glossary.yaml`（無ければ同梱 `config/glossary.example.yaml` をコピーして初期化）と文脈で固有語・専門語を補正する。
   補正は本文に残さず、議事録末尾の「補正メモ」に `元表記 → 補正` で列挙（推測を明示）。
   サンプルの主要誤変換（船だね/フラ種→船種、クラウドフォーメーション→CloudFormation、
   インファレンス→inference 等）が漏れないこと。
2. **マスキング**: 公開範囲が external / unknown なら、実名・顧客名・固有名を `<REDACTED:種別>` 化する。
   種別と規約は [`references/masking.md`](references/masking.md)（worklog の規約を流用）。
3. **話者置換**: 確定した参加者名/役割で `Speaker N` / `推定話者X` を置換する。匿名指定は「匿名」のまま。

### Phase D. 構造抽出と議事録生成

1. [`references/extraction.md`](references/extraction.md) の判定基準で構造を抽出する:
   - 会議の目的 / 全体要約（3〜5 行）/ 会話の流れ（時系列・議題単位、脱線は圧縮）
   - **決定事項**（明示的に合意されたもののみ）/ **保留・継続検討**（決めきれていない論点）
   - **TODO**（担当者・期日付き。不明は `担当: 不明` `期日: 未定` と明示。空欄禁止）
2. 会議種別に応じたテンプレで組み立てる:
   - `meeting` → [`templates/meeting.md`](templates/meeting.md)
   - `agent_call` → [`templates/agent_call.md`](templates/agent_call.md)
   - `chat` → [`templates/chat.md`](templates/chat.md)
3. `giziroku/minutes/YYYY-MM-DD_<会議タイトル>_議事録.md` に **1 ファイル 1 議事録**で書き出す。
   同一会議の分割録音は 1 議事録に束ねる。別会議をまたいだ結合はしない。
4. **完了判定**: 決定事項・TODO が 0 件のときは「抽出失敗」ではなく
   「雑談主体で決定/TODO なし」と判断根拠を添えて明示する（空欄で終わらせない）。
   議事録のメタ欄に**元文字起こしのファイル名**を記録する（後で原文を辿れるように）。
5. **入力の退避**: 議事録の書き出しに成功したら、入力ファイルを退避する（削除しない）:
   ```bash
   mkdir -p giziroku/processed && mv "<transcript_path>" giziroku/processed/
   ```
   - `transcripts/` 以外を直接指定された入力は、ユーザーに退避してよいか一度確認する
     （勝手に他所のファイルを動かさない）。
   - 同名ファイルが `processed/` に既にあれば上書きせず、ファイル名に連番/日付を付ける。
6. 出力後、チャットに要約（参加者・決定数・TODO 数・出力パス・退避先）を返す。

---

## 自己進化（実行ごとに資産が育つ）

固定する芯は崩さない（起動条件・4 段フロー・決定/保留/TODO の分離）。蓄積するのは資産:

- ユーザーが確定した参加者マッピング → `giziroku/config/roster.yaml` に追記（横断共有、次回の候補に使う）。
- ユーザーが訂正した誤変換 → `giziroku/config/glossary.yaml` に追記（横断共有、補正精度が上がる）。
- どの確認質問が毎回不要だったかは、運用しながら Phase B の初期推定を強める材料にする。

実データ（`giziroku/config/`）は固有名（機密）を含みうるため **git 管理外**で運用する。
同梱の `config/*.example.yaml` は汎用シードのみ（機密なし）で git 追跡してよい。

## やってはいけないこと

- 自動起動しない。明示依頼が無ければ走らない。
- Phase B を飛ばして生成しない。`Speaker N` / `推定話者X` を出力に残さない（匿名指定を除く）。
- 誤変換を本文で勝手に直しっぱなしにしない（必ず補正メモに `元 → 補正` を残す）。
- 公開範囲 unknown のままマスキングを省かない（安全側で external 扱い）。
- 決定と「言いさし・アイデア」を混同しない（合意のみ決定、仮は保留へ）。
