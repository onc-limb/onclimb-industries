# CLAUDE.md

onclimb-industries リポジトリのプロジェクト固有ガイドライン。

## スキル

スキルは `.claude/skills/` 配下に置き、**分類プレフィックス + スキル名**（例: `jarvis-worklog`）で命名する。
プレフィックスと分類の対応は [`.claude/skills/README.md`](.claude/skills/README.md) を参照。

各分類の共通ルール（役割・言語表記・原則・品質/安全性）は [`personas/`](personas/) に
プレフィックスごとの Markdown（`jarvis.md`, `friday.md` など）としてまとめている。

ドキュメント系（friday）のうち自由形式ドキュメント（設計書・提案書・技術記事など）は、
事前準備の `friday-doc-planner`（Stage 0）→ 種類別の生成スキル（Stage 1）の 2 段構成で作る
（詳細は `.claude/skills/README.md` の「friday 系の 2 段構成」。固定パイプライン型の
`friday-giziroku` / `friday-daily-report` は対象外）。

### 新しく Skill を作るとき

1. スキルの分類を決め、対応するプレフィックスを選ぶ（`.claude/skills/README.md` の一覧）。
2. **その分類の persona ファイル（`personas/<prefix>.md`）を必ず参照**し、そこに書かれた
   共通ルールに従って SKILL.md・スクリプト・出力を設計する。
3. ディレクトリ名は `<prefix>-<skill-name>`、`SKILL.md` の `name:` フロントマターも同じ値にする。
4. 新しい分類が必要な場合は、先に `personas/<prefix>.md` を作成して共通ルールを定義し、
   `.claude/skills/README.md` のプレフィックス一覧も更新する。

### スキルのデータ置き場と依存の方向

スキル群は当リポジトリ内で自己完結させ、`projects/` 配下のプロジェクトに依存させない。

- **スキルは `projects/` 内のプロジェクトにデータを保存・参照しない**。スキルのデータは
  当リポジトリ直下の git 管理外ディレクトリ（例: `dividend-data/`, `budget-data/`）に置き、
  `.gitignore` に理由コメント付きで追加する（既存エントリの書式に合わせる）。
- プロジェクト側がスキルのデータを使いたい場合は、**プロジェクト側に取得元パスの設定手段**
  （環境変数・設定ファイル等）を実装し、そこから読み込ませる。
  依存の方向は常に **プロジェクト → 当リポジトリ直下のデータ** の一方向で、逆流させない
  （プロジェクトが無い・壊れている状態でもスキル単体で完結して動くこと）。
- データのスキーマをプロジェクト側の型と揃える場合は、SKILL.md にその対応関係と
  「変更時は両側を同時に変える」旨を明記する。
- 例: `ultron-dividend-recorder` は `dividend-data/records.json` に記録し、
  personal-dashboard 側は環境変数 `DIVIDEND_RECORDS_PATH` でそれを取り込む。

### スキルフィードバックの運用

スキルを使って出た不満・改善点は、中央インボックス [`ideas/skill-feedback.md`](ideas/skill-feedback.md) にためる。

- ユーザーが「スキル改善メモ: 〜」等とフィードバックの記録を指示したら、
  インボックスの記録フォーマットに従って 1 件追記する。
- スキル実行中にユーザーからやり直し・修正指示・手動介入があったら、その作業の区切りで
  **1 回だけ**「フィードバックとして記録するか」を提案する（勝手に書かない。毎回聞かない）。
- 辞書・資産系（glossary / NG ワード / 名簿など）で直るものはインボックスにためず、
  各スキルの自己進化ルートでその場で追記する（対象一覧は skill-feedback.md 冒頭）。
- **SKILL.md・personas の書き換えは 1 件の不満で行わない**。skill-feedback.md のレビュー手順
  （5 件たまったら、または月 1）でまとめて振り分け・適用する。

## ToDo 台帳との突き合わせ

プロジェクト別のタスク台帳を `todo-data/todos.json` で管理している（jarvis-todo-management）。
「ToDo を作らずに作業してしまう」を防ぐため、スキル起動の有無によらず全セッションで次を行う。

- **まとまった作業（スキル実行・実装・調査など）の区切り**で `todo-data/todos.json` を確認し:
  - 対応するタスクがあれば `todo.py start / done` で状態を更新する（事実の記録なので自動。**一言通知する**）。
  - 無ければ `todo.py add --source-type session` で自動追記する（完了済み作業は `--status done`、
    やりかけ・派生は `--status inbox`）。**追記したら毎回一言通知する**。
  - どのタスクの作業か曖昧なときは勝手にマークせず、一言で確認する。
- **調査・壁打ちの区切り**で ToDo になりうる結論が出ていたら「これ ToDo にしますか」と候補を提示し、
  採用分だけ `--status inbox --source-type research` で記録する。
- ユーザーが「あとでやる」「〜しないと」と口にしたタスクは `--status inbox` で自動追記 + 一言通知する。
- 操作は必ず `.claude/skills/jarvis-todo-management/scripts/todo.py` 経由（todos.json を直接編集しない）。
  詳細な手順・原則は同スキルの SKILL.md（フロー C / F）を参照。

## projects ディレクトリ

`projects/` は、調査・作業のために実際のプロジェクトの git リポジトリを配置する作業場。

- `projects/` は `.gitignore` で **git 管理外**とする（当リポジトリでは追跡しない）。
- 各プロジェクトは `projects/<project-name>/` に配置し、その中で作業・ソースコード調査を行う。

### プロジェクト固有情報の分離ルール

- あるプロジェクトに関して生成・整理した情報（ドキュメント・報告書・思考の整理・調査メモなど）は、
  **そのプロジェクト固有のもの**として、当該プロジェクトのディレクトリ配下に保存する。
- 別のプロジェクトを調査・作業するときに、他プロジェクトの固有情報を持ち込んだり混在させたりしない。
  参照・前提・出力は、いま対象としているプロジェクトの範囲に閉じる。
- 複数プロジェクトに共通する知見を残したい場合は、特定プロジェクト配下ではなく、
  当リポジトリ側の適切な場所（スキル・personas・ideas など）に、固有情報を除いた形で切り出して保存する。

### iron-legion（自動実行ワークフロー群）

`projects/iron-legion/` は、人が張り付かなくても自律的に働くワークフローを収容する
private リポジトリ（詳細は同リポジトリの `README.md`）。`projects/` 配下のプロジェクトの
実装・改善作業で頻繁に使うため、以下を把握しておくこと。

- **extremis**（`projects/iron-legion/extremis/`）: 自己改善エンジニアリングループ
  （Elixir/OTP コア + Rust 製書き込み境界 sentinel）。対象プロジェクトの GitHub issue を渡すと
  分解 → 実装 → 検証 → 敵対的レビュー → PR → マージまで自律実行する。
  実行例: `mise exec -- ./extremis/core/extremis -p <project> epic <issue番号>`
- **veronica**（`projects/iron-legion/veronica/`）: マネジメント側ディスカバリーループ（Python）。
  観点カタログで「何をなぜやるべきか」（規約・監視・CI/CD・コスト等）を洗い出し、
  記述 → 敵対的検証 → Web 裏取りを自律実行して、ユーザーの Go/No-Go を経て
  extremis が実行できる GitHub issue を起票する。対象リポジトリへは読み取り専用。
- 役割分担: veronica が「何を・なぜ」を決めて issue 化し、extremis が「どう作るか」を
  自律実装する（veronica → issue → extremis → 顛末 → veronica retro の一方向ループ）。
- 対象プロジェクトは `projects/iron-legion/projects.toml` に一元登録し、
  各ワークフローの `-p/--project` で選択する。

**いつ参照するか:**

- `projects/` 配下のプロジェクトで「GitHub issue を自律実装させたい」「開発ループに投げたい」
  と言われたら → extremis（`extremis/README.md`、自己改善は `extremis/docs/SELF_IMPROVEMENT.md`）。
  jarvis-issue-planner で作った issue を extremis に渡す流れもここに接続する。
- 「このプロダクトに何が必要かを洗い出したい」「Go/No-Go を判断して issue 化したい」
  と言われたら → veronica（`veronica/README.md`）。
- iron-legion に新しいワークフローを追加するときは `projects/iron-legion/README.md` の
  追加規約（自己完結・projects.toml 参照・状態は dot ディレクトリ）に従う。

**注意:** `projects/iron-legion-self/` は extremis の**自己改善専用クローン**
（稼働中のチェックアウトを対象にできないため分離されている）。iron-legion 本体への
通常の作業・修正・参照は必ず `projects/iron-legion/` 側で行い、`iron-legion-self/` を
直接編集しない。また `extremis/sentinel/` は人間のみが変更・ビルドする領域。

## study ディレクトリ（AI がコードを書かない学習用の場）

`study/` は、ユーザーが勉強のために **AI（Claude）に絶対にコードを書かせない** ディレクトリ。

- **`study/` 配下ではコードを一切書かない・編集しない**（新規作成も含む）。ユーザー自身が書く。
- ユーザーからの質問には **言葉での解説・回答のみ** で応じる。方針・ヒント・間違いの指摘は
  日本語の説明で行い、コードそのもの（スニペット含む）は提示しない。
- 技術的担保として、PreToolUse フック `.claude/hooks/block-study-writes.py` が
  `Write`/`Edit`/`MultiEdit`/`NotebookEdit` によるこのディレクトリ配下への書き込みを拒否する。
- `study/` は `.gitignore` で git 管理外。
