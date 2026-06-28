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

使い方:
  bin/summarize.py                         # 全プロジェクト×全日付（classified 全体）
  bin/summarize.py 2026-06-22              # 指定日の全プロジェクト
  bin/summarize.py 2026-06-22 jarvis       # 指定日・指定プロジェクト
  bin/summarize.py --formats project 2026-06-22
  bin/summarize.py --dry-run ...           # claude を呼ばずプロンプトだけ生成

claude CLI が見つからない/失敗した場合は、合成プロンプトを digests/<type>/<...>.prompt.txt
に書き出すので、手動で `claude -p < そのファイル` 等で生成できる。
"""
import glob
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worklog_lib as W  # noqa: E402

FORMATS = ["project", "tech"]
OUTPUT_SUBDIR = "digests"  # 「整理された情報」の出力先（最終報告書ではない）
MAX_LOG_CHARS = 180000  # 1 出力あたりのログ投入上限（コンテキスト保護）

BASE_INSTRUCTION = """\
あなたは SES エンジニアの作業ログを「報告書を書くための整理された情報」へ構造化するアシスタントです。
これは最終報告書そのものではありません。後で別の担当（別スキル）がこの整理情報を入力に
きちんとした報告書へ整形します。したがって体裁よりも、情報の網羅・粒度・正確さを優先してください。
以下の作業ログ（Claude Code の操作記録を構造抽出・マスキング済み JSONL を読みやすく整形したもの）を整理してください。

# 厳守事項
1. 残ったノイズ（重複したやり取り、冗長なツール出力、空メッセージ、進捗メッセージ、機械的な反復）は除外する。
2. **過程を必ず残す**: 何を試し、なぜその判断をし、何が失敗し、何が効いたか。最終結果だけは不可。これがこの整理情報の存在理由。
3. 元ログに無い内容を捏造しない。推測が必要な箇所や情報が無い項目は「記録なし」と明示する。
4. 既に <REDACTED:種別> で伏字化された箇所はそのまま伏字のまま扱い、復元を試みない。
5. 出力は Markdown のみ。前置き・後書き・コードフェンス囲みは不要。指定の見出し構成に厳密に従う。
6. 各見出しは箇条書きで具体的に。後で報告書を書く人が困らないよう、固有の事実・数値・コマンド・判断を漏れなく拾う。
7. テンプレ内に表・ステータスラベル（[完了] 等）・サブ見出し（### …）・「状況/結論/根拠」等の小構造が指定されている場合は、その書式に従う。該当する事実が無い項目・セクションは「記録なし」と明記し、見出し自体は省略しない。
8. 時間帯・工数は、作業ログ各行のタイムスタンプ（[HH:MM:SS]）から読み取れる範囲で記載する（無理に推定しない）。

# 出力フォーマット（この構成・見出しで書く）
{template}

# 対象メタ情報
- プロジェクト: {project}
- 日付: {date}

# 作業ログ
{log}
"""


def load_template(name):
    path = os.path.join(W.templates_dir(), "%s.md" % name)
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    # テンプレート説明用の引用注記行（> ...）は出力に含めないよう除去する
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith(">"))


def render_log(entries):
    """JSONL エントリ列を人間可読な時系列テキストへ。"""
    lines = []
    for e in entries:
        ts = (e.get("ts") or "")[11:19]
        kind = e.get("kind")
        tool = e.get("tool")
        body = (e.get("body") or "").strip()
        if not body:
            continue
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
        lines.append("%s\n%s" % (head, body))
    text = "\n\n".join(lines)
    if len(text) > MAX_LOG_CHARS:
        text = text[:MAX_LOG_CHARS] + "\n\n…(ログが長いため以降を省略: 残り %d 文字)" % (len(text) - MAX_LOG_CHARS)
    return text


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


def run_claude(prompt):
    """claude -p をヘッドレス実行。(ok, output_or_error) を返す。"""
    claude = None
    for cand in ("claude",):
        from shutil import which
        claude = which(cand)
        if claude:
            break
    if not claude:
        return False, "claude CLI が見つかりません"
    try:
        proc = subprocess.run(
            [claude, "-p", "--model", "sonnet", "--output-format", "text"],
            input=prompt, capture_output=True, text=True, timeout=600,
        )
    except Exception as e:
        return False, "claude 実行エラー: %s" % e
    if proc.returncode != 0:
        return False, "claude 異常終了(%d): %s" % (proc.returncode, (proc.stderr or "")[:500])
    out = (proc.stdout or "").strip()
    if not out:
        return False, "claude 出力が空"
    return True, out


def parse_args(argv):
    formats = list(FORMATS)
    dry = False
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
        pos.append(a)
        i += 1
    date = pos[0] if len(pos) > 0 else None
    project = pos[1] if len(pos) > 1 else None
    return date, project, formats, dry


def main():
    home = W.worklog_home()
    cls_dir = os.path.join(home, "classified")
    date, project, formats, dry = parse_args(sys.argv[1:])

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
    generated, failed = 0, 0

    for pid, d, path in targets:
        entries = read_entries(path)
        log_text = render_log(entries)
        if not log_text.strip():
            continue
        disp_pid = "未分類" if pid == "_unclassified" else pid
        for fmt in formats:
            out_dir = os.path.join(home, OUTPUT_SUBDIR, fmt)
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, "%s_%s.md" % (pid, d))
            prompt = BASE_INSTRUCTION.format(
                template=templates[fmt], project=disp_pid, date=d, log=log_text,
            )
            if dry:
                with open(out_path + ".prompt.txt", "w", encoding="utf-8") as f:
                    f.write(prompt)
                sys.stderr.write("[summarize] (dry) %s\n" % (out_path + ".prompt.txt"))
                generated += 1
                continue
            sys.stderr.write("[summarize] 生成中 %s/%s ...\n" % (fmt, "%s_%s" % (pid, d)))
            ok, result = run_claude(prompt)
            if ok:
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(result + "\n")
                generated += 1
            else:
                with open(out_path + ".prompt.txt", "w", encoding="utf-8") as f:
                    f.write(prompt)
                sys.stderr.write("[summarize] 失敗(%s): %s -> プロンプトを %s に保存\n"
                                 % (fmt, result, out_path + ".prompt.txt"))
                failed += 1

    sys.stderr.write("[summarize] 生成=%d 失敗=%d\n" % (generated, failed))


if __name__ == "__main__":
    main()
