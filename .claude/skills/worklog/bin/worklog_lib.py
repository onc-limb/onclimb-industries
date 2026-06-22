#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""worklog 共通ライブラリ。

- 依存パッケージ無しで動かすための最小 YAML サブセットパーサ
  （pyyaml が無い／pip が PEP668 でブロックされる環境を想定）
- 設定ロード、パス展開、マスキング、プロジェクト判定、タイムスタンプ変換

注意: この YAML パーサはブロックスタイル（インデント）のサブセットのみ対応。
      フロースタイル（{a: b}）・複数行スカラ・アンカー等は未対応。
      config/*.yaml はこの制約内で書くこと。
"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

# ---------------------------------------------------------------------------
# 最小 YAML サブセットパーサ
# ---------------------------------------------------------------------------

def _strip_comment(s):
    """クォートを尊重して行末コメント(# ...)を除去する。"""
    out = []
    q = None
    prev = " "
    for c in s:
        if q:
            out.append(c)
            if c == q:
                q = None
        else:
            if c in ('"', "'"):
                q = c
                out.append(c)
            elif c == "#" and prev in (" ", "\t"):
                break
            else:
                out.append(c)
        prev = c
    return "".join(out).rstrip()


def _unescape_double(inner):
    out = []
    i = 0
    mp = {"n": "\n", "t": "\t", "\\": "\\", '"': '"', "'": "'", "/": "/"}
    while i < len(inner):
        c = inner[i]
        if c == "\\" and i + 1 < len(inner) and inner[i + 1] in mp:
            out.append(mp[inner[i + 1]])
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _parse_scalar(s):
    s = s.strip()
    if s == "":
        return None
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return _unescape_double(s[1:-1])
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        return s[1:-1]
    low = s.lower()
    if low in ("null", "~"):
        return None
    if low == "true":
        return True
    if low == "false":
        return False
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s):
        return float(s)
    return s


def _indent_of(line):
    return len(line) - len(line.lstrip(" "))


def _prepare_lines(text):
    out = []
    for raw in text.splitlines():
        stripped = _strip_comment(raw)
        if stripped.strip() == "":
            continue
        out.append((_indent_of(stripped), stripped.strip(), stripped))
    return out


def _parse_block(lines, i, indent):
    if i >= len(lines):
        return None, i
    _, content, _ = lines[i]
    if content == "-" or content.startswith("- "):
        return _parse_seq(lines, i, lines[i][0])
    return _parse_map(lines, i, lines[i][0])


def _parse_map(lines, i, indent):
    d = {}
    while i < len(lines):
        ci, content, _ = lines[i]
        if ci != indent:
            break
        key, sep, rest = content.partition(":")
        if sep == "":
            break
        key = key.strip()
        rest = rest.strip()
        if rest == "":
            if i + 1 < len(lines) and lines[i + 1][0] > indent:
                val, i = _parse_block(lines, i + 1, lines[i + 1][0])
            else:
                val, i = None, i + 1
            d[key] = val
        else:
            d[key] = _parse_scalar(rest)
            i += 1
    return d, i


def _parse_seq(lines, i, indent):
    arr = []
    while i < len(lines):
        ci, content, _ = lines[i]
        if ci != indent or not (content == "-" or content.startswith("- ")):
            break
        item = content[1:].strip()
        if item == "":
            if i + 1 < len(lines) and lines[i + 1][0] > indent:
                val, i = _parse_block(lines, i + 1, lines[i + 1][0])
            else:
                val, i = None, i + 1
            arr.append(val)
        elif ":" in item and not (item.startswith('"') or item.startswith("'")):
            # "- key: value" 形式（シーケンス内マッピング）
            item_indent = indent + (len(content) - len(content[1:].lstrip()))
            sub = [(item_indent, item, item)]
            j = i + 1
            while j < len(lines) and lines[j][0] >= item_indent:
                sub.append(lines[j])
                j += 1
            val, _ = _parse_map(sub, 0, item_indent)
            arr.append(val)
            i = j
        else:
            arr.append(_parse_scalar(item))
            i += 1
    return arr, i


def yaml_load(text):
    lines = _prepare_lines(text)
    if not lines:
        return {}
    val, _ = _parse_block(lines, 0, lines[0][0])
    return val


def yaml_load_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml_load(f.read())


# ---------------------------------------------------------------------------
# パス・設定
# ---------------------------------------------------------------------------

def skill_root():
    """このスクリプト群が入るスキルディレクトリ(=bin/の親)。config/ templates/ が居る場所。"""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def find_repo_root(start):
    d = os.path.abspath(start)
    for _ in range(60):
        if os.path.isdir(os.path.join(d, ".git")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def data_home():
    """データ(raw/classified/reports/archive/logs)を置く場所。
    優先: 環境変数 WORKLOG_DATA → WORKLOG_HOME(後方互換)
          → スキルが属する git リポジトリ直下の worklog-data/
          → ~/worklog-data
    コード/設定とは分離し、生ログをスキルディレクトリの外に置く。"""
    env = os.environ.get("WORKLOG_DATA") or os.environ.get("WORKLOG_HOME")
    if env:
        return os.path.abspath(os.path.expanduser(env))
    repo = find_repo_root(skill_root())
    if repo:
        return os.path.join(repo, "worklog-data")
    return os.path.expanduser("~/worklog-data")


# 後方互換: 旧コードは worklog_home() をデータ基点として使う
def worklog_home():
    return data_home()


def config_path(name):
    return os.path.join(skill_root(), "config", name)


def templates_dir():
    return os.path.join(skill_root(), "templates")


def load_config(name):
    return yaml_load_file(config_path(name))


def expand_path(p):
    if p is None:
        return None
    p = os.path.expandvars(p)
    p = os.path.expanduser(p)
    return p


def current_os():
    if sys.platform.startswith("win"):
        return "windows"
    return "macos" if sys.platform == "darwin" else "linux"


# ---------------------------------------------------------------------------
# マスキング
# ---------------------------------------------------------------------------

class Redactor:
    def __init__(self, cfg):
        self.literals = []
        for it in (cfg.get("literals") or []):
            if not it:
                continue
            self.literals.append((it.get("value", ""), it.get("label", "機密")))
        self.patterns = []
        for it in (cfg.get("patterns") or []):
            if not it:
                continue
            try:
                rx = re.compile(it["regex"])
            except re.error as e:
                sys.stderr.write("[worklog] 不正な正規表現をスキップ: %s (%s)\n" % (it.get("regex"), e))
                continue
            self.patterns.append((rx, it.get("label", "機密"), it.get("group")))

    def apply(self, text):
        if not isinstance(text, str) or not text:
            return text
        for value, label in self.literals:
            if value:
                text = re.sub(re.escape(value), "<REDACTED:%s>" % label, text, flags=re.IGNORECASE)
        for rx, label, group in self.patterns:
            repl = "<REDACTED:%s>" % label
            if group:
                def _sub(m, g=group, r=repl):
                    s = m.group(0)
                    return s.replace(m.group(g), r)
                text = rx.sub(_sub, text)
            else:
                text = rx.sub(repl, text)
        return text


def load_redactor():
    try:
        cfg = load_config("redaction.yaml")
    except FileNotFoundError:
        cfg = {}
    return Redactor(cfg or {})


# ---------------------------------------------------------------------------
# プロジェクト判定
# ---------------------------------------------------------------------------

def git_repo_name(cwd):
    """cwd から git リポジトリ名を推定（.git を上方向に探索）。"""
    if not cwd:
        return None
    d = cwd
    for _ in range(40):
        if os.path.isdir(os.path.join(d, ".git")) or os.path.isfile(os.path.join(d, ".git")):
            return os.path.basename(d)
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


class Classifier:
    def __init__(self, cfg):
        self.projects = cfg.get("projects") or []

    def classify(self, cwd, body_texts):
        """(project_id, reason) を返す。判定不能なら ('未分類', ...)。"""
        cwd = cwd or ""
        # ① cwd パス一致（最優先）
        for p in self.projects:
            for g in (p.get("path_globs") or []):
                if g and (cwd == g or cwd.startswith(g.rstrip("/") + "/") or g in cwd):
                    return p["id"], "cwd:%s" % g
        # ② git リポジトリ名
        repo = git_repo_name(cwd) or (os.path.basename(cwd) if cwd else None)
        if repo:
            for p in self.projects:
                if repo in (p.get("repos") or []):
                    return p["id"], "repo:%s" % repo
        # ③ 本文キーワード（弱い証拠）
        blob = "\n".join(t for t in body_texts if t)[:20000]
        for p in self.projects:
            for kw in (p.get("keywords") or []):
                if kw and kw in blob:
                    return p["id"], "keyword:%s" % kw
        return "未分類", "no-match"


def load_classifier():
    try:
        cfg = load_config("projects.yaml")
    except FileNotFoundError:
        cfg = {}
    return Classifier(cfg or {})


# ---------------------------------------------------------------------------
# タイムスタンプ
# ---------------------------------------------------------------------------

def to_jst_iso(ts):
    """ISO8601(UTC等) を +09:00 表記へ。失敗時は原文を返す。"""
    if not ts:
        return None
    try:
        s = ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(JST).isoformat()
    except Exception:
        return ts


if __name__ == "__main__":
    # 簡易セルフテスト
    for name in ("sources.yaml", "projects.yaml", "redaction.yaml"):
        try:
            cfg = load_config(name)
            print("[OK] %s -> %s keys" % (name, list(cfg.keys()) if isinstance(cfg, dict) else type(cfg)))
        except Exception as e:
            print("[NG] %s -> %s" % (name, e))
