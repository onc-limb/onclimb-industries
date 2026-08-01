#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collect 本体（collect.sh から呼ばれる）。

複数ソースの生 JSONL を走査し、
  1) 内部メタデータを捨てて user/assistant/tool_use/tool_result(/thinking) のみ抽出
  2) redaction.yaml のマスキングを適用
  3) §4 構造へ変換し raw/YYYY-MM-DD.jsonl(JST) へ追記
を行う。raw/.cursor で取り込み済みバイト位置を管理し、冪等に再実行できる
（サイズ不変のファイルは読まずにスキップ、追記分だけ seek して読む）。
SessionEnd Hook / 毎日 cron / PreCompact Hook / 手動、どこから呼ばれても安全。
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worklog_lib as W  # noqa: E402

MAX_BODY = 4000  # tool_result 等の本文上限（ノイズ抑制）

# 抽出対象外（=ノイズ）の type
SKIP_TYPES = {
    "attachment", "file-history-snapshot", "mode", "permission-mode",
    "system", "last-prompt", "summary", "skill-list",
}


def truncate(s):
    if isinstance(s, str) and len(s) > MAX_BODY:
        return s[:MAX_BODY] + "\n…(truncated %d chars)" % (len(s) - MAX_BODY)
    return s


def tool_use_body(name, inp):
    inp = inp or {}
    try:
        if name == "Bash":
            cmd = inp.get("command", "")
            desc = inp.get("description")
            return ("# %s\n%s" % (desc, cmd)) if desc else cmd
        if name in ("Read", "Write", "Edit", "NotebookEdit"):
            fp = inp.get("file_path") or inp.get("notebook_path") or ""
            if name == "Edit":
                return "%s\n[old] %s\n[new] %s" % (fp, inp.get("old_string", "")[:400], inp.get("new_string", "")[:400])
            if name == "Write":
                return "%s\n%s" % (fp, str(inp.get("content", ""))[:600])
            return fp
        if name in ("Grep", "Glob"):
            return "pattern=%s path=%s" % (inp.get("pattern", ""), inp.get("path", ""))
        return json.dumps(inp, ensure_ascii=False)[:MAX_BODY]
    except Exception:
        return str(inp)[:MAX_BODY]


def tool_result_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for it in content:
            if isinstance(it, dict):
                parts.append(it.get("text") or it.get("content") or "")
            else:
                parts.append(str(it))
        return "\n".join(p for p in parts if p)
    return str(content) if content is not None else ""


def extract_entries(obj, source, redactor):
    """JSONL 1 行(obj) を §4 エントリのリストに変換。対象外なら []。"""
    typ = obj.get("type")
    if typ in SKIP_TYPES or typ not in ("user", "assistant"):
        return []
    msg = obj.get("message") or {}
    role = msg.get("role") or ("assistant" if typ == "assistant" else "user")
    ts = W.to_jst_iso(obj.get("timestamp"))
    cwd = obj.get("cwd")
    sid = obj.get("sessionId")
    content = msg.get("content")
    base = {
        "ts": ts, "source": source, "session_id": sid,
        "project_id": "未分類", "cwd": cwd, "role": role,
    }
    out = []

    def emit(kind, tool, body):
        if body is None or (isinstance(body, str) and body.strip() == ""):
            return
        e = dict(base)
        e["kind"] = kind
        e["tool"] = tool
        e["body"] = redactor.apply(truncate(body))
        out.append(e)

    if isinstance(content, str):
        emit("instruction" if role == "user" else "response", None, content)
        return out

    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            it = item.get("type")
            if it == "text":
                emit("instruction" if role == "user" else "response", None, item.get("text"))
            elif it == "thinking":
                emit("response", None, item.get("thinking"))
            elif it == "tool_use":
                emit("tool_use", item.get("name"), tool_use_body(item.get("name"), item.get("input")))
            elif it == "tool_result":
                emit("tool_result", None, tool_result_text(item.get("content")))
    return out


def iter_cli_files(path):
    for f in glob.glob(os.path.join(path, "**", "*.jsonl"), recursive=True):
        yield f


def build_desktop_sessions(sources):
    """desktop_meta からデスクトップ由来の cliSessionId 集合を作る（source 判定に使う）。"""
    ids = set()
    for src in sources:
        if src.get("type") != "desktop_meta":
            continue
        if src.get("os") not in (W.current_os(), "any", None):
            continue
        root = W.expand_path(src.get("path"))
        if not root or not os.path.isdir(root):
            continue
        for f in glob.glob(os.path.join(root, "**", "*.json"), recursive=True):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    o = json.load(fh)
            except Exception:
                continue
            cli_sid = o.get("cliSessionId") or o.get("sessionId")
            if cli_sid:
                ids.add(cli_sid)
    return ids


def load_cursor(home):
    cpath = os.path.join(home, "raw", ".cursor")
    if os.path.isfile(cpath):
        try:
            with open(cpath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cursor(home, cursor):
    cpath = os.path.join(home, "raw", ".cursor")
    tmp = cpath + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cursor, f, ensure_ascii=False, indent=0)
    os.replace(tmp, cpath)


def main():
    home = W.worklog_home()
    raw_dir = os.path.join(home, "raw")
    os.makedirs(raw_dir, exist_ok=True)
    cfg = W.load_config("sources.yaml")
    sources = cfg.get("sources") or []
    redactor = W.load_redactor()
    cursor = load_cursor(home)
    desktop = build_desktop_sessions(sources)

    writers = {}  # date -> file handle

    def writer_for(date):
        if date not in writers:
            writers[date] = open(os.path.join(raw_dir, "%s.jsonl" % date), "a", encoding="utf-8")
        return writers[date]

    total_new = 0
    files_seen = 0
    for src in sources:
        if src.get("type") != "cli_jsonl":
            continue
        if src.get("os") not in (W.current_os(), "any", None):
            continue
        root = W.expand_path(src.get("path"))
        if not root or not os.path.isdir(root):
            sys.stderr.write("[collect] パス無し(skip): %s\n" % root)
            continue
        src_tag = src.get("tag")  # 明示タグがあれば source として優先する
        for fpath in iter_cli_files(root):
            files_seen += 1
            # カーソルは {"offset": 取り込み済みバイト位置, "size": 前回サイズ}。
            # サイズが変わっていなければ開かずにスキップし、増えていれば追記分だけ seek して読む。
            cur = cursor.get(fpath)
            try:
                size = os.path.getsize(fpath)
            except OSError as e:
                sys.stderr.write("[collect] 読込失敗 %s: %s\n" % (fpath, e))
                continue
            skip_lines = 0
            if isinstance(cur, dict):
                offset = int(cur.get("offset") or 0)
                if size == int(cur.get("size") or 0):
                    continue
                if size < offset:
                    offset = 0  # 縮んだ＝書き直された可能性があるので最初から読み直す
            elif isinstance(cur, int):
                # 旧形式（取り込み済み行数）からの移行: 一度だけ全読みして行数分スキップし、
                # 保存時にバイト位置の新形式へ置き換える
                offset = 0
                skip_lines = cur
            else:
                offset = 0
            try:
                with open(fpath, "rb") as fh:
                    fh.seek(offset)
                    data = fh.read()
            except Exception as e:
                sys.stderr.write("[collect] 読込失敗 %s: %s\n" % (fpath, e))
                continue
            lines = data.decode("utf-8", errors="replace").splitlines()
            if skip_lines:
                lines = lines[skip_lines:]
            for ln in lines:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    obj = json.loads(ln)
                except Exception:
                    continue
                sid = obj.get("sessionId")
                source = src_tag or ("desktop" if sid in desktop else "cli")
                for e in extract_entries(obj, source, redactor):
                    date = (e["ts"] or "")[:10] or "0000-00-00"
                    if not date or date == "0000-00-00":
                        date = "undated"
                    writer_for(date).write(json.dumps(e, ensure_ascii=False) + "\n")
                    total_new += 1
            pos = offset + len(data)  # 実際に読み終えたバイト位置（getsize 後の追記も含む）
            cursor[fpath] = {"offset": pos, "size": pos}

    for fh in writers.values():
        fh.close()
    save_cursor(home, cursor)
    sys.stderr.write("[collect] files=%d new_entries=%d -> %s\n" % (files_seen, total_new, raw_dir))


if __name__ == "__main__":
    main()
