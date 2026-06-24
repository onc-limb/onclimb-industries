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
.claude/skills/knowledge-base/
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
SKILL=/Users/satoshi-onga/Documents/portfolio/jarvis/.claude/skills/knowledge-base

# 全 tech digest からナレッジベースを生成（標準）
python3 "$SKILL/bin/kb_build.py"

# 出力先を実 Obsidian vault にする
python3 "$SKILL/bin/kb_build.py" --out ~/obsidian/knowledge

# 期間・プロジェクトで絞る
python3 "$SKILL/bin/kb_build.py" --since 2026-06-01
python3 "$SKILL/bin/kb_build.py" --project jarvis

# 分類体系(JSON)+index だけ先に見る / 少数だけ試す
python3 "$SKILL/bin/kb_build.py" --taxonomy-only
python3 "$SKILL/bin/kb_build.py" --limit 3

# claude を呼ばずプロンプト・インデックス構築だけ確認
python3 "$SKILL/bin/kb_build.py" --dry-run
```

### 処理の流れ（2 パス）

1. **パスA: タクソノミー** — 全 digest の要点インデックスを 1 回の `claude -p` で
   技術領域へクラスタリングし JSON（slug / title / category / sources / related）で受け取る。
2. **パスB: ノート生成** — 技術領域ごとに、寄与する digest の本文を渡して
   `tech_note.md` テンプレート構成の Obsidian ノートを生成（技術数だけ `claude -p`）。
3. **仕上げ** — タクソノミーから `index.md`（MOC）を生成。

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
- **冪等**: 同 slug ノートは上書き再生成。手書きの加筆は別ファイルに分ける。
- **横断集約**: 1 つの digest は複数の技術ノートに寄与してよい（縦割りを横串へ）。
- **公開は別工程**: この vault は「蓄積」。公開ポートフォリオ等は別途マスキング＋再構成した抜粋を使う。
