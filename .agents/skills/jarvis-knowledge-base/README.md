# knowledge-base — 技術ナレッジベース生成

worklog が生成する技術整理情報（`tech` digest）を一次ソースに、**技術領域ごと**に集約した
Obsidian 形式のナレッジベース（vault）を作るスキル。digest はプロジェクト×日付で縦割りだが、
このスキルが技術トピックで横串に再編成し、タグ・`[[リンク]]`入りの Markdown ノートを生成する。

設計の出典は `ideas/knowledge-base-idea.md`。

---

## なぜ必要か

- worklog の digest は「日々の作業」を縦に記録するが、ナレッジとして引くには
  「技術ごと」に横串で集約されている方が圧倒的に使いやすい。
- Markdown ＋ タグ ＋ リンクで貯めておけば、Obsidian の検索・グラフでそのまま再利用でき、
  将来は公開ポートフォリオ素材や RAG のインデックス元にも転用できる（idea フェーズ3）。

## 機密の扱い（設計の前提）

- 一次ソースを `tech` digest にするのは、技術知見が本来「転用できる一般化情報」で機密が薄いから
  （案件固有の文脈・数値は `project` digest 側に寄る）。
- digest は collect 段階でマスキング済み（`<REDACTED:種別>`）。ノート生成プロンプトでも
  「一般化して書く／固有名詞・接続情報を持ち込まない／伏字は復元しない」を厳守させる。
- **蓄積場所(vault)と公開場所は分ける**。公開派生は vault からさらにマスキング＋再構成した抜粋のみ。
  既定の出力先はリポジトリ直下 `.gitignore` 済み（別 private リポジトリへ移す前提）。

---

## ディレクトリ構成（コードとデータは分離）

**コード・設定**（git 追跡）:

```
.claude/skills/jarvis-knowledge-base/
├── SKILL.md                # スキル本体（自然言語トリガー）
├── README.md
├── bin/
│   ├── kb_build.py         # 本体: タクソノミー → ノート生成 → index.md
│   └── kb_lib.py           # 共通ライブラリ（パス解決・claude実行・JSON抽出・依存ゼロ）
├── config/
│   └── kb.yaml             # 出力先・取り込み対象などの設定
└── templates/
    └── tech_note.md        # 技術ノートの出力テンプレート（見出し構成）
```

**生成物(vault)**（git 追跡しない）:

```
<repo>/knowledge-base/       # 既定。KB_HOME / --out / config で変更可
├── index.md                 # MOC（技術別の目次。カテゴリ別に [[リンク]]）
├── tech/<slug>.md           # 技術領域ごとの知見ノート（frontmatter tags / #tag / [[link]]）
└── _taxonomy.json           # 生成に使った分類体系（再現・index 再生成用）
```

> 入力(tech digest)の場所は worklog と同じ規則で解決する: `WORKLOG_DATA` 環境変数 →
> リポジトリ直下 `worklog-data/` → `~/worklog-data` の `digests/tech/`。

---

## 使い方

```bash
SKILL=/Users/satoshi-onga/Documents/onclimb-industries/.claude/skills/jarvis-knowledge-base

# 標準: 初回=全構築 / 2回目以降=増分更新（状態ファイルの有無で自動判定）
python3 "$SKILL/bin/kb_build.py"

# タクソノミーから全再構築（slug 揺れの是正・分類見直し時）
python3 "$SKILL/bin/kb_build.py" --rebuild

# 出力先を実 Obsidian vault にする
python3 "$SKILL/bin/kb_build.py" --out ~/obsidian/knowledge

# 期間・プロジェクトで絞る
python3 "$SKILL/bin/kb_build.py" --since 2026-06-01
python3 "$SKILL/bin/kb_build.py" --project onclimb-industries

# 分類体系(JSON)+index だけ先に見る / 少数だけ試す
python3 "$SKILL/bin/kb_build.py" --taxonomy-only
python3 "$SKILL/bin/kb_build.py" --limit 3

# claude を呼ばずプロンプト・インデックス構築だけ確認
python3 "$SKILL/bin/kb_build.py" --dry-run
```

### 処理モード（状態ファイル `_taxonomy.json` の有無で自動切替）

**初回 = 全構築（2 パス）**

1. **パスA: タクソノミー** — 全 digest の要点インデックスを 1 回の `claude -p` で
   技術領域へクラスタリングし JSON（slug / title / category / sources / related）で受け取る。
2. **パスB: ノート生成** — 技術領域ごとに、寄与する digest の本文を渡して
   `tech_note.md` テンプレート構成の Obsidian ノートを生成（技術数だけ `claude -p`）。
3. **仕上げ** — `index.md`（MOC）を生成し、`_taxonomy.json` に技術領域＋取り込み済み digest（`seen`）を保存。

**2 回目以降 = 増分更新（スケールする）**

worklog が増えるたびに全再生成すると、コストが履歴総量に比例し、ノート入力上限（13 万字）超で
古い知見が切り捨てられる。そこでノート自体を「これまでの全 digest の圧縮メモリ」とみなし、増分だけ畳み込む:

1. **新規 digest のみ分類** — `seen` に無い digest を既存技術領域へ割り当て（必要時のみ新領域提案）。小さな `claude -p` 1 回。
2. **影響ノートだけマージ再生成** — 「既存ノート本文 + 新規 digest」を渡して更新版を生成。
   **新規 digest が付かなかった領域はスキップ（`claude` 呼び出しゼロ）**。古い digest は読み直さない。
3. **状態更新** — `seen` に新規分を加え、`index.md` を再生成。新規 digest が無ければ index 更新のみで即終了。

→ コストは**履歴総量ではなく新規 digest 量に比例**。slug は `_taxonomy.json` で固定され揺れない。

> `--rebuild` は状態を無視して全再クラスタ・全ノート再生成（slug 見直しや分類のやり直し用）。

---

## 設定（config/kb.yaml）

| キー | 既定 | 説明 |
|---|---|---|
| `output_dir` | `knowledge-base` | vault 出力先（相対ならリポジトリ直下基準。絶対可）。`--out`/`KB_HOME` 優先 |
| `note_subdir` | `tech` | 技術ノートを置くサブディレクトリ名 |
| `include_unclassified` | `true` | `_unclassified` の tech digest も取り込むか |

> パーサは `key: value` のスカラのみ対応（ネスト・フロー記法不可、値に `#` 不可）。

---

## 制約・注意

- **入力前提**: 先に worklog で `tech` digest を生成しておくこと（無いと 0 件で終了）。
- **claude CLI 必須**: 無い/失敗時は各プロンプトを `<vault>/*.prompt.txt` に保存し、後で手動生成可能。
  生成出力が frontmatter（`---`）で始まらない場合（`claude -p` がエージェント的に作業報告を返す等）は
  失敗扱いにし、生出力を `<vault>/tech/<slug>.md.raw.txt` に退避して既存ノートを壊さない。
- **状態ファイル `_taxonomy.json`**: 技術領域＋取り込み済み digest（`seen`）を保持。消すと初回相当の全構築に戻る。
- **増分の上書き**: 増分はノートをマージ再生成で上書きする。手書きの恒久メモは別ファイルに分ける。
- **slug 安定性**: 増分では既存 slug を固定。`--rebuild` 時のみ再クラスタで変わりうる（古いノートは残置するので手で掃除）。
- **横断集約**: 1 つの digest は複数の技術ノートに寄与してよい（縦割りを横串へ）。
- **公開は別工程**: この vault は「蓄積」。公開ポートフォリオ等は別途マスキング＋再構成した抜粋を使う。
