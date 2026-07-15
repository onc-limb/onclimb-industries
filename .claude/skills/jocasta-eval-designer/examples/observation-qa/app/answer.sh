#!/usr/bin/env bash
# Sample target app: climbing observation Q&A backed by the claude CLI.
# Reads the question from stdin and prints the answer to stdout.
set -euo pipefail

dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
question="$(cat)"

claude -p --model haiku \
  --append-system-prompt "$(cat "$dir/system-prompt.md")" \
  "$question"
