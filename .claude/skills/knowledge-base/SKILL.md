---
name: knowledge-base
description: >-
  worklog が生成した技術整理情報(tech digest)を入力に、技術領域ごとに集約した
  Obsidian 形式のナレッジベース(vault)を生成・更新するスキル。タグ・[[リンク]]入りの
  Markdown ノートを技術別に作る。「ナレッジベース作って」「知見をまとめて」「vault 更新して」
  「技術ノート作って」等で起動する。
---

# knowledge-base — 技術ナレッジベース生成スキル

worklog が縦割り（プロジェクト×日付）で吐き出す `tech` digest を、**技術領域で横串に**
再編成し、Obsidian で使えるタグ・リンク付き Markdown ノート群（vault）を生成する。

> 設計の出典: `ideas/knowledge-base-idea.md`。
> - 一次ソースは `tech` digest（一般化済み・マスキング済みで機密が薄い）。
> - 蓄積場所(vault)と公開場所は分離する。出力は既定で gitignore 配下（別 private リポジトリへ移す前提）。
> - 機密はナレッジに入れない（一般化済み＋ `<REDACTED:..>` を維持）。

## 場所（コードとデータは分離）

- ツール・設定: このスキルディレクトリ `.claude/skills/knowledge-base/`（`bin/` `config/` `templates/`）
- **入力**: worklog の `worklog-data/digests/tech/*.md`（`WORKLOG_DATA` 環境変数で上書き可）
- **出力(vault)**: 既定はリポジトリ直下 `knowledge-base/`。`--out` / `KB_HOME` / `config/kb.yaml` で変更可。
  既定の出力先はリポジトリ直下 `.gitignore` で除外済み。

## トリガーと対応フロー

| ユーザー発話の例 | 実行する標準フロー |
|---|---|
| 「ナレッジベース作って」「知見をまとめて」「vault 作って/更新して」「技術ノート作って」 | 標準フロー（全 tech digest → 技術別ノート + index.md） |
| 「最近のぶんだけ」「6月以降で」 | `--since YYYY-MM-DD` を付ける |
| 「jarvis の知見だけ」 | `--project <id>` を付ける |
| 「分類体系だけ見たい」「どんな技術領域になるか」 | `--taxonomy-only`（ノート生成せず JSON + index のみ） |
| 「動作確認」「お試しで少しだけ」 | `--limit N`（技術ノートを先頭 N 件に制限） |

## 標準フロー（一声でナレッジベースを生成）

```bash
SKILL=/Users/satoshi-onga/Documents/portfolio/jarvis/.claude/skills/knowledge-base
python3 "$SKILL/bin/kb_build.py"
```

- 生成物: `<vault>/index.md`（MOC）＋ `<vault>/tech/<slug>.md`（技術領域ごとの知見ノート）。
  - `_taxonomy.json` … 生成に使った分類体系（再現・index 再生成用）。
- 完了後、vault のパスと生成したノート一覧・要点をユーザーに提示する。
- 2 パス構成（`claude -p` をヘッドレス実行。worklog/summarize.py と同方式）:
  1. **タクソノミー**: 全 digest の要点を 1 回でクラスタリング → 技術領域 JSON。
  2. **ノート生成**: 技術領域ごとに寄与 digest を渡してノート 1 枚を生成。

## オプション

```bash
python3 "$SKILL/bin/kb_build.py" --out ~/obsidian/knowledge   # 出力先を実 vault に
python3 "$SKILL/bin/kb_build.py" --since 2026-06-01           # 指定日以降の digest のみ
python3 "$SKILL/bin/kb_build.py" --project jarvis             # 指定プロジェクトのみ
python3 "$SKILL/bin/kb_build.py" --no-unclassified            # _unclassified を除外
python3 "$SKILL/bin/kb_build.py" --limit 3                    # 技術ノートを先頭3件だけ（確認用）
python3 "$SKILL/bin/kb_build.py" --taxonomy-only              # 分類体系(JSON)+index のみ
python3 "$SKILL/bin/kb_build.py" --dry-run                    # claude を呼ばずプロンプトのみ出力
```

## 注意

- **入力が無いと動かない**: 先に worklog で `tech` digest を生成しておくこと（`summarize.py`）。
- **機密**: digest は collect 段階でマスキング済み。ノート生成プロンプトでも一般化・機密非混入を厳守させている。
  公開派生（ポートフォリオ等）は、この vault からさらにマスキング＋再構成を経た抜粋のみを使う（蓄積≠公開）。
- **claude CLI 必須**: タクソノミー/ノート生成は `claude -p` を使う。無い/失敗時はプロンプトを
  `<vault>/*.prompt.txt` に保存するので、後から手動生成できる。
- **冪等性**: 同じ slug のノートは上書き再生成される。手で追記した内容は失われるため、
  恒久的な加筆は別ファイル（例: `tech/<slug>.notes.md`）に分けることを推奨。
- digest は技術領域ごとに複数ノートへ寄与してよい（横断集約が目的）。
