# CLAUDE.md

onclimb-industries リポジトリのプロジェクト固有ガイドライン。

## モデル / effort のタスク別ルーティング

タスクの種類ごとに使うモデルと effort を `.claude/agents/` に定義してある。
**ユーザーが毎回 `/model` や `/effort` を打たなくて済むよう、下表に当てはまる作業は
該当エージェントに委譲すること**（これは常時有効な委譲指示であり、その都度の依頼を待たない）。

| 作業の種類 | エージェント | model / effort |
|---|---|---|
| 機械的な軽作業（件数を数える・ログ抽出・定型フォーマット・単純置換） | `quick` | haiku / low |
| 調査（どこに何があるか・実装の把握・影響範囲・外部情報の下調べ） | `research` | sonnet / medium |
| レビューと難所（コード/設計レビュー・原因不明のバグ究明・性能/セキュリティ検討） | `review` | opus / xhigh |
| 文章作成（ドキュメント・報告書・記事の草案、文章整形） | `writer` | sonnet / medium |

**委譲しないもの**（メインの会話で、セッション既定のモデルのまま進める）:

- 実装・修正そのもの（対話しながら進める作業。委譲すると手戻りが増える）
- ユーザーへのヒアリングが要る作業（要件確認・壁打ち・方針の相談）
- 数ファイルを読めば済む単発の確認（委譲のオーバーヘッドの方が大きい）

判断に迷う規模なら委譲せずメインで進めてよい。逆に、レビュー・調査を頼まれたのに
メインで抱え込むのは避ける（そのために定義してある）。

**セッション全体を特定のモデルで動かしたいとき**は委譲ではなく起動時に指定する:
`claude --agent review` のように起動すると、メインスレッド自体がその model / effort になる。

定義を増やす・しきい値を変えるときは `.claude/agents/*.md` の frontmatter
（`model`: sonnet/opus/haiku/fable/フルID/inherit、`effort`: low/medium/high/xhigh/max）を編集する。

### スキル側の指定

`.claude/skills/*/SKILL.md` の frontmatter も `model` と `effort` を持てる（全スキルに設定済み）。
`/<skill-name>` で起動した時点でそのモデル・effort に切り替わるので、スキルとして
確立した作業についてはエージェント委譲より**こちらが優先経路**。

| 用途 | model / effort | 例 |
|---|---|---|
| 設計・レビュー・監査・計画 | opus / high | arc-reactor 系のレビュー/設計、jarvis-issue-planner |
| 調査・生成・記録の主力 | sonnet / medium | jarvis-worklog、friday 系、edith 系 |
| 定型の記録・台帳操作 | sonnet / low | jarvis-todo-management |

スキルの `effort` は `low` / `medium` / `high` / `max`（または整数）。`xhigh` はエージェント側のみ。

**新しいスキルを作るときは frontmatter に `model` と `effort` を必ず書く**（上表の基準に合わせる）。

### スキル一覧の予算（description が Claude に届くための設定）

Claude に渡されるスキル一覧には文字数予算があり（`skillListingBudgetFraction`、既定は
コンテキストウィンドウの 1%）、超過分は `- <name>` だけになって **description が落ちる**。
description は「いつこのスキルを使うか」の判断材料なので、落ちたスキルは自動起動されなくなる。
落とす順番は使用頻度スコア（`usageCount × 0.5^(経過日数/7)`）が低い順で、使ったことのない
スキルから消える。当リポジトリは 39 スキル・description 合計 約12,500 字。既定 1%
（200k コンテキストで 8,000 字）では収まらないため、`.claude/settings.json` で 5% に上げてある。

**description の書き方**（全スキルこの形に統一済み。目安 200〜350 字）:

1. 何をするスキルか（1〜2 文。入力と出力、守るべき原則があれば 1 つだけ）
2. 起動トリガーの発話例を 3〜4 個（「〜して」の形。多くしすぎない）
3. 紛らわしい他スキルとの棲み分けを 1 文（「〜は ◯◯ の領分」）

処理手順・保存先パス・スクリプト名・内部フローは書かない（SKILL.md 本文の領分）。
長くなるほど他のスキルの description を押し出して、そちらが起動しなくなる。

`description:` の値は必ず `>-` の折り畳みブロックにする。半角 `: ` を含むと YAML が壊れて
frontmatter ごと読めなくなり、`#` を含むとそこ以降がコメント扱いで切り捨てられる（どちらも
実際に起きて、description が届いていなかった）。

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
4. frontmatter に `model` と `effort` を書く（基準は「モデル / effort のタスク別ルーティング」）。
5. 新しい分類が必要な場合は、先に `personas/<prefix>.md` を作成して共通ルールを定義し、
   `.claude/skills/README.md` のプレフィックス一覧も更新する。

### スキルのデータ置き場と依存の方向

スキル群は当リポジトリ内で自己完結させ、`projects/` 配下のプロジェクトに依存させない。

- **スキルは `projects/` 内のプロジェクトにデータを保存・参照しない**。スキルのデータは
  当リポジトリ直下の git 管理外ディレクトリ（例: `worklog-data/`, `todo-data/`）に置き、
  `.gitignore` に理由コメント付きで追加する（既存エントリの書式に合わせる）。
- プロジェクト側がスキルのデータを使いたい場合は、**プロジェクト側に取得元パスの設定手段**
  （環境変数・設定ファイル等）を実装し、そこから読み込ませる。
  依存の方向は常に **プロジェクト → 当リポジトリ直下のデータ** の一方向で、逆流させない
  （プロジェクトが無い・壊れている状態でもスキル単体で完結して動くこと）。
- データのスキーマをプロジェクト側の型と揃える場合は、SKILL.md にその対応関係と
  「変更時は両側を同時に変える」旨を明記する。
- 例: `jarvis-todo-management` は `todo-data/todos.json` に記録し、外部から使う場合は
  環境変数 `TODO_DATA` で取得元を指定して取り込む。

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

## ドメイン別知識ディレクトリ（ベストプラクティス）

開発のベストプラクティス・設計知識は、リポジトリ直下のドメイン別ディレクトリに
git 管理で蓄積する（旧 my-best-practices リポジトリを統合したもの）。

- `architecture/` — 設計原則・コードスメル・結合/依存のヒューリスティック
  （arc-reactor-architecture-review の知識正本）
- `frameworks/<fw>/` — フレームワーク別のコーディング規約・設計パターン（nextjs / solidjs-tanstack）
- `testing/` — テスト戦略（pyramid / trophy）
- `security/` — セキュリティチェックリスト
- `code-review/` — レビュー観点チェックリスト
- `git-workflow/` / `dev-environment/` — Git 運用・開発環境構築の標準
- `templates/` — ADR・コーディング規約・テスト方針等のプロジェクト初期化テンプレート

スキルはこれらの知識ディレクトリを自由に参照してよい（例: arc-reactor-architecture-review は
`perspectives/<観点>/INDEX.md` で「どのファイルを読むか」だけをスキル内に持ち、知識の実体は
`architecture/` 等を正本とする）。知識の追記は該当ドメインへ 1 テーマ 1 ファイルが基本で、
スキル経由（フロー B）でも直接編集でもよい。`projects/` 配下のプロジェクトから参照する場合も、
依存の方向は「プロジェクト → 当リポジトリの知識」の一方向とする。

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
