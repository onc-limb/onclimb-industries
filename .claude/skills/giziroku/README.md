# giziroku スキル

音声文字起こし（Plaud / Teams 等）から、対話で前提を固めてから社内共有できる議事録を
1 本生成するスキル。設計の出典: [`ideas/giziroku.md`](../../../ideas/giziroku.md)。

## 構成

```
.claude/skills/giziroku/
  SKILL.md              # 起動条件・4 段フロー（エントリポイント）
  scripts/
    parse_transcript.py # Phase A: 話者集計・抜粋・タイムライン・話者なし推定（決定的処理）
  templates/
    meeting.md          # 会議用議事録テンプレ
    agent_call.md       # AI エージェント通話用
    chat.md             # 雑談用
  references/
    dialogue_flow.md    # Phase B の確認 4 点と質問の作法
    extraction.md       # 決定/保留/TODO の判定基準
    masking.md          # マスキング規約（worklog の定義を流用）
  config/
    glossary.example.yaml  # 誤変換辞書の雛形（汎用シード・機密なし・git 追跡）
    roster.example.yaml    # 参加者名簿の雛形（空・git 追跡）
```

データと自己進化資産はリポジトリ直下 `giziroku/`（git 管理外）に置く。`transcripts/`（入力）→
生成成功後に `processed/` へ退避（原文は削除しない）、`minutes/`（出力）、`config/`（誤変換辞書・
参加者名簿の実データ＝蓄積先）。雛形は同梱 `config/*.example.yaml`。
構成は [`giziroku/README.md`](../../../giziroku/README.md) を参照。

## 使い方

ユーザーが文字起こしファイルを指して「議事録にして」等と明示的に依頼したときに起動する
（自動起動しない）。詳細な手順は [SKILL.md](SKILL.md)。

```bash
# Phase A の素材取得（スキルが内部で呼ぶ）
python3 .claude/skills/giziroku/scripts/parse_transcript.py "giziroku/transcripts/xxx-transcript.txt" --json
```

worklog（作業ログ整理）とは別系統。パイプラインを共有しない。
