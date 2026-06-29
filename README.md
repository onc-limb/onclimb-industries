# jarvis

AI Agent Skills

ドキュメント生成や日々の作業支援を目的とした AI エージェント（Claude Code）のスキル群を管理するリポジトリです。

## ディレクトリ構成

```
.
├── .claude/skills/   # スキル本体
│   ├── giziroku/                       # 文字起こしから議事録を生成
│   ├── worklog/                        # 会話・操作ログを収集・分類し整理情報を生成
│   ├── knowledge-base/                 # tech digest から Obsidian 形式のナレッジベースを生成
│   ├── report-record/                  # 依頼者向け報告の一次記録（案件×対応日）
│   ├── report-deck/                    # 一次記録から報告用 HTML スライドを生成
│   ├── high-dividend-stock-screener/   # 日本の高配当株を screening し候補リスト化
│   ├── problem-essence-organizer/      # 課題発見〜手段検討の思考整理
│   └── self-evolving-skill-creator/    # 自己進化パイプライン付きスキルの生成
├── friday/
└── ideas/            # スキルのアイデア・検討中の構想
```
