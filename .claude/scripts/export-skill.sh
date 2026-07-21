#!/usr/bin/env bash
# Export stocked skills from my-skills/skills/ to user scope or another repository.
#
# Usage:
#   export-skill.sh                              Interactive: pick destination then skill.
#   export-skill.sh --user <skill>               Copy to ~/.claude/skills/<skill>.
#   export-skill.sh --to <repo> <skill>          Copy to <repo>/.claude/skills/<skill>.
#   export-skill.sh --list                       List stocked skills.
#   export-skill.sh --force ...                  Overwrite destination without asking.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SRC_DIR="${ROOT_DIR}/skills"

USER_SKILL_DIR="${HOME}/.claude/skills"

err() { echo "error: $*" >&2; }
info() { echo "==> $*"; }

usage() {
  sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
}

list_skills() {
  local found=0
  if [[ ! -d "${SRC_DIR}" ]]; then
    echo "  (no skills directory: ${SRC_DIR})"
    return 0
  fi
  while IFS= read -r entry; do
    if [[ -f "${entry}/SKILL.md" ]]; then
      printf '  %s\n' "$(basename "${entry}")"
      found=1
    fi
  done < <(find "${SRC_DIR}" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort)
  if [[ "${found}" -eq 0 ]]; then
    echo "  (no skills found)"
  fi
}

pick_skill() {
  local skills=()
  while IFS= read -r entry; do
    if [[ -f "${entry}/SKILL.md" ]]; then
      skills+=("$(basename "${entry}")")
    fi
  done < <(find "${SRC_DIR}" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort)

  if [[ "${#skills[@]}" -eq 0 ]]; then
    err "no skills stocked in ${SRC_DIR}"
    return 1
  fi

  echo "Stocked skills:" >&2
  local i=1
  for s in "${skills[@]}"; do
    printf '  %2d) %s\n' "${i}" "${s}" >&2
    i=$((i + 1))
  done
  printf 'Pick number (or skill name): ' >&2
  local choice
  read -r choice
  if [[ "${choice}" =~ ^[0-9]+$ ]]; then
    local idx=$((choice - 1))
    if (( idx < 0 || idx >= ${#skills[@]} )); then
      err "out of range"
      return 1
    fi
    echo "${skills[$idx]}"
  else
    echo "${choice}"
  fi
}

copy_out() {
  local name="$1"
  local dest_root="$2"
  local force="$3"

  local src="${SRC_DIR}/${name}"
  if [[ ! -f "${src}/SKILL.md" ]]; then
    err "skill not found or invalid: ${src}"
    return 1
  fi

  mkdir -p "${dest_root}"
  local dest="${dest_root}/${name}"

  if [[ -e "${dest}" ]]; then
    if [[ "${force}" -ne 1 ]]; then
      printf 'overwrite existing %s? [y/N] ' "${dest}" >&2
      local ans
      read -r ans
      if [[ ! "${ans}" =~ ^[Yy]$ ]]; then
        info "skipped: ${name}"
        return 0
      fi
    fi
    rm -rf "${dest}"
  fi

  cp -RL "${src}" "${dest}"
  info "exported ${name} -> ${dest}"
}

main() {
  local mode=""
  local repo=""
  local skill=""
  local force=0
  local list_only=0

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help) usage; exit 0 ;;
      --user) mode="user"; shift ;;
      --to)
        mode="repo"
        if [[ $# -lt 2 ]]; then err "--to needs <repo>"; exit 2; fi
        repo="$2"; shift 2 ;;
      --list) list_only=1; shift ;;
      --force) force=1; shift ;;
      --*) err "unknown option: $1"; usage; exit 2 ;;
      *)
        if [[ -z "${skill}" ]]; then skill="$1"; else err "extra arg: $1"; exit 2; fi
        shift ;;
    esac
  done

  if [[ "${list_only}" -eq 1 ]]; then
    info "stocked skills in ${SRC_DIR}:"
    list_skills
    exit 0
  fi

  if [[ -z "${mode}" ]]; then
    echo "Select destination:"
    echo "  1) user scope (${USER_SKILL_DIR})"
    echo "  2) another repository (.claude/skills/)"
    printf 'choice [1/2]: '
    local s
    read -r s
    case "${s}" in
      2)
        mode="repo"
        printf 'repository path: '
        read -r repo
        ;;
      *)
        mode="user"
        ;;
    esac
  fi

  local dest_root=""
  case "${mode}" in
    user) dest_root="${USER_SKILL_DIR}" ;;
    repo)
      if [[ -z "${repo}" ]]; then err "missing repo path"; exit 2; fi
      if [[ ! -d "${repo}" ]]; then err "not a directory: ${repo}"; exit 1; fi
      dest_root="${repo}/.claude/skills"
      ;;
  esac

  if [[ -z "${skill}" ]]; then
    skill="$(pick_skill)" || exit 1
  fi

  copy_out "${skill}" "${dest_root}" "${force}"
}

main "$@"
