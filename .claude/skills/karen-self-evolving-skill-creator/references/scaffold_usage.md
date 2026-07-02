# `scaffold_skill.py` の使い方

新しい自己進化スキルを 1 コマンドで作成する。

## 推奨配置

新規スキルは **`<repo-root>/.claude/skills/<name>/`** に置く。
Claude Code は `.claude/skills/` 配下を自動スキャンするため、ここに置けば再起動後すぐ available skill として認識される。

## 命名規則 (プレフィックス必須)

スキル名は **分類プレフィックス + スキル名** (例: `arc-reactor-pr-reviewer`) とする。
既知プレフィックスは `jarvis` / `friday` / `arc-reactor` / `ultron` / `edith` / `karen` / `vision`。
プレフィックスの選び方は `.claude/skills/README.md`、分類ごとの共通ルールは `personas/<prefix>.md` を参照する。
既知プレフィックスで始まらない名前はエラーになる (例外的に `--allow-no-prefix` で回避可能だが、原則使わない)。

## 基本

```bash
python scripts/scaffold_skill.py \
  --name <prefix>-<kebab-case-skill-name> \
  --dest <repo-root>/.claude/skills \
  --description "<トリガー文を含むスキル説明>"
```

例 (このリポジトリ内で新規スキルを作る場合):

```bash
python scripts/scaffold_skill.py \
  --name arc-reactor-pr-reviewer \
  --dest <repo-root>/.claude/skills \
  --description "PR をレビューし、コメントと評価を返す。自己進化を備える。"
```

生成物:

```
<repo-root>/.claude/skills/arc-reactor-pr-reviewer/
├── SKILL.md
├── pipeline.config.json
├── EVOLUTION.md            # 空 (進化レビューの履歴を追記していく)
├── scripts/
│   └── pipeline.py         # メタスキルから symlink ではなくコピーで配布
├── references/
│   └── user_preferences.md # 空
└── logs/
    ├── pipeline.jsonl      # 空 (touch 済み)
    ├── artifacts/
    └── evolutions/
```

## オプション

| フラグ | 既定 | 説明 |
|---|---|---|
| `--name` | 必須 | スキル名 (kebab-case、既知プレフィックス始まり) |
| `--dest` | 必須 | 親ディレクトリ |
| `--description` | 必須 | description 文字列 (トリガー文と「自己進化を備える」を含めること) |
| `--threshold` | 10 | 進化トリガーのサイクル数しきい値 |
| `--auto-apply` | true | 進化の自動適用 (`--no-auto-apply` で無効化) |
| `--allow-no-prefix` | false | 既知プレフィックスで始まらない名前を許可 (原則使わない) |
| `--force` | false | 既存ディレクトリ上書き |

## 生成後にやること

1. `SKILL.md` の本文をドメインに合わせて書く。**`## 自己進化パイプライン` セクションは削除しないこと**。
2. 必要なら `scripts/` にドメイン固有スクリプトを追加。
3. `evals/evals.json` を作って skill-creator フローで品質を測る (任意)。
4. 動作確認: 1 サイクル分の `log-start` / `log-end` を手動で呼び、`logs/pipeline.jsonl` が更新されることを確認。

## メタスキル本体への適用

このメタスキル自体も同じ構造に従っているため、本体ディレクトリで:

```bash
python scripts/pipeline.py log-start --skill-name karen-self-evolving-skill-creator --instruction "新規スキル作成"
# ... 作業 ...
python scripts/pipeline.py log-end --cycle-id <ID> --completion-state success --completion-reason "..."
```

を毎サイクル呼ぶこと。
