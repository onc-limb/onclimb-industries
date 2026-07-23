#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""summarize: 分類済みログを入力に claude -p で「整理された情報（digest）」を 2 形式生成する。

これは最終報告書そのものではなく、後段の別スキルが報告書へ整形するための
"整理された情報" を作る段階。詳細・網羅を優先し、過程を漏れなく残す。

2 形式:
  project … プロジェクト視点の整理情報（目的→作業→つまづき/気づき→最終対応） -> digests/project/
  tech    … 技術者視点の整理情報（解決したい技術課題→ユーザー視点の課題
            →AIがつまづいたコマンド周りの課題→解決方法）                    -> digests/tech/

整理プロンプトの必須要件（本システムの存在理由）:
  - 残存ノイズ（重複・冗長なツール出力・進捗メッセージ等）を除外する
  - 過程（何を試し/なぜ判断し/何が失敗し何が効いたか）を必ず残す。結果だけは不可
  - 元ログにない内容を捏造しない。不明点は「記録なし」と明示
  - 報告書としての体裁づくりより、情報の網羅・粒度・正確さを優先する

高速化のための挙動:
  - 差分スキップ: 既存 digest が分類済みログ（classified/<pid>/<date>.jsonl）より新しければ
    生成をスキップする（classify 側も内容不変ならファイルを触らないため、この比較が機能する）。
    強制再生成は --force。
  - 2 形式統合: project と tech の両方が対象のときは 1 回の claude 呼び出しで両形式を
    出力させ、区切り行で分割して保存する（呼び出し回数が半分になる）。

使い方:
  bin/summarize.py                         # 全プロジェクト×全日付（classified 全体）
  bin/summarize.py 2026-06-22              # 指定日の全プロジェクト
  bin/summarize.py 2026-06-22 onclimb-industries       # 指定日・指定プロジェクト
  bin/summarize.py --formats project 2026-06-22
  bin/summarize.py --force 2026-06-22      # 差分スキップを無効化して再生成
  bin/summarize.py --dry-run ...           # claude を呼ばずプロンプトだけ生成

claude CLI が見つからない/失敗した場合は、合成プロンプトを digests/<type>/<...>.prompt.txt
に書き出すので、手動で `claude -p < そのファイル` 等で生成できる。
"""
import glob
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worklog_lib as W  # noqa: E402

FORMATS = ["project", "tech"]
OUTPUT_SUBDIR = "digests"  # 「整理された情報」の出力先（最終報告書ではない）

# 2 形式統合出力の区切り行。この行より前が project、後が tech。
# ログ本文に偶然現れない程度に特殊な文字列にしてある。
FORMAT_DELIM = "<<<WORKLOG-FORMAT:tech>>>"
MAX_LOG_CHARS = 180000  # 1 出力あたりのログ投入上限（コンテキスト保護）
ENTRY_SEP = "\n\n"  # 1 エントリ間の区切り

# tool_result（ツール実行の生出力）圧縮。情報密度が低いのに全体量の過半を
# 占めるため、先頭 HEAD 字 + 末尾 TAIL 字だけ残して中間を省略する。これにより
# 後述の文字数ベース分割数（= claude 呼び出し回数）が減る。末尾を残すのは、
# コマンドの成否・変更ファイル数・エラーが末尾に出やすいため。
TOOL_RESULT_HEAD = 400
TOOL_RESULT_TAIL = 200

# claude 並列実行の同時数。上げるほど速いが、Max プランの 5 時間レート枠に
# 当たりやすくなる。環境変数 WORKLOG_SUMMARIZE_CONCURRENCY で調整可能。
try:
    CONCURRENCY = max(1, int(os.environ.get("WORKLOG_SUMMARIZE_CONCURRENCY", "4")))
except ValueError:
    CONCURRENCY = 4

BASE_INSTRUCTION = """\
あなたは SES エンジニアの作業ログを「報告書を書くための整理された情報」へ構造化するアシスタントです。
これは最終報告書そのものではありません。後で別の担当（別スキル）がこの整理情報を入力に
きちんとした報告書へ整形します。したがって体裁よりも、情報の網羅・粒度・正確さを優先してください。
以下の作業ログ（Claude Code の操作記録を構造抽出・マスキング済み JSONL を読みやすく整形したもの）を整理してください。

# 厳守事項
1. 残ったノイズ（重複したやり取り、冗長なツール出力、空メッセージ、進捗メッセージ、機械的な反復）は除外する。
2. **過程を必ず残す**: 何を試し、なぜその判断をし、何が失敗し、何が効いたか。最終結果だけは不可。これがこの整理情報の存在理由。
3. 元ログに無い内容を捏造しない。推測が必要な箇所や情報が無い項目は「記録なし」と明示する。
   その際、欠損の型が判別できれば括弧で添える: 「記録なし（セッション中断）」（ログが途中で切れた）/
   「記録なし（ユーザー手動・ログ外）」（ユーザーが手で実施したと申告・示唆されている）/
   「記録なし（背景の記載なし）」（依頼理由・背景が会話に出てこない）。判別できなければ「記録なし」のみ。
   ※この型は下流（jarvis-record）がヒアリングの聞き方を変えるために使う。
4. 既に <REDACTED:種別> で伏字化された箇所はそのまま伏字のまま扱い、復元を試みない。
5. 出力は Markdown のみ。前置き・後書き・コードフェンス囲みは不要。指定の見出し構成に厳密に従う。
6. 各見出しは箇条書きで具体的に。後で報告書を書く人が困らないよう、固有の事実・数値・コマンド・判断を漏れなく拾う。
7. テンプレ内に表・ステータスラベル（[完了] 等）・サブ見出し（### …）・「状況/結論/根拠」等の小構造が指定されている場合は、その書式に従う。該当する事実が無い項目・セクションは「記録なし」と明記し、見出し自体は省略しない。
8. 時間帯・工数は、作業ログ各行のタイムスタンプ（[HH:MM:SS]）から読み取れる範囲で記載する（無理に推定しない）。
{segment_note}
{output_spec}

# 対象メタ情報
- プロジェクト: {project}
- 日付: {date}

# 作業ログ
{log}
"""

# 出力フォーマット指定。1 形式のみのときは従来どおりテンプレを 1 つ渡す。
SINGLE_OUTPUT_SPEC = """\
# 出力フォーマット（この構成・見出しで書く）
{template}"""

# 2 形式が対象のときは 1 回の呼び出しで両方を出力させる（呼び出し回数の半減が目的。
# 入力ログが支配的で、同じログを 2 回読ませるのが無駄なため）。区切り行で分割保存する。
MERGED_OUTPUT_SPEC = """\
# 出力フォーマット（2 形式を 1 回で出力する）
同じ作業ログから「プロジェクト視点」と「技術者視点」の 2 つの整理情報を続けて出力する。
1. まず下記［プロジェクト視点テンプレ］の構成・見出しでプロジェクト視点の整理情報を書く。
2. 次に、区切り行として {delim} だけの行を 1 行出力する（前後に説明・空白・コードフェンスを付けない）。
3. 続けて下記［技術者視点テンプレ］の構成・見出しで技術者視点の整理情報を書く。
両形式とも上の厳守事項に従う。同じ事実でも両方の観点で必要なら双方に書く（片方に書いたからと省略しない）。

［プロジェクト視点テンプレ］
{template_project}

［技術者視点テンプレ］
{template_tech}"""

# 時間帯分割時（セグメント 2 個以上）にのみ厳守事項へ追記する注意書き。
# 各セグメントの出力は「## 【時間帯 i/n】」見出しの下に連結されるため、
# テンプレを丸ごと繰り返すと H1 や TL;DR が N 回並んで階層が壊れる。
SEGMENT_NOTE = """\
9. この作業ログは長いため時間帯で分割されており、あなたが整理するのはその一部です。
   出力は他の時間帯の整理と「## 【時間帯 i/n】」見出しの下に連結されるため、
   （2 形式出力の場合は各形式とも）H1 見出し（# …）とテンプレ冒頭の結論層
   （TL;DR・成果サマリ）のセクションは出力せず、それ以降の ## 見出しから書き始める。"""

# 時間帯分割ファイルの後処理: band（時間帯セクション）間の重複・矛盾を検知して
# digest 冒頭に「突き合わせリスト」を出す。並行セッションが別 band に分かれると、
# 同じ作業が複数 band に別内容で書かれ、下流（jarvis-record）が食い違いに気づけないため。
# あくまで「ユーザーに確認する候補」であり、どちらが正しいかはここで決めない。
RECON_INSTRUCTION = """\
以下は、1 日の作業ログを時間帯で分割して整理した digest です（プロジェクト: {project} / 日付: {date}）。
時間帯セクション（## 【時間帯 i/n: HH:MM–HH:MM】）の間で、
(1) 同じ作業・同じ対象が複数の時間帯に重複して書かれている箇所、
(2) 同じ対象について記述が食い違っている箇所（例: 一方は「未対応」、他方は「完了」）
を抽出してください。

# 厳守事項
- digest に書かれていることだけを根拠にする。どちらが正しいかを判定・推測しない。
- 出力は Markdown の箇条書きのみ。前置き・後書き・見出し・コードフェンスは不要。
- 各項目は「- **対象**: 時間帯X は「…」/ 時間帯Y は「…」〔重複 or 矛盾〕」の形式で、
  対象と各時間帯の記述を短く引用する。
- 該当が無ければ「- なし」とだけ出力する。
- 別の作業をたまたま似た言葉で書いただけの可能性が残る場合は、項目末尾に（別作業の可能性あり）と添える。

# digest
{digest}
"""


def reconcile_bands(project, date, band_blocks):
    """時間帯分割された digest の band 間重複・矛盾リストを claude で生成する。
    返り値は digest 冒頭に挿すセクション文字列（失敗時はその旨の注記）。"""
    digest_text = cap_text("\n\n".join(band_blocks))
    prompt = RECON_INSTRUCTION.format(project=project, date=date, digest=digest_text)
    # 重複・矛盾の抽出は軽い仕事なので現行 Haiku で十分（digest 本文の生成は Sonnet のまま）
    ok, result = W.run_claude(prompt, model="haiku")
    header = "## 【時間帯間の重複・矛盾（jarvis-record での突き合わせ用）】"
    if ok:
        body = result.strip() or "- なし"
        return "%s\n\n%s" % (header, body)
    return ("%s\n\n- （自動検知に失敗: %s。jarvis-record 側で時間帯セクションを"
            "突き合わせること）" % (header, result))


def digest_is_fresh(out_path, src_path):
    """digest が分類済みログより新しければ True（＝再生成不要）。
    classify が内容不変のファイルを触らない（mtime 保持）ことを前提にした差分スキップ。"""
    try:
        return os.path.getmtime(out_path) >= os.path.getmtime(src_path)
    except OSError:
        return False


def split_merged_output(text):
    """2 形式統合出力を区切り行で (project, tech) に分割する。区切りが無ければ None。"""
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        # 稀にモデルが区切り行をバッククォートで囲むことがあるため許容する
        if ln.strip().strip("`") == FORMAT_DELIM:
            return "\n".join(lines[:i]).strip(), "\n".join(lines[i + 1:]).strip()
    return None


def load_template(name):
    path = os.path.join(W.templates_dir(), "%s.md" % name)
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    # テンプレート説明用の引用注記行（> ...）は出力に含めないよう除去する
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith(">"))


def compress_tool_result(body):
    """tool_result 本文を先頭 HEAD 字 + 末尾 TAIL 字だけ残して圧縮する。
    中間は「…(結果の中間 N 字を省略)…」に置き換える。短ければそのまま返す。"""
    if len(body) <= TOOL_RESULT_HEAD + TOOL_RESULT_TAIL:
        return body
    omitted = len(body) - TOOL_RESULT_HEAD - TOOL_RESULT_TAIL
    return "%s\n…(結果の中間 %d 字を省略)…\n%s" % (
        body[:TOOL_RESULT_HEAD], omitted, body[-TOOL_RESULT_TAIL:],
    )


def render_entry(e):
    """1 エントリを人間可読な時系列テキストへ。空 body は None を返しスキップ対象。"""
    ts = (e.get("ts") or "")[11:19]
    kind = e.get("kind")
    tool = e.get("tool")
    body = (e.get("body") or "").strip()
    if not body:
        return None
    # tool_result のみ圧縮（指示 / 応答 / tool_use は情報密度が高いので触らない）
    if kind == "tool_result":
        body = compress_tool_result(body)
    if kind == "instruction":
        head = "[%s] 指示(user)" % ts
    elif kind == "response":
        head = "[%s] 応答(assistant)" % ts
    elif kind == "tool_use":
        head = "[%s] 操作 %s" % (ts, tool or "")
    elif kind == "tool_result":
        head = "[%s] 結果" % ts
    else:
        head = "[%s] %s" % (ts, kind)
    return "%s\n%s" % (head, body)


def cap_text(text):
    """1 セグメントが上限超過した場合の最後の砦。上限を超えた分を切り捨てる。"""
    if len(text) > MAX_LOG_CHARS:
        return text[:MAX_LOG_CHARS] + ENTRY_SEP + \
            "…(ログが長いため以降を省略: 残り %d 文字)" % (len(text) - MAX_LOG_CHARS)
    return text


def chunk_time_range(chunk):
    """ブロック（エントリ列）の最初/最後のタイムスタンプ (HH:MM) を返す。"""
    times = [t for t in ((e.get("ts") or "")[11:16] for e in chunk) if t]
    if not times:
        return None, None
    return times[0], times[-1]


def split_to_fit(entries):
    """整形後テキストが MAX_LOG_CHARS 以下に収まるよう、時系列のままエントリ
    境界で文字数ベースに詰めて分割する。返り値は [(chunk_entries, rendered_text), ...]。
    各ブロックを上限近くまで充填するので、件数均等分割より分割数が減り、
    時間帯の切れ目も少なくなる。"""
    chunks = []
    cur_entries, cur_parts, cur_len = [], [], 0
    for e in entries:
        r = render_entry(e)
        if r is None:
            continue
        add = len(r) + (len(ENTRY_SEP) if cur_parts else 0)
        if cur_parts and cur_len + add > MAX_LOG_CHARS:
            chunks.append((cur_entries, ENTRY_SEP.join(cur_parts)))
            cur_entries, cur_parts, cur_len = [], [], 0
            add = len(r)
        cur_entries.append(e)
        cur_parts.append(r)
        cur_len += add
    if cur_parts:
        chunks.append((cur_entries, ENTRY_SEP.join(cur_parts)))
    # 単一エントリが上限超過した場合の最後の砦
    return [(ce, cap_text(txt)) for ce, txt in chunks]


def read_entries(path):
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def run_claude_many(prompts):
    """複数プロンプトを最大 CONCURRENCY 件まで同時に claude へ投げ、
    入力順で [(ok, output_or_error), ...] を返す。"""
    if len(prompts) <= 1:
        return [W.run_claude(p, model="sonnet") for p in prompts]
    results = [None] * len(prompts)
    with ThreadPoolExecutor(max_workers=min(CONCURRENCY, len(prompts))) as ex:
        futs = {ex.submit(W.run_claude, p, model="sonnet"): idx for idx, p in enumerate(prompts)}
        for fut, idx in futs.items():
            results[idx] = fut.result()
    return results


def parse_args(argv):
    formats = list(FORMATS)
    dry = False
    force = False
    pos = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--formats":
            formats = [x.strip() for x in argv[i + 1].split(",") if x.strip() in FORMATS]
            i += 2
            continue
        if a == "--dry-run":
            dry = True
            i += 1
            continue
        if a == "--force":
            force = True
            i += 1
            continue
        pos.append(a)
        i += 1
    date = pos[0] if len(pos) > 0 else None
    project = pos[1] if len(pos) > 1 else None
    return date, project, formats, dry, force


def main():
    home = W.worklog_home()
    cls_dir = os.path.join(home, "classified")
    date, project, formats, dry, force = parse_args(sys.argv[1:])

    # 対象 (project_id, date, path) を列挙
    targets = []
    proj_dirs = [project] if project else [
        d for d in os.listdir(cls_dir) if os.path.isdir(os.path.join(cls_dir, d))
    ]
    for pid in proj_dirs:
        pat = os.path.join(cls_dir, pid, "%s.jsonl" % (date or "*"))
        for f in sorted(glob.glob(pat)):
            d = os.path.basename(f)[:-6]
            targets.append((pid, d, f))

    if not targets:
        sys.stderr.write("[summarize] 対象なし (date=%s project=%s)\n" % (date, project))
        return

    templates = {fmt: load_template(fmt) for fmt in formats}

    # (project_id, date) を 1 ジョブとし、必要な形式だけを対象にする。
    # 両形式が対象なら 1 回の claude 呼び出しで両方出力させる（MERGED_OUTPUT_SPEC）。
    # 各ジョブは 1 つ以上のセグメント（時間帯）を持つ。上限以下なら 1 セグメント、
    # 超過したら split_to_fit で文字数分割する。
    jobs = []  # {formats, out_paths, label, pid, date, n, units:[(span, prompt), ...]}
    skipped = 0
    for pid, d, path in targets:
        out_paths = {}
        for fmt in formats:
            out_dir = os.path.join(home, OUTPUT_SUBDIR, fmt)
            os.makedirs(out_dir, exist_ok=True)
            out_paths[fmt] = os.path.join(out_dir, "%s_%s.md" % (pid, d))
        # 差分スキップ: digest が分類済みログより新しい形式は生成しない
        stale = [f for f in formats if force or not digest_is_fresh(out_paths[f], path)]
        if not stale:
            skipped += 1
            continue
        entries = read_entries(path)
        chunks = split_to_fit(entries)
        if not chunks or not any(txt.strip() for _, txt in chunks):
            continue
        disp_pid = "未分類" if pid == "_unclassified" else pid
        n = len(chunks)
        # テンプレ H1 のプレースホルダを実値へ（{一般化した…} 等 LLM 向けの穴は残す）
        tmpl = {f: templates[f].replace("{project}", disp_pid).replace("{date}", d)
                for f in stale}
        if len(stale) > 1:
            spec = MERGED_OUTPUT_SPEC.format(
                delim=FORMAT_DELIM,
                template_project=tmpl["project"], template_tech=tmpl["tech"],
            )
        else:
            spec = SINGLE_OUTPUT_SPEC.format(template=tmpl[stale[0]])
        units = []
        for idx, (chunk_entries, text) in enumerate(chunks, start=1):
            if n > 1:
                lo, hi = chunk_time_range(chunk_entries)
                span = "%s–%s" % (lo or "??", hi or "??")
                log_for_prompt = (
                    "（この作業ログは長いため時間帯 %d/%d: %s の部分です）\n\n%s"
                    % (idx, n, span, text)
                )
            else:
                span = None
                log_for_prompt = text
            prompt = BASE_INSTRUCTION.format(
                output_spec=spec, project=disp_pid, date=d, log=log_for_prompt,
                segment_note=(SEGMENT_NOTE if n > 1 else ""),
            )
            units.append((span, prompt))
        jobs.append({
            "formats": stale, "out_paths": out_paths,
            "label": "%s/%s_%s" % ("+".join(stale), pid, d),
            "pid": disp_pid, "date": d,
            "n": n, "units": units,
        })

    if skipped:
        sys.stderr.write("[summarize] スキップ=%d（digest が最新。再生成は --force）\n" % skipped)

    generated, failed = 0, 0

    if dry:
        for job in jobs:
            path = job["out_paths"][job["formats"][0]] + ".prompt.txt"
            if job["n"] == 1:
                blob = job["units"][0][1]
            else:
                sep = "\n" + "=" * 60 + "\n"
                blob = sep.join(
                    "## 【時間帯 %d/%d: %s】\n%s" % (i, job["n"], span or "", pr)
                    for i, (span, pr) in enumerate(job["units"], start=1)
                )
            with open(path, "w", encoding="utf-8") as f:
                f.write(blob)
            sys.stderr.write("[summarize] (dry) %s\n" % path)
            generated += 1
        sys.stderr.write("[summarize] 生成=%d 失敗=%d スキップ=%d\n" % (generated, failed, skipped))
        return

    # 全ジョブの全セグメントのプロンプトを平坦化し、まとめて並列生成する。
    flat, index = [], []  # index[k] = (job_idx, unit_idx)
    for ji, job in enumerate(jobs):
        for ui, (_span, prompt) in enumerate(job["units"]):
            index.append((ji, ui))
            flat.append(prompt)

    if not flat:
        sys.stderr.write("[summarize] 生成対象なし（スキップ=%d）\n" % skipped)
        return

    n_split = sum(1 for j in jobs if j["n"] > 1)
    sys.stderr.write(
        "[summarize] %d ファイル / %d セグメント（分割ファイル %d）を最大 %d 並列で生成中...\n"
        % (len(jobs), len(flat), n_split, min(CONCURRENCY, len(flat)))
    )
    results = run_claude_many(flat)

    per_job = {}
    for (ji, ui), res in zip(index, results):
        per_job.setdefault(ji, {})[ui] = res

    for ji, job in enumerate(jobs):
        resmap = per_job.get(ji, {})
        fmts = job["formats"]
        n = job["n"]
        merged = len(fmts) > 1
        # 失敗時のプロンプト・生出力の保存先は先頭形式のパスを基準にする（内容は形式共通）
        prompt_base = job["out_paths"][fmts[0]]

        # セグメントごとの結果を fmt -> (ok, text_or_err) に正規化する。
        # 統合出力は区切り行で分割し、分割できなければ生出力を保存して両形式とも失敗扱い。
        unit_res = []
        for ui, (span, prompt) in enumerate(job["units"]):
            ok, result = resmap.get(ui, (False, "結果なし"))
            if not ok:
                unit_res.append({f: (False, result) for f in fmts})
                continue
            if not merged:
                unit_res.append({fmts[0]: (True, result)})
                continue
            parts = split_merged_output(result)
            if parts is None:
                suffix = (".part%d" % (ui + 1)) if n > 1 else ""
                raw_path = "%s.raw%s.txt" % (prompt_base, suffix)
                with open(raw_path, "w", encoding="utf-8") as f:
                    f.write(result)
                err = "区切り行が無く 2 形式に分割できない（生出力を %s に保存）" % raw_path
                unit_res.append({f: (False, err) for f in fmts})
            else:
                unit_res.append({"project": (True, parts[0]), "tech": (True, parts[1])})

        for fmt in fmts:
            out_path = job["out_paths"][fmt]
            label = "%s/%s_%s" % (fmt, job["pid"], job["date"])
            if n == 1:
                ok, result = unit_res[0][fmt]
                if ok:
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(result + "\n")
                    generated += 1
                else:
                    with open(prompt_base + ".prompt.txt", "w", encoding="utf-8") as f:
                        f.write(job["units"][0][1])
                    sys.stderr.write("[summarize] 失敗(%s): %s -> プロンプトを %s に保存\n"
                                     % (label, result, prompt_base + ".prompt.txt"))
                    failed += 1
                continue

            # 分割ファイル: 各セグメントを時間帯見出し付きで 1 ファイルに連結する
            head = "（ログが長いため時間帯で %d 分割して整理）" % n
            band_blocks = []
            n_ok = 0
            for ui, (span, prompt) in enumerate(job["units"]):
                i = ui + 1
                ok, result = unit_res[ui][fmt]
                header = "---\n## 【時間帯 %d/%d: %s】" % (i, n, span or "")
                if ok:
                    band_blocks.append("%s\n\n%s" % (header, result))
                    n_ok += 1
                else:
                    part_path = "%s.prompt.part%d.txt" % (prompt_base, i)
                    with open(part_path, "w", encoding="utf-8") as f:
                        f.write(prompt)
                    band_blocks.append("%s\n\n（この時間帯の生成に失敗: %s。プロンプトを %s に保存）"
                                       % (header, result, part_path))
            # band 間の重複・矛盾リストを冒頭に挿す（2 セグメント以上成功した場合のみ意味がある）
            blocks = [head]
            if n_ok >= 2:
                blocks.append(reconcile_bands(job["pid"], job["date"], band_blocks))
            blocks.extend(band_blocks)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write("\n\n".join(blocks) + "\n")
            if n_ok == n:
                generated += 1
            else:
                failed += 1
                sys.stderr.write("[summarize] 一部失敗(%s): %d/%d セグメント成功\n"
                                 % (label, n_ok, n))

    sys.stderr.write("[summarize] 生成=%d 失敗=%d スキップ=%d\n" % (generated, failed, skipped))
    # 夜間実行（nightly.sh）が「失敗した日を翌晩に再試行する」判定に使うため、失敗時は非 0 で終了する
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
