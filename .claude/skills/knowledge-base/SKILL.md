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
| 「ナレッジベース作って」「知見をまとめて」「vault 作って/更新して」「技術ノート作って」 | 標準フロー（初回=全構築 / 2回目以降=増分更新） |
| 「最初から作り直して」「全部再生成」 | `--rebuild`（タクソノミーから全再構築） |
| 「最近のぶんだけ」「6月以降で」 | `--since YYYY-MM-DD` を付ける |
| 「onclimb-industries の知見だけ」 | `--project <id>` を付ける |
| 「分類体系だけ見たい」「どんな技術領域になるか」 | `--taxonomy-only`（ノート生成せず JSON + index のみ） |
| 「動作確認」「お試しで少しだけ」 | `--limit N`（技術ノートを先頭 N 件に制限） |

## 標準フロー（一声でナレッジベースを生成・更新）

```bash
SKILL=/Users/satoshi-onga/Documents/onclimb-industries/.claude/skills/knowledge-base
python3 "$SKILL/bin/kb_build.py"
```

`_taxonomy.json`（状態ファイル）の有無で自動的にモードが切り替わる:

- **初回（状態なし）= 全構築（2 パス）**。`claude -p` をヘッドレス実行（worklog/summarize.py と同方式）:
  1. **タクソノミー**: 全 digest の要点を 1 回でクラスタリング → 技術領域 JSON。
  2. **ノート生成**: 技術領域ごとに寄与 digest を渡してノート 1 枚を生成。
- **2 回目以降（状態あり）= 増分更新**。worklog が増えても全再生成せずスケールする:
  1. **新規 digest のみ分類**（既存領域へ割り当て／必要時のみ新領域提案）。
  2. **影響を受けたノートだけ**「既存ノート + 新規 digest」でマージ再生成。**変化の無い領域はスキップ（LLM 呼び出しゼロ）**。
  3. 新規 digest が無ければ index 更新のみで即終了（claude を一切呼ばない）。

> なぜ増分か: 全 digest 再生成はコストが履歴総量に比例し、ノート入力上限（13万字）超で古い知見が切り捨てられる。
> ノート自体を「これまでの全 digest の圧縮メモリ」とみなし、**新規分だけ**をマージするのでコストは新規量に比例する。

- 生成物: `<vault>/index.md`（MOC）＋ `<vault>/tech/<slug>.md`（技術領域ごとの知見ノート）。
  - `_taxonomy.json` … 技術領域 + 取り込み済み digest（`seen`）を保持する**状態ファイル**。増分更新の土台。
- 完了後、vault のパスと更新/新規/スキップ件数・要点をユーザーに提示する。

## オプション

```bash
python3 "$SKILL/bin/kb_build.py"                              # 標準: 初回=全構築 / 以降=増分更新
python3 "$SKILL/bin/kb_build.py" --rebuild                    # タクソノミーから全再構築（slug 揺れの是正等）
python3 "$SKILL/bin/kb_build.py" --out ~/obsidian/knowledge   # 出力先を実 vault に
python3 "$SKILL/bin/kb_build.py" --since 2026-06-01           # 指定日以降の digest のみ
python3 "$SKILL/bin/kb_build.py" --project onclimb-industries             # 指定プロジェクトのみ
python3 "$SKILL/bin/kb_build.py" --no-unclassified            # _unclassified を除外
python3 "$SKILL/bin/kb_build.py" --limit 3                    # 技術ノートを先頭3件だけ（確認用）
python3 "$SKILL/bin/kb_build.py" --taxonomy-only              # 分類体系(JSON)+index のみ（全再クラスタ）
python3 "$SKILL/bin/kb_build.py" --dry-run                    # claude を呼ばずプロンプトのみ出力
```

## 注意

- **入力が無いと動かない**: 先に worklog で `tech` digest を生成しておくこと（`summarize.py`）。
- **機密**: digest は collect 段階でマスキング済み。ノート生成プロンプトでも一般化・機密非混入を厳守させている。
  公開派生（ポートフォリオ等）は、この vault からさらにマスキング＋再構成を経た抜粋のみを使う（蓄積≠公開）。
- **claude CLI 必須**: タクソノミー/ノート生成は `claude -p` を使う。無い/失敗時はプロンプトを
  `<vault>/*.prompt.txt` に保存するので、後から手動生成できる。
- **増分とノート上書き**: 増分更新は該当ノートを「既存ノート + 新規 digest」でマージ再生成し**上書き**する。
  手で追記した内容は失われるため、恒久的な加筆は別ファイル（例: `tech/<slug>.notes.md`）に分けることを推奨。
- **slug は状態ファイルで固定**: 増分では既存 slug を再利用するので揺れない。`--rebuild` 時のみ再クラスタで
  slug が変わりうる（その場合は古い `tech/*.md` が残置するので、必要なら手で掃除する）。
- **状態ファイルを消すと全構築に戻る**: `_taxonomy.json` を削除 or `--rebuild` で初回相当の全再構築。
- digest は技術領域ごとに複数ノートへ寄与してよい（横断集約が目的）。
