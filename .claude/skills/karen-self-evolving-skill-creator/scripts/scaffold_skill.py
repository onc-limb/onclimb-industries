#!/usr/bin/env python3
"""Scaffold a new self-evolving skill.

assets/skill_template/ を元に新しいスキルを生成する。pipeline.py を子スキル側へコピーし、
logs/ を含む標準レイアウトを構築する。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "assets" / "skill_template"
PIPELINE_SRC = ROOT / "scripts" / "pipeline.py"
EVOLVE_SRC = ROOT / "scripts" / "evolve.py"
SHARED_REFS = ("pipeline_spec.md", "log_schema.md", "evolution_principles.md")

KEBAB_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")

# リポジトリの分類プレフィックス (.claude/skills/README.md / personas/<prefix>.md を参照)
KNOWN_PREFIXES = ("jarvis", "friday", "arc-reactor", "ultron", "edith", "karen", "vision")


def render_template(src: Path, dst: Path, mapping: dict[str, str]) -> None:
    text = src.read_text(encoding="utf-8")
    for key, value in mapping.items():
        text = text.replace("{{" + key + "}}", value)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8")


def copy_shared_reference(name: str, dst_dir: Path) -> None:
    src = ROOT / "references" / name
    if not src.exists():
        return
    dst = dst_dir / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def cmd_scaffold(args: argparse.Namespace) -> int:
    if not KEBAB_RE.match(args.name):
        print(f"error: --name must be kebab-case (got {args.name!r})", file=sys.stderr)
        return 2

    if not args.allow_no_prefix and not any(
        args.name.startswith(prefix + "-") for prefix in KNOWN_PREFIXES
    ):
        print(
            f"error: --name must start with a known prefix {KNOWN_PREFIXES} "
            f"(got {args.name!r}). See .claude/skills/README.md and personas/<prefix>.md, "
            "or pass --allow-no-prefix to bypass.",
            file=sys.stderr,
        )
        return 2

    dest_parent = Path(args.dest).expanduser().resolve()
    if not dest_parent.exists():
        print(f"error: --dest does not exist: {dest_parent}", file=sys.stderr)
        return 2

    skill_root = dest_parent / args.name
    if skill_root.exists():
        if not args.force:
            print(f"error: {skill_root} already exists (use --force to overwrite)", file=sys.stderr)
            return 2
        shutil.rmtree(skill_root)

    skill_root.mkdir(parents=True)
    (skill_root / "scripts").mkdir()
    (skill_root / "references").mkdir()
    (skill_root / "logs" / "artifacts").mkdir(parents=True)
    (skill_root / "logs" / "evolutions").mkdir(parents=True)
    (skill_root / "logs" / "pipeline.jsonl").touch()

    mapping = {
        "SKILL_NAME": args.name,
        "SKILL_DESCRIPTION": args.description,
        "EVOLUTION_THRESHOLD": str(args.threshold),
        "AUTO_APPLY": "true" if args.auto_apply else "false",
    }

    render_template(TEMPLATE_DIR / "SKILL.md.template", skill_root / "SKILL.md", mapping)
    render_template(
        TEMPLATE_DIR / "pipeline.config.json.template",
        skill_root / "pipeline.config.json",
        mapping,
    )
    shutil.copy2(TEMPLATE_DIR / "EVOLUTION.md", skill_root / "EVOLUTION.md")
    shutil.copy2(
        TEMPLATE_DIR / "references" / "user_preferences.md",
        skill_root / "references" / "user_preferences.md",
    )

    shutil.copy2(PIPELINE_SRC, skill_root / "scripts" / "pipeline.py")
    shutil.copy2(EVOLVE_SRC, skill_root / "scripts" / "evolve.py")

    for ref_name in SHARED_REFS:
        copy_shared_reference(ref_name, skill_root / "references")

    # 簡易な README で人手に対して使い方を案内
    readme = skill_root / "README.md"
    readme.write_text(
        "\n".join(
            [
                f"# {args.name}",
                "",
                f"{args.description}",
                "",
                "## 開発者向け",
                "",
                "- 詳細は `SKILL.md` を参照。",
                "- パイプラインは `python scripts/pipeline.py log-start ...` / `log-end ...` で呼ぶ。",
                "- 進化レビュー: `python scripts/evolve.py review`。",
                "- 進化前スナップショット: `python scripts/evolve.py snapshot`。",
                "",
                "## 自己進化ログの場所",
                "",
                "- `logs/pipeline.jsonl` (append-only)",
                "- `logs/artifacts/<cycle_id>/` (大きい生成物)",
                "- `logs/evolutions/<ts>/` (進化前スナップショット & diff)",
                "",
            ]
        ),
        encoding="utf-8",
    )

    summary = {
        "skill_root": str(skill_root),
        "files_created": sorted(
            str(p.relative_to(skill_root))
            for p in skill_root.rglob("*")
            if p.is_file()
        ),
        "next_steps": [
            "SKILL.md の TODO を埋める (トリガー条件・ドメイン固有手順)",
            "evals/ を追加してテストする (任意)",
            "1 サイクル log-start / log-end を実行して logs/pipeline.jsonl が更新されることを確認",
        ],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--name",
        required=True,
        help=f"kebab-case のスキル名。既知プレフィックス {KNOWN_PREFIXES} で始めること",
    )
    parser.add_argument("--dest", required=True, help="親ディレクトリ (生成先)")
    parser.add_argument("--description", required=True, help="SKILL description (トリガー文を含む)")
    parser.add_argument("--threshold", type=int, default=10, help="進化トリガーのサイクル数しきい値")
    parser.add_argument(
        "--auto-apply",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="進化レビュー結果の自動適用 (既定: 有効, --no-auto-apply で無効化)",
    )
    parser.add_argument(
        "--allow-no-prefix",
        action="store_true",
        help="既知プレフィックスで始まらない名前を許可する (原則使わない)",
    )
    parser.add_argument("--force", action="store_true", help="既存ディレクトリを上書き")
    parser.set_defaults(func=cmd_scaffold)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
