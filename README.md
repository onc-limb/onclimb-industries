# onclimb-industries

AI Agent Skills

ドキュメント生成や日々の作業支援を目的とした AI エージェント（Claude Code）のスキル群を管理するリポジトリです。

## ディレクトリ構成

```
.
├── .claude/skills/   # スキル本体（<prefix>-<name> で命名。命名規約は .claude/skills/README.md）
│   ├── jarvis-worklog/                        # 会話・操作ログを収集・分類し整理情報を生成
│   ├── jarvis-knowledge-base/                 # tech digest から Obsidian 形式のナレッジベースを生成
│   ├── jarvis-record/                         # worklog から当日の作業を機械的にまとめた一次記録（案件×対応日）
│   ├── friday-daily-report/                   # 一次記録から依頼者向けの日次報告 HTML スライドを生成
│   ├── friday-giziroku/                       # 文字起こしから共有用の議事録を生成
│   ├── ultron-high-dividend-stock-screener/   # 日本の高配当株を screening し候補リスト化
│   ├── karen-problem-essence-organizer/       # 課題発見〜手段検討の思考整理
│   └── karen-self-evolving-skill-creator/     # 自己進化パイプライン付きスキルの生成
├── personas/         # スキル分類（プレフィックス）ごとの共通ルール
├── projects/         # 調査・作業用に実プロジェクトの git リポジトリを配置（git 管理外）
└── ideas/            # スキルのアイデア・検討中の構想
```

## projects ディレクトリ

実際のプロジェクトの git リポジトリを配置し、その中での作業やソースコード調査を行うための作業場です。

- `.gitignore` で **git 管理外**（当リポジトリでは追跡しない）。中身は各プロジェクト自身のリポジトリで管理する。
- プロジェクト固有の情報（ドキュメント・報告書・思考の整理など）は、そのプロジェクトのディレクトリ配下に
  プロジェクト固有として保存する。詳細な運用ルールは [`CLAUDE.md`](CLAUDE.md) を参照。
