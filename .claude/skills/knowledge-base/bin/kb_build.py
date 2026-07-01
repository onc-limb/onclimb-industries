#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kb_build: worklog の tech digest を入力に、技術領域ごとの Obsidian ノート群
（タグ・[[リンク]]入り Markdown）からなるナレッジベース(vault)を生成する。

設計（ideas/knowledge-base-idea.md 準拠）:
  - 一次ソースは tech digest（一般化済み・マスキング済みで機密が薄い）。
  - digest はプロジェクト×日付で縦割りなので、横串（技術領域ごと）に再編成する。
  - 蓄積場所(vault)と公開場所は分離。出力先は --out / KB_HOME / config で差し替え可、
    既定はリポジトリ直下 knowledge-base/（.gitignore 済み。別 private リポジトリへ移す前提）。

2 パス構成（worklog/summarize.py と同じく claude -p をヘッドレス実行）:
  パスA タクソノミー: 全 digest の要点インデックスを 1 回の claude 呼び出しで
                      技術領域へクラスタリングし JSON で受け取る。
  パスB ノート生成  : 技術領域ごとに、寄与する digest の本文を渡して
                      Obsidian ノート 1 枚を生成する（技術数だけ呼ぶ）。
  仕上げ: タクソノミーから index.md（MOC: Map of Content）を生成する。

使い方:
  bin/kb_build.py                         # 全 tech digest からナレッジベースを生成
  bin/kb_build.py --out ~/vault           # 出力先を指定
  bin/kb_build.py --since 2026-06-01       # 指定日以降の digest のみ対象
  bin/kb_build.py --project onclimb-industries         # 指定プロジェクトの digest のみ対象
  bin/kb_build.py --limit 3                # 生成する技術ノートを先頭 N 件に制限（動作確認用）
  bin/kb_build.py --dry-run                # claude を呼ばずプロンプト/インデックスのみ出力
  bin/kb_build.py --taxonomy-only          # タクソノミー(JSON)生成まで（ノートは作らない）
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kb_lib as K  # noqa: E402

MAX_INDEX_CHARS_PER_DIGEST = 1400   # タクソノミー入力: digest 1 件あたりの要約上限
MAX_NOTE_SOURCE_CHARS = 130000      # ノート生成入力: 寄与 digest 本文の合計上限
TAXONOMY_TIMEOUT = 600
NOTE_TIMEOUT = 600


# ---------------------------------------------------------------------------
# digest の読み込みと要点抽出
# ---------------------------------------------------------------------------

def split_id(name):
    """'onclimb-industries_2026-06-23' -> ('onclimb-industries', '2026-06-23')。日付が無ければ date=''。"""
    m = re.match(r"^(.+)_(\d{4}-\d{2}-\d{2})$", name)
    if m:
        return m.group(1), m.group(2)
    return name, ""


def section(text, header):
    """'## header' 直下〜次の '## ' 直前までの本文を返す。無ければ ''。"""
    lines = text.splitlines()
    out, capture = [], False
    for ln in lines:
        if ln.startswith("## "):
            if capture:
                break
            capture = (ln[3:].strip().startswith(header))
            continue
        if capture:
            out.append(ln)
    return "\n".join(out).strip()


def subsection_titles(block):
    return [ln[4:].strip() for ln in block.splitlines() if ln.startswith("### ")]


def load_digest(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    name = os.path.basename(path)[:-3]  # strip .md
    pid, date = split_id(name)
    return {"id": name, "pid": pid, "date": date, "text": text, "path": path}


def digest_index_entry(d):
    """タクソノミー用の compact なインデックス文字列。"""
    text = d["text"]
    tldr = section(text, "TL;DR")
    learn = section(text, "技術的な学び")
    skills = section(text, "スキル証跡")
    parts = ["[%s] (project=%s, date=%s)" % (d["id"], d["pid"], d["date"])]
    if tldr:
        parts.append("TL;DR: " + " / ".join(l.lstrip("- ").strip()
                                             for l in tldr.splitlines() if l.strip())[:400])
    titles = subsection_titles(learn)
    if titles:
        parts.append("学び: " + "; ".join(titles))
    if skills:
        # 「使った技術/スキル」「検索用キーワード/タグ」行を優先的に拾う
        keep = [l.strip("- ").strip() for l in skills.splitlines()
                if ("技術" in l or "タグ" in l or "キーワード" in l or "スキル" in l) and l.strip()]
        if keep:
            parts.append("技術/タグ: " + " | ".join(keep))
    entry = "\n".join(parts)
    return entry[:MAX_INDEX_CHARS_PER_DIGEST]


# ---------------------------------------------------------------------------
# プロンプト構築
# ---------------------------------------------------------------------------

TAXONOMY_PROMPT = """\
あなたは SES エンジニアの技術ナレッジを体系化するアシスタントです。
以下は、日々の作業ログから生成された「技術整理情報(digest)」の要点インデックス一覧です。
各 digest はプロジェクト×日付で縦割りになっています。これを **技術領域(トピック)** で
横串に再編成するためのタクソノミー(分類体系)を作ってください。

# やること
- 全 digest を俯瞰し、共通する技術領域・トピックでまとめる。
- 1 つの技術領域には複数の digest が寄与してよい(横断的に集約するのが目的)。
- 粒度は「後でナレッジとして引きやすい」単位。細かすぎず粗すぎず、目安 5〜20 領域。
- 各領域に、寄与する digest の id(提示した [..] の中身)を列挙する。実在する id だけを使う。
- 顧客名・固有名詞は領域名に含めない(既に <REDACTED:..> のものはそのまま)。

# 出力(厳守)
- **JSON のみ**を出力。前置き・後書き・コードフェンス・説明文は一切書かない。
- スキーマ:
{{
  "technologies": [
    {{
      "slug": "kebab-case-ascii",          // ファイル名になる。英小文字/数字/ハイフンのみ
      "title": "日本語可の表示名",
      "category": "language|framework|tool|infra|concept|practice",
      "sources": ["<digest id>", ...],     // 提示した id のみ。最低1件
      "related": ["<別の slug>", ...]       // 関連する技術領域の slug(任意・無ければ空配列)
    }}
  ]
}}

# digest 要点インデックス一覧
{index}
"""

NOTE_PROMPT = """\
あなたは作業ログ由来の「技術整理情報(digest)」を、技術ナレッジの Markdown ドキュメントへ
統合するアシスタントです。

# 最重要（厳守・これを破ると出力は無効）
- あなたの応答テキストは、そのまま 1 つの Markdown ファイルとして保存される。
- よって応答には **Markdown ドキュメント本体のみ** を出力する。
- 前置き・後書き・要約・「書き出しました」等の作業報告・コードフェンス囲み・チャット的説明を一切書かない。
- ファイル書き込みやツール実行はしない。あなたが出力したテキストがそのままノートの中身になる。
- 出力は必ず frontmatter（先頭行が `---`）から始め、テンプレート末尾まで本体だけを書く。

# タスク
以下の digest 群を、指定された技術領域の観点で 1 枚のノートに統合する。
digest はプロジェクト×日付で縦割りなので、同じ技術の知見を横断的にまとめる。

# 対象の技術領域
- タイトル: {title}
- 識別子(slug, タグに使う): {slug}
- カテゴリ: {category}
- 関連技術 slug（本文の [[..]] リンクに使う。これ以外のリンクは作らない）: {related}
- 寄与プロジェクト（frontmatter の project/<id> タグに使う）: {projects}

# 内容の厳守事項
1. 指定テンプレートと同じ見出し構成にする。該当が無い項目は「記録なし」と明記し、見出しは省略しない。
2. frontmatter の tags に最低限: `knowledge-base` / `tech/{slug}` / 寄与プロジェクトごとに `project/<id>`。
   内容に応じて `課題種別/<種別>`（例: 課題種別/トラブルシュート, 課題種別/設計判断）も付与してよい。
3. 関連技術へのリンクは上記 related の slug のみ `[[<slug>]]` で張る。無ければ「関連技術: なし」。
   文中の重要キーワードや課題種別は `#tag` でも付与してよい。
4. 各知見の末尾に出典を `出典: <project> / <date>` と明記する（複数可）。
5. **一般化して書く**。固有名詞・接続情報・顧客特定情報は持ち込まない。
   既に <REDACTED:種別> のものはそのまま伏字で残し復元しない。機密はナレッジに入れない。
6. 元の digest に無い内容を捏造しない。複数 digest で重複する知見は統合し、矛盾は併記する。

# 出力テンプレート（この見出し構成で書く。() 内は書き方の指示なので最終出力では実内容へ置換する）
{template}

# 入力: この技術領域に寄与する digest 群
{sources}
"""


def build_taxonomy_prompt(digests):
    index = "\n\n".join(digest_index_entry(d) for d in digests)
    return TAXONOMY_PROMPT.format(index=index)


def build_note_prompt(tech, source_digests, template):
    projects = sorted(set(d["pid"] for d in source_digests))
    blocks, total = [], 0
    for d in source_digests:
        block = "===== digest: %s (project=%s, date=%s) =====\n%s" % (
            d["id"], d["pid"], d["date"], d["text"])
        if total + len(block) > MAX_NOTE_SOURCE_CHARS:
            blocks.append("…(入力が長いため以降の digest を省略)")
            break
        blocks.append(block)
        total += len(block)
    return NOTE_PROMPT.format(
        title=tech.get("title") or tech["slug"],
        slug=tech["slug"],
        category=tech.get("category") or "concept",
        related=", ".join(tech.get("related") or []) or "(なし)",
        projects=", ".join(projects) or "(なし)",
        template=template,
        sources="\n\n".join(blocks),
    )


# ---------------------------------------------------------------------------
# タクソノミー正規化
# ---------------------------------------------------------------------------

def normalize_taxonomy(raw, valid_ids):
    techs = []
    seen_slugs = set()
    items = raw.get("technologies") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return techs
    for i, t in enumerate(items):
        if not isinstance(t, dict):
            continue
        slug = K.slugify(t.get("slug") or t.get("title") or "", fallback="tech-%d" % (i + 1))
        base = slug
        n = 2
        while slug in seen_slugs:
            slug = "%s-%d" % (base, n)
            n += 1
        seen_slugs.add(slug)
        sources = [s for s in (t.get("sources") or []) if s in valid_ids]
        if not sources:
            continue  # 実在 digest に紐づかない領域は捨てる
        techs.append({
            "slug": slug,
            "title": (t.get("title") or slug).strip(),
            "category": (t.get("category") or "concept").strip(),
            "sources": sources,
            "related": [K.slugify(r) for r in (t.get("related") or []) if r],
        })
    return techs


# ---------------------------------------------------------------------------
# index.md(MOC)
# ---------------------------------------------------------------------------

CATEGORY_LABEL = {
    "language": "言語", "framework": "フレームワーク", "tool": "ツール",
    "infra": "インフラ", "concept": "概念", "practice": "プラクティス",
}


def write_index(home, note_subdir, techs, updated):
    by_cat = {}
    for t in techs:
        by_cat.setdefault(t.get("category") or "concept", []).append(t)
    lines = [
        "---",
        "title: ナレッジベース 目次",
        "tags:",
        "  - knowledge-base",
        "  - moc",
        "updated: %s" % updated,
        "---",
        "",
        "# ナレッジベース（技術別）",
        "",
        "> worklog の技術整理情報(tech digest)から、技術領域ごとに集約した知見ノートの目次。",
        "> 各ノートは Obsidian のタグ・リンクで横断検索できる。",
        "",
        "技術領域数: %d" % len(techs),
        "",
    ]
    for cat in ["language", "framework", "tool", "infra", "concept", "practice"]:
        items = by_cat.get(cat)
        if not items:
            continue
        lines.append("## %s" % CATEGORY_LABEL.get(cat, cat))
        for t in sorted(items, key=lambda x: x["slug"]):
            srcs = ", ".join(sorted(set(split_id(s)[0] for s in t["sources"])))
            lines.append("- [[%s/%s|%s]] — %s（出典: %s）"
                         % (note_subdir, t["slug"], t["title"], t["category"], srcs))
        lines.append("")
    # 既知カテゴリ外
    other = [c for c in by_cat if c not in CATEGORY_LABEL]
    for cat in other:
        lines.append("## %s" % cat)
        for t in sorted(by_cat[cat], key=lambda x: x["slug"]):
            lines.append("- [[%s/%s|%s]]" % (note_subdir, t["slug"], t["title"]))
        lines.append("")
    path = os.path.join(home, "index.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


# ---------------------------------------------------------------------------
# 状態（_taxonomy.json）: 技術領域 + 取り込み済み digest（増分更新の土台）
# ---------------------------------------------------------------------------

STATE_FILE = "_taxonomy.json"


def state_path(home):
    return os.path.join(home, STATE_FILE)


def save_state(home, techs, seen, updated):
    import json as _json
    data = {"technologies": techs, "seen": sorted(seen), "updated": updated}
    with open(state_path(home), "w", encoding="utf-8") as f:
        _json.dump(data, f, ensure_ascii=False, indent=2)


def load_state(home):
    """既存の状態を読む。無効/不在なら None。"""
    import json as _json
    p = state_path(home)
    if not os.path.exists(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = _json.load(f)
    except Exception:
        return None
    techs = data.get("technologies")
    if not isinstance(techs, list) or not techs:
        return None
    # フィールド整形
    for t in techs:
        t["sources"] = list(t.get("sources") or [])
        t["related"] = list(t.get("related") or [])
        t.setdefault("category", "concept")
        t.setdefault("title", t.get("slug", ""))
    seen = data.get("seen")
    if not seen:
        # 旧フォーマット（seen 無し）からの移行: 既存ノートの sources を取り込み済みとみなす
        seen = sorted({s for t in techs for s in t["sources"]})
    data["seen"] = seen
    return data


# ---------------------------------------------------------------------------
# 増分更新: 新規 digest のみ分類 → 該当ノートだけ「既存ノート + 新規 digest」で再生成
# ---------------------------------------------------------------------------

INCR_CLASSIFY_PROMPT = """\
あなたは技術ナレッジの分類器です。既存の技術領域一覧と、新しく増えた digest の要点を渡します。
各 digest を、内容が最も合致する **既存領域** に割り当ててください。
どの既存領域にも当てはまらない場合に限り、新しい領域を提案します。

# 出力（厳守）
- **JSON のみ**を出力。前置き・後書き・コードフェンス・説明文は一切書かない。
- スキーマ:
{{
  "assignments": [
    {{"id": "<digest id>", "slugs": ["<既存 or new の slug>", ...]}}   // 1 digest を複数領域へ割当可
  ],
  "new_technologies": [
    {{"slug": "kebab-ascii", "title": "表示名", "category": "language|framework|tool|infra|concept|practice", "related": ["<slug>", ...]}}
  ]
}}
- 既存領域に合うなら新領域を作らない（無闇に増やさない）。
- assignments の slugs には、既存 slug か new_technologies で定義した slug のみを使う。
- 提示した digest id のみを使う。

# 既存の技術領域（slug | title | category）
{existing}

# 新しく増えた digest（要点）
{new_index}
"""

MERGE_PROMPT = """\
あなたは既存の技術ナレッジノートに、新しく増えた作業ログ由来の知見を統合して
更新版ノートを書き出すアシスタントです。

# 最重要（厳守・これを破ると出力は無効）
- あなたの応答テキストは、そのまま 1 つの Markdown ファイルとして上書き保存される。
- よって応答には **更新後のノート本体のみ** を出力する。
- 前置き・後書き・要約・「更新しました」等の作業報告・コードフェンス囲み・チャット的説明を一切書かない。
- ファイル書き込みやツール実行はしない。出力したテキストがそのままノートになる。
- 出力は必ず frontmatter（先頭行が `---`）から始める。

# タスク
「既存ノート」を土台に、「新しく増えた digest」群の知見**だけ**を統合し、更新版ノートを出力する。
- 既存ノートの構成・既存の知見・既存の出典（出典: <project> / <date>）は維持する。
- 新しい digest から得られる新規知見を追加し、各知見末尾に出典を明記する。
- 既存と重複・矛盾する場合は、**追記で増やさず** 1 つに統合・更新（矛盾は併記）。ノートを肥大化させない。
- frontmatter の `updated` を {updated} にする。tags は既存を尊重し、新たな寄与プロジェクトがあれば
  `project/<id>` を追加する（既存タグは消さない）。
- 関連技術リンクは {related} の slug のみ `[[<slug>]]`。それ以外のリンクは作らない。
- 一般化して書く。固有名詞・接続情報・顧客特定情報は持ち込まない。<REDACTED:種別> は復元しない。捏造しない。

# 対象の技術領域
- タイトル: {title} ／ slug: {slug} ／ カテゴリ: {category}
- 新たな寄与プロジェクト（あれば project/<id> タグに追加）: {projects}

# 既存ノート（これを土台に更新する）
{existing_note}

# 新しく増えた digest 群（この分の知見だけ取り込む）
{new_sources}
"""


def build_incr_classify_prompt(existing_techs, new_digests):
    existing = "\n".join("%s | %s | %s" % (t["slug"], t.get("title", ""), t.get("category", ""))
                         for t in existing_techs)
    new_index = "\n\n".join(digest_index_entry(d) for d in new_digests)
    return INCR_CLASSIFY_PROMPT.format(existing=existing, new_index=new_index)


def build_merge_prompt(tech, existing_note, new_digests, updated):
    projects = sorted(set(d["pid"] for d in new_digests))
    blocks, total = [], 0
    for d in new_digests:
        block = "===== digest: %s (project=%s, date=%s) =====\n%s" % (
            d["id"], d["pid"], d["date"], d["text"])
        if total + len(block) > MAX_NOTE_SOURCE_CHARS:
            blocks.append("…(入力が長いため以降の digest を省略)")
            break
        blocks.append(block)
        total += len(block)
    return MERGE_PROMPT.format(
        title=tech.get("title") or tech["slug"],
        slug=tech["slug"],
        category=tech.get("category") or "concept",
        related=", ".join(tech.get("related") or []) or "(なし)",
        projects=", ".join(projects) or "(なし)",
        updated=updated,
        existing_note=existing_note,
        new_sources="\n\n".join(blocks),
    )


def _write_note_guarded(out_path, ok, result):
    """生成結果を frontmatter ガード付きで書き出す。(成功bool) を返す。"""
    note = K.strip_code_fence(result) if ok else ""
    if ok and not note.lstrip().startswith("---"):
        with open(out_path + ".raw.txt", "w", encoding="utf-8") as f:
            f.write(note)
        return False
    if ok:
        for ext in (".raw.txt", ".prompt.txt"):
            if os.path.exists(out_path + ext):
                os.remove(out_path + ext)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(note + "\n")
        return True
    return False


def run_incremental(home, note_subdir, digests, state, opts, updated):
    """増分更新: 新規 digest だけを分類し、影響を受けた技術ノートのみ
    「既存ノート + 新規 digest」で再生成する。変化の無い領域はスキップ（LLM 呼び出しゼロ）。"""
    notes_dir = os.path.join(home, note_subdir)
    os.makedirs(notes_dir, exist_ok=True)
    by_id = {d["id"]: d for d in digests}
    techs = state["technologies"]
    bymap = {t["slug"]: t for t in techs}
    seen = set(state["seen"])

    current_ids = set(by_id.keys())
    new_ids = sorted(current_ids - seen)
    if not new_ids:
        idx = write_index(home, note_subdir, techs, updated)
        save_state(home, techs, seen, updated)
        sys.stderr.write("[kb] 増分更新: 新規 digest なし。最新です（index 更新のみ）。\n")
        sys.stderr.write("[kb] ナレッジベース: %s\n" % home)
        return 0
    new_digests = [by_id[i] for i in new_ids]
    sys.stderr.write("[kb] 増分更新: 新規 digest %d 件を分類します...\n" % len(new_ids))

    # 1) 新規 digest を既存領域へ割り当て（必要なら新領域提案）
    prompt = build_incr_classify_prompt(techs, new_digests)
    ok, result = K.run_claude(prompt, timeout=TAXONOMY_TIMEOUT)
    if not ok:
        with open(os.path.join(home, "_incr_classify.prompt.txt"), "w", encoding="utf-8") as f:
            f.write(prompt)
        sys.stderr.write("[kb] 増分分類 失敗: %s -> プロンプトを保存\n" % result)
        return 2
    try:
        raw = K.extract_json(result)
    except ValueError as e:
        with open(os.path.join(home, "_incr_classify.raw.txt"), "w", encoding="utf-8") as f:
            f.write(result)
        sys.stderr.write("[kb] 増分分類: JSON 抽出失敗(%s) -> 生出力を保存\n" % e)
        return 2

    # 2) 新領域を登録
    for nt in (raw.get("new_technologies") or []):
        if not isinstance(nt, dict):
            continue
        slug = K.slugify(nt.get("slug") or nt.get("title") or "")
        if not slug or slug in bymap:
            continue
        t = {"slug": slug, "title": (nt.get("title") or slug).strip(),
             "category": (nt.get("category") or "concept").strip(),
             "related": [K.slugify(r) for r in (nt.get("related") or []) if r],
             "sources": []}
        techs.append(t)
        bymap[slug] = t

    # 3) 割り当てを反映し、領域ごとの「今回追加された digest」を集計
    added_by_slug = {}
    for a in (raw.get("assignments") or []):
        if not isinstance(a, dict):
            continue
        did = a.get("id")
        if did not in by_id or did not in set(new_ids):
            continue
        for s in (a.get("slugs") or []):
            slug = K.slugify(s)
            t = bymap.get(slug)
            if not t:  # 未知 slug を参照していたら最小定義で作る（防御的）
                t = {"slug": slug, "title": slug, "category": "concept",
                     "related": [], "sources": []}
                techs.append(t)
                bymap[slug] = t
            if did not in t["sources"]:
                t["sources"].append(did)
            added_by_slug.setdefault(slug, [])
            if did not in added_by_slug[slug]:
                added_by_slug[slug].append(did)

    # 4) 影響を受けた領域のみノート更新
    template = K.load_template("tech_note")
    updated_cnt, created_cnt, failed = 0, 0, 0
    for slug in sorted(added_by_slug):
        t = bymap[slug]
        added_srcs = [by_id[i] for i in added_by_slug[slug] if i in by_id]
        out_path = os.path.join(notes_dir, "%s.md" % slug)
        if os.path.exists(out_path):
            with open(out_path, "r", encoding="utf-8") as f:
                existing_note = f.read()
            prompt = build_merge_prompt(t, existing_note, added_srcs, updated)
            mode = "更新"
        else:
            # ノートが無い（新領域 or 消失）→ その領域の全 sources から新規生成
            all_srcs = [by_id[i] for i in t["sources"] if i in by_id]
            prompt = build_note_prompt(t, all_srcs or added_srcs, template)
            mode = "新規"
        sys.stderr.write("[kb] 増分%s: %s (+%d digest) 生成中...\n" % (mode, slug, len(added_srcs)))
        ok, result = K.run_claude(prompt, timeout=NOTE_TIMEOUT)
        if _write_note_guarded(out_path, ok, result):
            if mode == "更新":
                updated_cnt += 1
            else:
                created_cnt += 1
        else:
            with open(out_path + ".prompt.txt", "w", encoding="utf-8") as f:
                f.write(prompt)
            sys.stderr.write("[kb] 増分%s 失敗(%s): %s -> プロンプトを保存\n"
                             % (mode, slug, result if not ok else "非ノート出力"))
            failed += 1

    # 5) seen を全新規 digest で更新（未割当も含め二度と分類し直さない）し、状態・index を保存
    seen |= set(new_ids)
    save_state(home, techs, seen, updated)
    idx = write_index(home, note_subdir, techs, updated)
    skipped = len(techs) - len(added_by_slug)
    sys.stderr.write("[kb] 増分完了: 更新=%d 新規=%d 失敗=%d スキップ=%d / index=%s\n"
                     % (updated_cnt, created_cnt, failed, skipped, idx))
    sys.stderr.write("[kb] ナレッジベース: %s\n" % home)
    return 0


# ---------------------------------------------------------------------------
# 引数
# ---------------------------------------------------------------------------

def parse_args(argv):
    opts = {"out": None, "since": None, "until": None, "project": None,
            "limit": None, "dry_run": False, "taxonomy_only": False,
            "include_unclassified": None, "from_taxonomy": None, "rebuild": False}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--out":
            opts["out"] = argv[i + 1]; i += 2; continue
        if a == "--from-taxonomy":
            opts["from_taxonomy"] = argv[i + 1]; i += 2; continue
        if a == "--rebuild":
            opts["rebuild"] = True; i += 1; continue
        if a == "--since":
            opts["since"] = argv[i + 1]; i += 2; continue
        if a == "--until":
            opts["until"] = argv[i + 1]; i += 2; continue
        if a == "--project":
            opts["project"] = argv[i + 1]; i += 2; continue
        if a == "--limit":
            opts["limit"] = int(argv[i + 1]); i += 2; continue
        if a == "--dry-run":
            opts["dry_run"] = True; i += 1; continue
        if a == "--taxonomy-only":
            opts["taxonomy_only"] = True; i += 1; continue
        if a == "--include-unclassified":
            opts["include_unclassified"] = True; i += 1; continue
        if a == "--no-unclassified":
            opts["include_unclassified"] = False; i += 1; continue
        sys.stderr.write("[kb] 不明な引数を無視: %s\n" % a)
        i += 1
    return opts


def collect_digests(opts, cfg):
    src_dir = K.digests_dir("tech")
    if not os.path.isdir(src_dir):
        sys.stderr.write("[kb] tech digest が見つかりません: %s\n" % src_dir)
        return []
    inc_uncl = opts["include_unclassified"]
    if inc_uncl is None:
        inc_uncl = cfg.get("include_unclassified", True)
    digests = []
    for path in sorted(glob.glob(os.path.join(src_dir, "*.md"))):
        name = os.path.basename(path)[:-3]
        pid, date = split_id(name)
        if pid == "_unclassified" and not inc_uncl:
            continue
        if opts["project"] and pid != opts["project"]:
            continue
        if opts["since"] and date and date < opts["since"]:
            continue
        if opts["until"] and date and date > opts["until"]:
            continue
        digests.append(load_digest(path))
    return digests


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    opts = parse_args(sys.argv[1:])
    cfg = K.load_config()
    note_subdir = cfg.get("note_subdir", "tech")
    home = K.kb_home(opts["out"])
    updated = K.today_jst()

    digests = collect_digests(opts, cfg)
    if not digests:
        sys.stderr.write("[kb] 対象 digest が 0 件。終了。\n")
        return 1
    valid_ids = set(d["id"] for d in digests)
    sys.stderr.write("[kb] 対象 tech digest: %d 件 -> 出力先: %s\n" % (len(digests), home))

    os.makedirs(home, exist_ok=True)
    notes_dir = os.path.join(home, note_subdir)
    os.makedirs(notes_dir, exist_ok=True)

    import json as _json

    # ---- パスA をスキップして保存済みタクソノミーを再利用（全ノート再生成） ----
    if opts["from_taxonomy"]:
        with open(opts["from_taxonomy"], "r", encoding="utf-8") as f:
            saved = _json.load(f)
        techs = normalize_taxonomy(saved, valid_ids)
        if not techs:
            sys.stderr.write("[kb] --from-taxonomy: 有効な技術領域が 0 件。終了。\n")
            return 2
        sys.stderr.write("[kb] タクソノミー再利用: %s（技術領域 %d 件）\n"
                         % (opts["from_taxonomy"], len(techs)))
        rc = run_pass_b(home, note_subdir, digests, techs, opts, updated)
        save_state(home, techs, valid_ids, updated)  # 以降は増分更新に乗せる
        return rc

    # ---- 増分更新: 既存状態があり、--rebuild / --taxonomy-only / --dry-run でないとき ----
    state = load_state(home)
    if state and not opts["rebuild"] and not opts["taxonomy_only"] and not opts["dry_run"]:
        sys.stderr.write("[kb] 既存状態を検出 -> 増分更新モード（--rebuild で全再構築）\n")
        return run_incremental(home, note_subdir, digests, state, opts, updated)

    # ---- パスA: タクソノミー（全再構築 / 初回 / --rebuild / --taxonomy-only） ----
    tax_prompt = build_taxonomy_prompt(digests)
    tax_prompt_path = os.path.join(home, "_taxonomy.prompt.txt")
    if opts["dry_run"]:
        with open(tax_prompt_path, "w", encoding="utf-8") as f:
            f.write(tax_prompt)
        sys.stderr.write("[kb] (dry-run) タクソノミー用プロンプトを %s に保存\n" % tax_prompt_path)
        sys.stderr.write("[kb] (dry-run) digest %d 件のインデックスを構築済み。claude は呼ばない。\n"
                         % len(digests))
        return 0

    sys.stderr.write("[kb] パスA: タクソノミー生成中（claude -p）...\n")
    ok, result = K.run_claude(tax_prompt, timeout=TAXONOMY_TIMEOUT)
    if not ok:
        with open(tax_prompt_path, "w", encoding="utf-8") as f:
            f.write(tax_prompt)
        sys.stderr.write("[kb] パスA 失敗: %s -> プロンプトを %s に保存\n" % (result, tax_prompt_path))
        return 2
    try:
        raw = K.extract_json(result)
    except ValueError as e:
        raw_path = os.path.join(home, "_taxonomy.raw.txt")
        with open(raw_path, "w", encoding="utf-8") as f:
            f.write(result)
        sys.stderr.write("[kb] パスA: JSON 抽出失敗(%s) -> 生出力を %s に保存\n" % (e, raw_path))
        return 2
    techs = normalize_taxonomy(raw, valid_ids)
    if not techs:
        sys.stderr.write("[kb] パスA: 有効な技術領域が 0 件。終了。\n")
        return 2

    # タクソノミー＋取り込み済み digest を状態として残す（増分更新・index 再生成の土台）
    save_state(home, techs, valid_ids, updated)
    sys.stderr.write("[kb] パスA 完了: 技術領域 %d 件\n" % len(techs))

    if opts["taxonomy_only"]:
        idx = write_index(home, note_subdir, techs, updated)
        sys.stderr.write("[kb] taxonomy-only: index=%s\n" % idx)
        return 0

    return run_pass_b(home, note_subdir, digests, techs, opts, updated)


def run_pass_b(home, note_subdir, digests, techs, opts, updated):
    """パスB: 技術領域ごとに Obsidian ノートを生成し、最後に index.md を書く。"""
    notes_dir = os.path.join(home, note_subdir)
    os.makedirs(notes_dir, exist_ok=True)
    template = K.load_template("tech_note")
    by_id = {d["id"]: d for d in digests}
    target_techs = techs[:opts["limit"]] if opts["limit"] else techs
    generated, failed = 0, 0
    for t in target_techs:
        srcs = [by_id[i] for i in t["sources"] if i in by_id]
        if not srcs:
            continue
        prompt = build_note_prompt(t, srcs, template)
        out_path = os.path.join(notes_dir, "%s.md" % t["slug"])
        sys.stderr.write("[kb] パスB: %s (%d sources) 生成中...\n" % (t["slug"], len(srcs)))
        ok, result = K.run_claude(prompt, timeout=NOTE_TIMEOUT)
        note = K.strip_code_fence(result) if ok else ""
        # ガード: ノートは frontmatter(---) で始まるはず。会話的メタ応答（claude -p が
        # エージェント的に振る舞い「書き出しました」等を返すケース）を弾く。
        if ok and not note.lstrip().startswith("---"):
            ok = False
            result = "frontmatter(---) で始まらない非ノート出力（メタ応答の可能性）"
            with open(out_path + ".raw.txt", "w", encoding="utf-8") as f:
                f.write(note)
        if ok:
            # 再生成成功時は前回の失敗痕跡（.raw.txt / .prompt.txt）を掃除
            for ext in (".raw.txt", ".prompt.txt"):
                if os.path.exists(out_path + ext):
                    os.remove(out_path + ext)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(note + "\n")
            generated += 1
        else:
            with open(out_path + ".prompt.txt", "w", encoding="utf-8") as f:
                f.write(prompt)
            sys.stderr.write("[kb] パスB 失敗(%s): %s -> プロンプトを保存\n" % (t["slug"], result))
            failed += 1

    idx = write_index(home, note_subdir, techs, updated)
    sys.stderr.write("[kb] 完了: ノート生成=%d 失敗=%d / index=%s\n" % (generated, failed, idx))
    sys.stderr.write("[kb] ナレッジベース: %s\n" % home)
    return 0


if __name__ == "__main__":
    sys.exit(main())
