#!/usr/bin/env python3
"""worklog MCP サーバー — record.py の薄い stdio ラッパー。

Claude Code / Codex 等の MCP クライアントから worklog イベント
(milestone / blocker) を記録するためのツールを公開する。記録ロジックは
record.record_event() が正本で、ここではプロトコル変換だけを行う。

- トランスポート: stdio（1 行 1 メッセージの JSON-RPC 2.0。常駐せず
  クライアントが都度 spawn する）
- 依存: 標準ライブラリのみ（mcp SDK 不使用。リポジトリの自作優先方針）
- 注意: stdout はプロトコル専用。診断メッセージは一切 stdout に出さないこと
  （record_event は print しない。print するのは record.py の CLI main のみ）
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import record  # noqa: E402

SERVER_INFO = {"name": "worklog-recorder", "version": "0.1.0"}
# クライアントが protocolVersion を申告しなかった場合に返す既定値
# ASSUMPTION: MCP はクライアント申告のバージョンをそのまま受理する運用で
# 問題ない（本サーバーはバージョン間で差の出る機能を使っていない）
PROTOCOL_FALLBACK = "2025-06-18"

_COMMON_PROPS = {
    "project": {
        "type": "string",
        "description": "worklog projects.yaml のプロジェクト id。特定できなければ省略（? で記録される）",
    },
    "agent": {
        "type": "string",
        "description": "記録主体の名前（例: claude-code / codex）。省略時はクライアント名から補完",
    },
    "background": {"type": "string", "description": "なぜこの作業をしたかの背景・文脈"},
    "result": {"type": "string", "description": "結果・現状"},
    "refs": {
        "type": "array", "items": {"type": "string"},
        "description": "関連するファイルパス・PR URL・Issue 等",
    },
}

TOOLS = [
    {
        "name": "record_milestone",
        "description": (
            "作業のひと区切り（実装・修正・調査などの完了）を worklog に記録する。"
            "背景(background)・実施内容(did)・結果(result)を構造化して残し、"
            "日次 digest・日報の骨格になる。まとまった作業を終えるたびに 1 件呼ぶこと。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": dict(
                _COMMON_PROPS,
                did={"type": "string", "description": "実施内容（必須）"},
                blocker={"type": "string", "description": "途中で遭遇した障害（あれば）"},
            ),
            "required": ["did"],
        },
    },
    {
        "name": "record_blocker",
        "description": (
            "作業中に遭遇した障害・エラーをその場で worklog に記録する（解消を待たない）。"
            "blocker にはエラー原文を要約せずそのまま入れること（機密は自動マスキングされる）。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": dict(
                _COMMON_PROPS,
                blocker={"type": "string", "description": "症状・エラー原文（必須。要約しない）"},
                did={"type": "string", "description": "試したこと（あれば）"},
            ),
            "required": ["blocker"],
        },
    },
]

TOOL_KIND = {"record_milestone": "milestone", "record_blocker": "blocker"}


class Server:
    def __init__(self):
        self.default_agent = None  # initialize の clientInfo.name から補完する

    def send(self, payload):
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    def reply(self, msg_id, result):
        self.send({"jsonrpc": "2.0", "id": msg_id, "result": result})

    def reply_error(self, msg_id, code, message):
        self.send({"jsonrpc": "2.0", "id": msg_id,
                   "error": {"code": code, "message": message}})

    def on_initialize(self, params):
        client = (params or {}).get("clientInfo") or {}
        if client.get("name"):
            self.default_agent = str(client["name"])
        return {
            "protocolVersion": (params or {}).get("protocolVersion") or PROTOCOL_FALLBACK,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }

    def on_tools_call(self, params):
        name = (params or {}).get("name")
        args = (params or {}).get("arguments") or {}
        kind = TOOL_KIND.get(name)
        if kind is None:
            raise KeyError("unknown tool: %r" % name)
        refs = args.get("refs")
        if isinstance(refs, str):  # クライアントが文字列で渡してきても受ける
            refs = [refs]
        path, ev = record.record_event(
            kind=kind,
            project=args.get("project"),
            agent=args.get("agent") or self.default_agent,
            background=args.get("background"),
            did=args.get("did"),
            blocker=args.get("blocker"),
            result=args.get("result"),
            refs=refs)
        text = "[record] %s project=%s agent=%s -> %s" % (
            ev["kind"], ev["project"], ev["agent"], path)
        return {"content": [{"type": "text", "text": text}], "isError": False}

    def handle(self, msg):
        method = msg.get("method")
        msg_id = msg.get("id")
        if msg_id is None:  # notification（initialized / cancelled 等）は無応答
            return
        try:
            if method == "initialize":
                self.reply(msg_id, self.on_initialize(msg.get("params")))
            elif method == "ping":
                self.reply(msg_id, {})
            elif method == "tools/list":
                self.reply(msg_id, {"tools": TOOLS})
            elif method == "tools/call":
                try:
                    self.reply(msg_id, self.on_tools_call(msg.get("params")))
                except (ValueError, KeyError) as e:
                    # ツール実行の失敗は JSON-RPC エラーではなく isError で返す（MCP の流儀）
                    self.reply(msg_id, {"content": [{"type": "text", "text": str(e)}],
                                        "isError": True})
            else:
                self.reply_error(msg_id, -32601, "method not found: %s" % method)
        except Exception as e:  # 想定外はプロトコルを壊さずエラー応答で返す
            self.reply_error(msg_id, -32603, "internal error: %s" % e)

    def run(self):
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                self.reply_error(None, -32700, "parse error")
                continue
            self.handle(msg)


if __name__ == "__main__":
    Server().run()
