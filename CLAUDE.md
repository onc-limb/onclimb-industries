# CLAUDE.md

onclimb-industries リポジトリのプロジェクト固有ガイドライン。

## スキル

スキルは `.claude/skills/` 配下に置き、**分類プレフィックス + スキル名**（例: `jarvis-worklog`）で命名する。
プレフィックスと分類の対応は [`.claude/skills/README.md`](.claude/skills/README.md) を参照。

各分類の共通ルール（役割・言語表記・原則・品質/安全性）は [`personas/`](personas/) に
プレフィックスごとの Markdown（`jarvis.md`, `friday.md` など）としてまとめている。

### 新しく Skill を作るとき

1. スキルの分類を決め、対応するプレフィックスを選ぶ（`.claude/skills/README.md` の一覧）。
2. **その分類の persona ファイル（`personas/<prefix>.md`）を必ず参照**し、そこに書かれた
   共通ルールに従って SKILL.md・スクリプト・出力を設計する。
3. ディレクトリ名は `<prefix>-<skill-name>`、`SKILL.md` の `name:` フロントマターも同じ値にする。
4. 新しい分類が必要な場合は、先に `personas/<prefix>.md` を作成して共通ルールを定義し、
   `.claude/skills/README.md` のプレフィックス一覧も更新する。
