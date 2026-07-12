#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""knowledge-base スキルの共通ライブラリ（依存ゼロ）。

役割:
  - worklog が生成した digest（特に tech）の置き場を解決する
  - ナレッジベース(vault)の出力先を解決する
  - claude -p のヘッドレス実行ラッパ
  - claude 出力からの寛容な JSON 抽出 / slug 整形 / 最小設定パーサ

worklog スキルと同じリポジトリ内に同居する前提だが、worklog_lib には依存しない
（cross-skill 結合を避けるため、必要な最小限を自前で持つ）。
"""
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from shutil import which

JST = timezone(timedelta(hours=9))


# ---------------------------------------------------------------------------
# パス解決
# ---------------------------------------------------------------------------

def skill_root():
    """このスクリプト群が入るスキルディレクトリ(=bin/ の親)。config/ templates/ の場所。"""
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


def worklog_data_home():
    """worklog の生成データ(digests 等)の基点。worklog_lib.data_home と同じ規則。
    優先: WORKLOG_DATA → WORKLOG_HOME → リポジトリ直下 worklog-data/ → ~/worklog-data。"""
    env = os.environ.get("WORKLOG_DATA") or os.environ.get("WORKLOG_HOME")
    if env:
        return os.path.abspath(os.path.expanduser(env))
    repo = find_repo_root(skill_root())
    if repo:
        return os.path.join(repo, "worklog-data")
    return os.path.expanduser("~/worklog-data")


def digests_dir(fmt="tech"):
    return os.path.join(worklog_data_home(), "digests", fmt)


def capture_data_home():
    """jarvis-capture の生成データ（技術/経験キャプチャノート）の基点。
    優先: CAPTURE_DATA → リポジトリ直下 capture-data/ → ~/capture-data。"""
    env = os.environ.get("CAPTURE_DATA")
    if env:
        return os.path.abspath(os.path.expanduser(env))
    repo = find_repo_root(skill_root())
    if repo:
        return os.path.join(repo, "capture-data")
    return os.path.expanduser("~/capture-data")


def capture_tech_dir():
    return os.path.join(capture_data_home(), "tech")


def kb_home(override=None):
    """ナレッジベース(vault)の出力先。
    優先: 明示引数(--out) → KB_HOME 環境変数 → config の output_dir
          → リポジトリ直下 knowledge-base/ → ~/knowledge-base。
    config の output_dir が相対パスならリポジトリ直下を基準にする。"""
    if override:
        return os.path.abspath(os.path.expanduser(override))
    env = os.environ.get("KB_HOME")
    if env:
        return os.path.abspath(os.path.expanduser(env))
    cfg = load_config()
    out = cfg.get("output_dir")
    repo = find_repo_root(skill_root())
    if out:
        out = os.path.expanduser(out)
        if os.path.isabs(out):
            return out
        base = repo or os.path.expanduser("~")
        return os.path.join(base, out)
    if repo:
        return os.path.join(repo, "knowledge-base")
    return os.path.expanduser("~/knowledge-base")


def templates_dir():
    return os.path.join(skill_root(), "templates")


def load_template(name):
    with open(os.path.join(templates_dir(), "%s.md" % name), "r", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# 最小設定パーサ（kb.yaml は "key: value" のスカラのみ。ブロック/フロー記法は使わない）
# ---------------------------------------------------------------------------

def load_config():
    path = os.path.join(skill_root(), "config", "kb.yaml")
    cfg = {}
    if not os.path.exists(path):
        return cfg
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if line.lstrip().startswith("#") or not line.strip():
                continue
            # 値中に # は使わない前提（インラインコメントを素朴に除去）
            if " #" in line:
                line = line.split(" #", 1)[0]
            if ":" not in line:
                continue
            k, _, v = line.partition(":")
            k, v = k.strip(), v.strip()
            if v == "":
                continue
            low = v.lower()
            if low in ("true", "false"):
                cfg[k] = (low == "true")
            elif re.fullmatch(r"-?\d+", v):
                cfg[k] = int(v)
            else:
                cfg[k] = v.strip('"').strip("'")
    return cfg


# ---------------------------------------------------------------------------
# claude -p
# ---------------------------------------------------------------------------

def run_claude(prompt, timeout=600):
    """claude -p をヘッドレス実行。(ok, output_or_error) を返す。"""
    claude = which("claude")
    if not claude:
        return False, "claude CLI が見つかりません"
    try:
        proc = subprocess.run(
            # ツール使用を禁止し、テキスト生成のみさせる（エージェント的に振る舞い
            # 「書き出しました」等のメタ応答を返す失敗モードの抑止）。
            # --tools "" は組み込みツールの全無効化（claude --help に明記）。
            # ASSUMPTION: --disallowedTools "*" は MCP 等を含む全ツール名にマッチする想定
            #             （フラグ自体は claude --help で確認済みだがパターン仕様は未確認のため併用）。
            [claude, "-p", "--output-format", "text",
             "--tools", "", "--disallowedTools", "*"],
            input=prompt, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, "claude 実行タイムアウト(%ds)" % timeout
    except Exception as e:
        return False, "claude 実行エラー: %s" % e
    if proc.returncode != 0:
        return False, "claude 異常終了(%d): %s" % (proc.returncode, (proc.stderr or "")[:500])
    out = (proc.stdout or "").strip()
    if not out:
        return False, "claude 出力が空"
    return True, out


def run_claude_many(prompts, timeout=600, concurrency=3):
    """複数プロンプトを最大 concurrency 件まで同時に claude へ投げ、
    入力順で [(ok, output_or_error), ...] を返す（worklog/summarize.py と同方式）。"""
    if len(prompts) <= 1:
        return [run_claude(p, timeout=timeout) for p in prompts]
    results = [None] * len(prompts)
    with ThreadPoolExecutor(max_workers=min(concurrency, len(prompts))) as ex:
        futs = {ex.submit(run_claude, p, timeout): idx for idx, p in enumerate(prompts)}
        for fut, idx in futs.items():
            results[idx] = fut.result()
    return results


# ---------------------------------------------------------------------------
# 出力整形ユーティリティ
# ---------------------------------------------------------------------------

def strip_code_fence(text):
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", t)
        t = re.sub(r"\n```\s*$", "", t)
    return t.strip()


def extract_json(text):
    """claude 出力から最初の JSON 値（オブジェクト/配列）を寛容に取り出す。
    前置き・後書き・コードフェンスが混ざっても可能な限り復元する。失敗時は ValueError。"""
    t = strip_code_fence(text)
    candidates = [i for i in (t.find("{"), t.find("[")) if i != -1]
    if not candidates:
        raise ValueError("JSON 開始記号が見つかりません")
    start = min(candidates)
    # raw_decode で先頭の JSON 値だけを取り出す（末尾の余分なテキストを許容・O(n)）
    try:
        obj, _ = json.JSONDecoder().raw_decode(t, start)
        return obj
    except ValueError:
        pass
    # フォールバック: 末尾を縮めながら json.loads を試す（raw_decode で拾えない出力への保険）
    for end in range(len(t), start, -1):
        chunk = t[start:end].strip()
        if not chunk:
            continue
        try:
            return json.loads(chunk)
        except Exception:
            continue
    raise ValueError("有効な JSON を抽出できませんでした")


def slugify(s, fallback="tech"):
    """ASCII の kebab-case slug へ。非 ASCII が落ちて空になったら fallback を返す。"""
    s = (s or "").strip().lower()
    s = s.replace("/", "-").replace("_", "-").replace(".", "-")
    s = re.sub(r"[^a-z0-9-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or fallback


def today_jst():
    # Python スクリプトなので datetime.now は利用可（Workflow JS の制約とは無関係）
    return datetime.now(JST).strftime("%Y-%m-%d")
