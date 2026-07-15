#!/usr/bin/env python3
"""evalkit.py - LLM application evaluation toolkit (jocasta series).

Collects answers from a target LLM application, scores them against
pre-defined ideal / NG answers (deterministic checks + LLM-as-a-judge),
and generates human-readable reports.

Data layout (git-ignored, default <repo>/llm-eval-data, override with
LLM_EVAL_DATA_DIR):

  llm-eval-data/<app>/
    config.json           app profile, adapter, judge settings
    dataset/cases.json    test cases (ideal points / NG points / checks)
    runs/<run-id>/        immutable run artifacts
      responses.jsonl     collected answers
      judgments.jsonl     LLM judge scores + reasons
      scores.jsonl        merged per-case scores
      summary.json        aggregates
      report.md           human-readable report
    improvements/         improvement records (written by improver skill)

Stdlib only. The LLM judge is invoked through the `claude` CLI.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILLS_DIR = SCRIPT_DIR.parent.parent
REPO_ROOT = SKILLS_DIR.parent.parent
EXAMPLES_DIR = SKILLS_DIR / "jocasta-eval-designer" / "examples"
DATA_DIR = Path(os.environ.get("LLM_EVAL_DATA_DIR", REPO_ROOT / "llm-eval-data"))

KNOWN_METRICS = ("correctness", "completeness", "ng_compliance", "relevancy", "faithfulness")

JUDGE_PROMPT_TEMPLATE = """あなたは LLM アプリケーションの回答を採点する厳密な評価者です。
以下の質問・回答・評価基準を読み、指定されたメトリクスごとに 0.0〜1.0 のスコアと根拠を返してください。

# 対象アプリ
{app_description}

# 質問
{question}
{context_block}
# アプリの回答（採点対象）
{answer}

# 理想回答が含むべき要点（ideal_points）
{ideal_points}
{reference_block}
# してほしくない回答・含んではいけない内容（ng_points）
{ng_points}

# 採点するメトリクス
{metric_definitions}

# 出力形式
次の JSON オブジェクトのみを出力してください（コードフェンスや説明文は不要）。
score は 0.0〜1.0 の数値。reason は日本語で、どの要点を満たした/欠いた・どの NG に抵触したかを具体的に書くこと。

{{
{output_schema}
}}
"""

METRIC_DEFINITIONS = {
    "correctness": "回答内容が事実・理想回答の要点に照らして正しいか。誤情報・矛盾があるほど減点。",
    "completeness": "ideal_points のうちいくつが実質的にカバーされているか。カバー率をスコアに反映する。",
    "ng_compliance": "ng_points に挙げた内容に抵触していないか。1.0=全く抵触なし、抵触が重大なほど 0.0 に近づける。",
    "relevancy": "質問に対して的を射た回答か。無関係な内容・質問のすり替えがあるほど減点。",
    "faithfulness": "提供されたコンテキストに忠実か。コンテキストに無い事実の創作（ハルシネーション）があるほど減点。",
}


def die(msg: str, code: int = 1):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def app_dir(app: str) -> Path:
    return DATA_DIR / app


def load_json(path: Path):
    if not path.exists():
        die(f"file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        die(f"invalid JSON in {path}: {e}")


def load_config(app: str) -> dict:
    return load_json(app_dir(app) / "config.json")


def load_cases(app: str) -> list:
    data = load_json(app_dir(app) / "dataset" / "cases.json")
    return data.get("cases", [])


def write_jsonl(path: Path, rows: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list:
    if not path.exists():
        die(f"file not found: {path} （先に前段のサブコマンドを実行してください）")
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def resolve_run(app: str, run_id: str) -> Path:
    runs_dir = app_dir(app) / "runs"
    if run_id == "latest":
        if not runs_dir.exists():
            die(f"no runs found for app '{app}'")
        runs = sorted(d.name for d in runs_dir.iterdir() if d.is_dir())
        if not runs:
            die(f"no runs found for app '{app}'")
        run_id = runs[-1]
    run_dir = runs_dir / run_id
    if not run_dir.exists():
        die(f"run not found: {run_dir}")
    return run_dir


# ---------------------------------------------------------------- commands


def cmd_list_apps(_args):
    if not DATA_DIR.exists():
        print(f"(no apps yet: {DATA_DIR} が未作成)")
        return
    for d in sorted(DATA_DIR.iterdir()):
        if d.is_dir() and (d / "config.json").exists():
            cfg = json.loads((d / "config.json").read_text(encoding="utf-8"))
            n_cases = 0
            cases_path = d / "dataset" / "cases.json"
            if cases_path.exists():
                n_cases = len(json.loads(cases_path.read_text(encoding="utf-8")).get("cases", []))
            runs_dir = d / "runs"
            n_runs = len([r for r in runs_dir.iterdir() if r.is_dir()]) if runs_dir.exists() else 0
            print(f"{d.name}\tcases={n_cases}\truns={n_runs}\t{cfg.get('app', {}).get('description', '')}")


def cmd_init(args):
    target = app_dir(args.app)
    if target.exists():
        die(f"app '{args.app}' already exists: {target}")
    if args.from_example:
        src = EXAMPLES_DIR / args.from_example
        if not src.exists():
            avail = ", ".join(d.name for d in EXAMPLES_DIR.iterdir() if d.is_dir()) if EXAMPLES_DIR.exists() else "(none)"
            die(f"example not found: {src}\navailable: {avail}")
        shutil.copytree(src, target)
        print(f"initialized '{args.app}' from example '{args.from_example}' at {target}")
    else:
        (target / "dataset").mkdir(parents=True)
        (target / "runs").mkdir()
        (target / "improvements").mkdir()
        config = {
            "app": {"name": args.app, "description": "TODO: アプリの説明"},
            "adapter": {
                "type": "manual",
                "command": None,
                "timeout_sec": 120,
            },
            "judge": {
                "command": ["claude", "-p", "--model", "claude-sonnet-5", "--output-format", "json"],
                "metrics": ["correctness", "completeness", "ng_compliance", "relevancy"],
                "weights": {"correctness": 0.35, "completeness": 0.25, "ng_compliance": 0.25, "relevancy": 0.15},
                "pass_threshold": 0.7,
            },
        }
        (target / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (target / "dataset" / "cases.json").write_text(json.dumps({"cases": []}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"initialized empty app '{args.app}' at {target}")
        print("次: jocasta-eval-designer でケースを作成するか dataset/cases.json を編集してください")


def cmd_validate(args):
    errors, warnings = [], []
    cfg = load_config(args.app)
    adapter = cfg.get("adapter", {})
    judge = cfg.get("judge", {})
    if adapter.get("type") not in ("command", "http", "manual"):
        errors.append(f"adapter.type must be command|http|manual, got: {adapter.get('type')}")
    if adapter.get("type") == "command" and not adapter.get("command"):
        errors.append("adapter.type=command には adapter.command が必要")
    if adapter.get("type") == "http" and not adapter.get("url"):
        errors.append("adapter.type=http には adapter.url が必要")
    metrics = judge.get("metrics", [])
    if not metrics:
        errors.append("judge.metrics が空")
    for m in metrics:
        if m not in KNOWN_METRICS:
            errors.append(f"unknown metric: {m} (known: {', '.join(KNOWN_METRICS)})")
    weights = judge.get("weights", {})
    missing_w = [m for m in metrics if m not in weights]
    if missing_w:
        warnings.append(f"weights 未指定のメトリクス（均等割で補完されます）: {', '.join(missing_w)}")

    cases = load_cases(args.app)
    if not cases:
        errors.append("dataset/cases.json に cases がありません")
    seen_ids = set()
    for i, c in enumerate(cases):
        cid = c.get("id") or f"(index {i})"
        if not c.get("id"):
            errors.append(f"case {cid}: id がありません")
        elif c["id"] in seen_ids:
            errors.append(f"case {cid}: id が重複しています")
        else:
            seen_ids.add(c["id"])
        if not c.get("question"):
            errors.append(f"case {cid}: question がありません")
        if not c.get("ideal_points") and not c.get("reference_answer"):
            warnings.append(f"case {cid}: ideal_points も reference_answer も無く、correctness/completeness の判定根拠が弱い")
        if "faithfulness" in metrics and not c.get("context"):
            warnings.append(f"case {cid}: faithfulness を測る設定ですが context がありません（このケースでは skip されます）")

    for e in errors:
        print(f"ERROR: {e}")
    for w in warnings:
        print(f"WARN:  {w}")
    if not errors:
        print(f"OK: config + {len(cases)} cases")
    sys.exit(1 if errors else 0)


def run_adapter(cfg: dict, question: str, app: str) -> str:
    adapter = cfg["adapter"]
    timeout = adapter.get("timeout_sec", 120)
    if adapter["type"] == "command":
        cmd = adapter["command"]
        if isinstance(cmd, str):
            cmd = ["bash", "-c", cmd]
        proc = subprocess.run(
            cmd, input=question, capture_output=True, text=True,
            timeout=timeout, cwd=app_dir(app),
        )
        if proc.returncode != 0:
            raise RuntimeError(f"adapter command failed (exit {proc.returncode}): {proc.stderr.strip()[:500]}")
        return proc.stdout.strip()
    if adapter["type"] == "http":
        template = adapter.get("request_template", {"question": "{question}"})
        body = json.loads(json.dumps(template, ensure_ascii=False).replace("{question}", json.dumps(question, ensure_ascii=False)[1:-1]))
        req = urllib.request.Request(
            adapter["url"],
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", **adapter.get("headers", {})},
            method=adapter.get("method", "POST"),
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        answer = payload
        for key in adapter.get("response_path", "answer").split("."):
            answer = answer[key]
        return str(answer)
    raise RuntimeError("adapter.type=manual では collect は使えません。responses.jsonl を手動で用意し score から実行してください")


def cmd_collect(args):
    cfg = load_config(args.app)
    cases = load_cases(args.app)
    if not cases:
        die("cases が空です。先に jocasta-eval-designer でデータセットを作成してください")
    if cfg["adapter"]["type"] == "manual":
        die("adapter.type=manual のため collect は使えません。runs/<run-id>/responses.jsonl を手動で配置してください")
    if args.case:
        cases = [c for c in cases if c["id"] in args.case]
        if not cases:
            die(f"指定 id のケースが見つかりません: {args.case}")

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = app_dir(args.app) / "runs" / run_id
    rows = []
    print(f"run {run_id}: {len(cases)} cases を収集します")
    for c in cases:
        start = time.time()
        row = {"case_id": c["id"], "question": c["question"]}
        try:
            row["answer"] = run_adapter(cfg, c["question"], args.app)
            row["error"] = None
        except Exception as e:  # noqa: BLE001 - record and continue
            row["answer"] = None
            row["error"] = str(e)
        row["latency_ms"] = int((time.time() - start) * 1000)
        status = "ok" if not row["error"] else f"ERROR: {row['error'][:80]}"
        print(f"  {c['id']}: {status} ({row['latency_ms']}ms)")
        rows.append(row)
    write_jsonl(run_dir / "responses.jsonl", rows)
    meta = {"run_id": run_id, "collected_at": datetime.now().isoformat(timespec="seconds"),
            "note": args.note, "n_cases": len(rows),
            "n_errors": sum(1 for r in rows if r["error"])}
    (run_dir / "run.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"saved: {run_dir / 'responses.jsonl'}")
    print(f"次: evalkit.py judge {args.app} --run {run_id}")


def case_metrics(cfg: dict, case: dict) -> list:
    metrics = list(cfg["judge"]["metrics"])
    if "faithfulness" in metrics and not case.get("context"):
        metrics.remove("faithfulness")
    return metrics


def build_judge_prompt(cfg: dict, case: dict, answer: str) -> str:
    metrics = case_metrics(cfg, case)
    context_block = ""
    if case.get("context"):
        context_block = f"\n# アプリに与えられたコンテキスト（検索結果など）\n{case['context']}\n"
    reference_block = ""
    if case.get("reference_answer"):
        reference_block = f"\n# 参考: 理想回答の全文（reference_answer）\n{case['reference_answer']}\n"
    ideal = "\n".join(f"- {p}" for p in case.get("ideal_points", [])) or "（定義なし）"
    ng = "\n".join(f"- {p}" for p in case.get("ng_points", [])) or "（定義なし）"
    defs = "\n".join(f"- {m}: {METRIC_DEFINITIONS[m]}" for m in metrics)
    schema = ",\n".join(f'  "{m}": {{"score": 0.0, "reason": "..."}}' for m in metrics)
    return JUDGE_PROMPT_TEMPLATE.format(
        app_description=cfg["app"].get("description", ""),
        question=case["question"],
        context_block=context_block,
        answer=answer,
        ideal_points=ideal,
        reference_block=reference_block,
        ng_points=ng,
        metric_definitions=defs,
        output_schema=schema,
    )


def extract_json_object(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        brace = re.search(r"\{.*\}", text, re.DOTALL)
        if brace:
            text = brace.group(0)
    return json.loads(text)


def call_judge(cfg: dict, prompt: str) -> dict:
    cmd = cfg["judge"].get("command") or ["claude", "-p", "--model", "claude-sonnet-5", "--output-format", "json"]
    proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                          timeout=cfg["judge"].get("timeout_sec", 300))
    if proc.returncode != 0:
        raise RuntimeError(f"judge command failed (exit {proc.returncode}): {proc.stderr.strip()[:500]}")
    out = proc.stdout.strip()
    # claude --output-format json wraps the answer in an envelope with a "result" field
    try:
        envelope = json.loads(out)
        if isinstance(envelope, dict) and "result" in envelope:
            out = envelope["result"]
    except json.JSONDecodeError:
        pass
    return extract_json_object(out)


def cmd_judge(args):
    cfg = load_config(args.app)
    cases = {c["id"]: c for c in load_cases(args.app)}
    run_dir = resolve_run(args.app, args.run)
    responses = read_jsonl(run_dir / "responses.jsonl")

    if args.export_prompts:
        prompts_dir = run_dir / "judge-prompts"
        prompts_dir.mkdir(exist_ok=True)
        n = 0
        for r in responses:
            if r.get("error") or r["case_id"] not in cases:
                continue
            prompt = build_judge_prompt(cfg, cases[r["case_id"]], r["answer"])
            (prompts_dir / f"{r['case_id']}.txt").write_text(prompt, encoding="utf-8")
            n += 1
        print(f"exported {n} judge prompts to {prompts_dir}")
        print("各プロンプトの判定 JSON を judgments.jsonl（{'case_id':..., 'metrics': {...}} 形式）に集約してください")
        return

    rows = []
    for r in responses:
        cid = r["case_id"]
        if r.get("error"):
            print(f"  {cid}: skip（collect 時エラー）")
            continue
        if cid not in cases:
            print(f"  {cid}: skip（dataset に存在しない）")
            continue
        prompt = build_judge_prompt(cfg, cases[cid], r["answer"])
        try:
            result = call_judge(cfg, prompt)
            metrics = {}
            for m in case_metrics(cfg, cases[cid]):
                entry = result.get(m, {})
                metrics[m] = {"score": max(0.0, min(1.0, float(entry.get("score", 0.0)))),
                              "reason": str(entry.get("reason", ""))}
            rows.append({"case_id": cid, "metrics": metrics, "error": None})
            avg = sum(v["score"] for v in metrics.values()) / max(len(metrics), 1)
            print(f"  {cid}: judged (mean {avg:.2f})")
        except Exception as e:  # noqa: BLE001 - record and continue
            rows.append({"case_id": cid, "metrics": {}, "error": str(e)})
            print(f"  {cid}: ERROR: {str(e)[:120]}")
    write_jsonl(run_dir / "judgments.jsonl", rows)
    print(f"saved: {run_dir / 'judgments.jsonl'}")
    print(f"次: evalkit.py score {args.app} --run {run_dir.name}")


def deterministic_checks(case: dict, answer: str) -> dict:
    checks = case.get("checks", {}) or {}
    violations = []
    for kw in checks.get("must_include", []):
        if kw not in answer:
            violations.append(f"must_include 未達: 「{kw}」が含まれていない")
    for kw in checks.get("must_not_include", []):
        if kw in answer:
            violations.append(f"must_not_include 抵触: 「{kw}」が含まれている")
    max_chars = checks.get("max_chars")
    if max_chars and len(answer) > max_chars:
        violations.append(f"max_chars 超過: {len(answer)} > {max_chars}")
    n_rules = len(checks.get("must_include", [])) + len(checks.get("must_not_include", [])) + (1 if max_chars else 0)
    return {"n_rules": n_rules, "violations": violations,
            "score": 1.0 if n_rules == 0 else (n_rules - len(violations)) / n_rules}


def cmd_score(args):
    cfg = load_config(args.app)
    cases = {c["id"]: c for c in load_cases(args.app)}
    run_dir = resolve_run(args.app, args.run)
    responses = {r["case_id"]: r for r in read_jsonl(run_dir / "responses.jsonl")}
    judgments = {j["case_id"]: j for j in read_jsonl(run_dir / "judgments.jsonl")}
    weights = dict(cfg["judge"].get("weights", {}))
    threshold = cfg["judge"].get("pass_threshold", 0.7)

    rows = []
    not_collected = [cid for cid in cases if cid not in responses]
    for cid, resp in responses.items():
        case = cases.get(cid)
        if not case:
            print(f"  {cid}: skip（dataset に存在しない。dataset が run 後に変更された可能性）")
            continue
        if resp.get("error") or cid not in judgments or judgments[cid].get("error"):
            reason = "collect エラー" if resp.get("error") else "judge 未実施/エラー"
            rows.append({"case_id": cid, "status": "error", "error": reason,
                         "overall": 0.0, "passed": False, "metrics": {}, "deterministic": None})
            continue
        judged = judgments[cid]["metrics"]
        det = deterministic_checks(case, resp["answer"])
        used_metrics = list(judged.keys())
        w = {m: weights.get(m) for m in used_metrics}
        unassigned = [m for m in used_metrics if w[m] is None]
        remaining = max(0.0, 1.0 - sum(v for v in w.values() if v is not None))
        for m in unassigned:
            w[m] = remaining / len(unassigned) if unassigned else 0.0
        total_w = sum(w.values()) or 1.0
        judge_score = sum(judged[m]["score"] * w[m] for m in used_metrics) / total_w
        # deterministic violations cap the overall score: hard rules broken = not acceptable
        overall = judge_score * det["score"]
        rows.append({
            "case_id": cid, "status": "ok", "error": None,
            "metrics": judged, "deterministic": det,
            "judge_score": round(judge_score, 3),
            "overall": round(overall, 3),
            "passed": overall >= threshold,
            "boundary": abs(overall - threshold) <= 0.1,
            "tags": case.get("tags", []),
        })
    write_jsonl(run_dir / "scores.jsonl", rows)

    ok_rows = [r for r in rows if r["status"] == "ok"]
    metric_means = {}
    for m in KNOWN_METRICS:
        vals = [r["metrics"][m]["score"] for r in ok_rows if m in r["metrics"]]
        if vals:
            metric_means[m] = round(sum(vals) / len(vals), 3)
    summary = {
        "run_id": run_dir.name,
        "scored_at": datetime.now().isoformat(timespec="seconds"),
        "n_cases": len(rows),
        "n_errors": len(rows) - len(ok_rows),
        "n_not_collected": len(not_collected),
        "pass_threshold": threshold,
        "pass_rate": round(sum(1 for r in ok_rows if r["passed"]) / len(ok_rows), 3) if ok_rows else 0.0,
        "overall_mean": round(sum(r["overall"] for r in ok_rows) / len(ok_rows), 3) if ok_rows else 0.0,
        "metric_means": metric_means,
        "n_boundary": sum(1 for r in ok_rows if r.get("boundary")),
        "n_deterministic_violations": sum(len(r["deterministic"]["violations"]) for r in ok_rows if r["deterministic"]),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"次: evalkit.py report {args.app} --run {run_dir.name}")


def cmd_report(args):
    cfg = load_config(args.app)
    cases = {c["id"]: c for c in load_cases(args.app)}
    run_dir = resolve_run(args.app, args.run)
    responses = {r["case_id"]: r for r in read_jsonl(run_dir / "responses.jsonl")}
    scores = read_jsonl(run_dir / "scores.jsonl")
    summary = load_json(run_dir / "summary.json")
    meta = load_json(run_dir / "run.json") if (run_dir / "run.json").exists() else {}

    lines = []
    lines.append(f"# 評価レポート: {cfg['app']['name']} — run {run_dir.name}")
    lines.append("")
    if meta.get("note"):
        lines.append(f"> note: {meta['note']}")
        lines.append("")
    lines.append("## サマリ")
    lines.append("")
    lines.append(f"- 総合スコア（平均）: **{summary['overall_mean']}** / pass 率: **{summary['pass_rate']}**（閾値 {summary['pass_threshold']}）")
    lines.append(f"- ケース数: {summary['n_cases']}（エラー {summary['n_errors']} / 境界 {summary['n_boundary']} / 決定的チェック違反 {summary['n_deterministic_violations']} 件 / 未収集 {summary.get('n_not_collected', 0)}）")
    lines.append(f"- メトリクス平均: " + " / ".join(f"{m}={v}" for m, v in summary["metric_means"].items()))
    lines.append("")
    lines.append("## ケース別スコア（低い順）")
    lines.append("")
    metric_names = [m for m in KNOWN_METRICS if m in summary["metric_means"]]
    header = "| case | overall | pass | " + " | ".join(metric_names) + " | 決定的違反 |"
    lines.append(header)
    lines.append("|" + "---|" * (len(metric_names) + 4))
    for r in sorted(scores, key=lambda x: x["overall"]):
        if r["status"] != "ok":
            lines.append(f"| {r['case_id']} | - | ERROR({r['error']}) | " + " | ".join("-" for _ in metric_names) + " | - |")
            continue
        flags = "✅" if r["passed"] else "❌"
        if r.get("boundary"):
            flags += " ⚠️境界"
        cells = " | ".join(f"{r['metrics'][m]['score']:.2f}" if m in r["metrics"] else "-" for m in metric_names)
        n_v = len(r["deterministic"]["violations"]) if r["deterministic"] else 0
        lines.append(f"| {r['case_id']} | {r['overall']:.2f} | {flags} | {cells} | {n_v} |")
    lines.append("")

    worst = [r for r in sorted(scores, key=lambda x: x["overall"]) if r["status"] == "ok"][:args.detail]
    lines.append(f"## ワースト {len(worst)} ケース詳細")
    lines.append("")
    for r in worst:
        case = cases.get(r["case_id"], {})
        resp = responses.get(r["case_id"], {})
        lines.append(f"### {r['case_id']} — overall {r['overall']:.2f} {'✅' if r['passed'] else '❌'}")
        lines.append("")
        lines.append(f"**質問**: {case.get('question', '')}")
        lines.append("")
        answer = (resp.get("answer") or "")
        if len(answer) > 800:
            answer = answer[:800] + "…（省略）"
        lines.append(f"**回答**:\n\n> " + answer.replace("\n", "\n> "))
        lines.append("")
        for m, v in r["metrics"].items():
            lines.append(f"- **{m}={v['score']:.2f}**: {v['reason']}")
        if r["deterministic"] and r["deterministic"]["violations"]:
            for v in r["deterministic"]["violations"]:
                lines.append(f"- **決定的チェック違反**: {v}")
        lines.append("")

    boundary = [r for r in scores if r.get("boundary")]
    if boundary:
        lines.append("## 境界ケース（判定が揺らぎうる）")
        lines.append("")
        lines.append("閾値±0.1 のケース。再判定でスコアが変わる可能性があるため、壁打ちで中身を確認する優先候補。")
        lines.append("")
        for r in boundary:
            lines.append(f"- {r['case_id']} (overall {r['overall']:.2f})")
        lines.append("")

    lines.append("## 次のアクション")
    lines.append("")
    lines.append("このレポートを入力に `jocasta-eval-improver` で壁打ちし、次のいずれかへ落とし込む:")
    lines.append("")
    lines.append("1. アプリ側の改善（プロンプト・検索・後処理の修正案）")
    lines.append("2. データセット側の見直し（理想回答・NG 定義・質問文の妥当性）")
    lines.append("3. 再測定（改善後に `evalkit.py collect` から新しい run を取り compare する）")
    lines.append("")

    report_path = run_dir / "report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"saved: {report_path}")


def cmd_compare(args):
    run_a = resolve_run(args.app, args.runs[0])
    run_b = resolve_run(args.app, args.runs[1])
    sum_a = load_json(run_a / "summary.json")
    sum_b = load_json(run_b / "summary.json")
    scores_a = {r["case_id"]: r for r in read_jsonl(run_a / "scores.jsonl")}
    scores_b = {r["case_id"]: r for r in read_jsonl(run_b / "scores.jsonl")}

    print(f"# compare: {run_a.name} → {run_b.name}\n")
    print(f"| 指標 | {run_a.name} | {run_b.name} | Δ |")
    print("|---|---|---|---|")
    for key in ("overall_mean", "pass_rate"):
        d = round(sum_b[key] - sum_a[key], 3)
        print(f"| {key} | {sum_a[key]} | {sum_b[key]} | {'+' if d >= 0 else ''}{d} |")
    all_metrics = sorted(set(sum_a["metric_means"]) | set(sum_b["metric_means"]))
    for m in all_metrics:
        va, vb = sum_a["metric_means"].get(m), sum_b["metric_means"].get(m)
        if va is None or vb is None:
            continue
        d = round(vb - va, 3)
        print(f"| {m} | {va} | {vb} | {'+' if d >= 0 else ''}{d} |")
    print()
    moved = []
    for cid in sorted(set(scores_a) & set(scores_b)):
        a, b = scores_a[cid], scores_b[cid]
        if a["status"] != "ok" or b["status"] != "ok":
            continue
        d = round(b["overall"] - a["overall"], 3)
        if abs(d) >= 0.05:
            moved.append((d, cid, a["overall"], b["overall"]))
    if moved:
        print("## 変動したケース（|Δ| >= 0.05）\n")
        for d, cid, oa, ob in sorted(moved):
            print(f"- {cid}: {oa:.2f} → {ob:.2f} ({'+' if d >= 0 else ''}{d})")


def main():
    parser = argparse.ArgumentParser(description="LLM application evaluation toolkit (jocasta)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list-apps", help="登録済みアプリの一覧")

    p = sub.add_parser("init", help="アプリの評価環境を作成")
    p.add_argument("app")
    p.add_argument("--from-example", help="jocasta-eval-designer/examples/ の例から作成")

    p = sub.add_parser("validate", help="config と dataset の整合チェック")
    p.add_argument("app")

    p = sub.add_parser("collect", help="アダプタ経由で全ケースの回答を収集し新しい run を作る")
    p.add_argument("app")
    p.add_argument("--case", action="append", help="特定ケースのみ（複数指定可）")
    p.add_argument("--note", help="run のメモ（何を変えた後の測定か）")

    p = sub.add_parser("judge", help="LLM-as-a-judge で採点（claude CLI 使用）")
    p.add_argument("app")
    p.add_argument("--run", default="latest")
    p.add_argument("--export-prompts", action="store_true",
                   help="claude CLI を呼ばずジャッジ用プロンプトをファイル出力する（セッション内判定用）")

    p = sub.add_parser("score", help="決定的チェックと judge 結果を統合しスコア確定")
    p.add_argument("app")
    p.add_argument("--run", default="latest")

    p = sub.add_parser("report", help="run のレポート（report.md）を生成")
    p.add_argument("app")
    p.add_argument("--run", default="latest")
    p.add_argument("--detail", type=int, default=3, help="詳細を載せるワーストケース数")

    p = sub.add_parser("compare", help="2 つの run を比較")
    p.add_argument("app")
    p.add_argument("--runs", nargs=2, required=True, metavar=("RUN_A", "RUN_B"))

    args = parser.parse_args()
    {
        "list-apps": cmd_list_apps,
        "init": cmd_init,
        "validate": cmd_validate,
        "collect": cmd_collect,
        "judge": cmd_judge,
        "score": cmd_score,
        "report": cmd_report,
        "compare": cmd_compare,
    }[args.command](args)


if __name__ == "__main__":
    main()
