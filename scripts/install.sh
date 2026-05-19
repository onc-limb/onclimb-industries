#!/usr/bin/env bash
#
# Copy this repository's .claude/ contents into a target Claude config dir.
#
# Usage:
#   ./scripts/install.sh --user                  # → ~/.claude/
#   ./scripts/install.sh --project <path>        # → <path>/.claude/
#   ./scripts/install.sh -p <path> --dry-run     # preview only
#   ./scripts/install.sh -u --delete             # mirror (remove extras at target)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE_DIR="$REPO_ROOT/.claude"

usage() {
  cat <<EOF
Usage: $(basename "$0") (--user | --project <path>) [--dry-run] [--delete]

Copy contents of ${SOURCE_DIR}/ into the target Claude config directory.
Existing files at the target are overwritten; other files are left alone
unless --delete is passed.

Options:
  -u, --user               Target ~/.claude/ (user-level)
  -p, --project <path>     Target <path>/.claude/ (project-level)
      --dry-run            Show what would change without writing
      --delete             Mirror source exactly (deletes target-only files)
  -h, --help               Show this help
EOF
}

TARGET=""
RSYNC_FLAGS=(-av)

while [[ $# -gt 0 ]]; do
  case "$1" in
    -u|--user)
      TARGET="$HOME/.claude"
      shift
      ;;
    -p|--project)
      [[ $# -ge 2 ]] || { echo "Error: --project requires a path" >&2; exit 1; }
      # Resolve to absolute path
      proj_path="$2"
      if [[ ! -d "$proj_path" ]]; then
        echo "Error: project directory does not exist: $proj_path" >&2
        exit 1
      fi
      TARGET="$(cd "$proj_path" && pwd)/.claude"
      shift 2
      ;;
    --dry-run)
      RSYNC_FLAGS+=(--dry-run)
      shift
      ;;
    --delete)
      RSYNC_FLAGS+=(--delete)
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Error: unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$TARGET" ]]; then
  echo "Error: must specify --user or --project <path>" >&2
  usage
  exit 1
fi

if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "Error: source directory does not exist: $SOURCE_DIR" >&2
  exit 1
fi

# Refuse to clobber the source itself
SOURCE_REAL="$(cd "$SOURCE_DIR" && pwd -P)"
TARGET_PARENT="$(dirname "$TARGET")"
mkdir -p "$TARGET"
TARGET_REAL="$(cd "$TARGET" && pwd -P)"
if [[ "$SOURCE_REAL" == "$TARGET_REAL" ]]; then
  echo "Error: source and target resolve to the same path: $SOURCE_REAL" >&2
  exit 1
fi

echo "Source: $SOURCE_DIR/"
echo "Target: $TARGET/"
if [[ " ${RSYNC_FLAGS[*]} " == *" --dry-run "* ]]; then
  echo "(dry-run — no changes will be made)"
fi
echo

rsync "${RSYNC_FLAGS[@]}" "$SOURCE_DIR/" "$TARGET/"

echo
echo "Done."
