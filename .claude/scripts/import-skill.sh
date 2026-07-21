#!/usr/bin/env bash
# Import Claude/Codex skills from user scope or other repositories into my-skills/skills/.
#
# Usage:
#   import-skill.sh                              Interactive: pick source then skill.
#   import-skill.sh --user <skill>               Copy from ~/.claude/skills/<skill>.
#   import-skill.sh --from <repo> <skill>        Copy from <repo>/.claude/skills/<skill>.
#   import-skill.sh --list                       List user-scope skills.
#   import-skill.sh --list --from <repo>         List skills under <repo>/.claude/skills.
#   import-skill.sh --force ...                  Overwrite existing skill without asking.
#
# A "skill" is a directory containing SKILL.md.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEST_DIR="${ROOT_DIR}/skills"

USER_SKILL_DIR="${HOME}/.claude/skills"

err() { echo "error: $*" >&2; }
info() { echo "==> $*"; }

usage() {
  sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
}

# Search candidate locations for a skill source directory inside a given repo.
# Echoes the matched path, or empty string if none found.
resolve_repo_skills_dir() {
  local repo="$1"
  for sub in ".claude/skills" "skills" "my-skills/skills" "agents/skills"; do
    if [[ -d "${repo}/${sub}" ]]; then
      echo "${repo}/${sub}"
      return 0
    fi
  done
  return 1
}

# List skills under a directory. A skill is a child directory that contains SKILL.md.
list_skills() {
  local dir="$1"
  if [[ ! -d "${dir}" ]]; then
    err "skills directory not found: ${dir}"
    return 1
  fi
  local found=0
  # Resolve symlinks so list shows real targets too.
  while IFS= read -r entry; do
    local name
    name="$(basename "${entry}")"
    if [[ -f "${entry}/SKILL.md" ]] || [[ -L "${entry}" && -f "${entry}/SKILL.md" ]]; then
      printf '  %s\n' "${name}"
      found=1
    fi
  done < <(find "${dir}" -mindepth 1 -maxdepth 1 \( -type d -o -type l \) 2>/dev/null | sort)
  if [[ "${found}" -eq 0 ]]; then
    echo "  (no skills found)"
  fi
}

pick_skill() {
  local dir="$1"
  local skills=()
  while IFS= read -r entry; do
    if [[ -f "${entry}/SKILL.md" ]]; then
      skills+=("$(basename "${entry}")")
    fi
  done < <(find "${dir}" -mindepth 1 -maxdepth 1 \( -type d -o -type l \) 2>/dev/null | sort)

  if [[ "${#skills[@]}" -eq 0 ]]; then
    err "no skills found in ${dir}"
    return 1
  fi

  echo "Available skills in ${dir}:" >&2
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

copy_skill() {
  local src="$1"
  local name="$2"
  local force="$3"

  if [[ ! -f "${src}/SKILL.md" ]]; then
    err "not a skill (missing SKILL.md): ${src}"
    return 1
  fi

  mkdir -p "${DEST_DIR}"
  local dest="${DEST_DIR}/${name}"

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

  # -R recurse, -L dereference symlinks (so a symlinked skill becomes a real copy)
  cp -RL "${src}" "${dest}"
  info "imported ${name} -> ${dest}"
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
      --from)
        mode="repo"
        if [[ $# -lt 2 ]]; then err "--from needs <repo>"; exit 2; fi
        repo="$2"; shift 2 ;;
      --list) list_only=1; shift ;;
      --force) force=1; shift ;;
      --*) err "unknown option: $1"; usage; exit 2 ;;
      *)
        if [[ -z "${skill}" ]]; then skill="$1"; else err "extra arg: $1"; exit 2; fi
        shift ;;
    esac
  done

  # Resolve source skills directory for list/copy.
  local src_dir=""
  case "${mode}" in
    user|"")
      src_dir="${USER_SKILL_DIR}"
      ;;
    repo)
      src_dir="$(resolve_repo_skills_dir "${repo}" || true)"
      if [[ -z "${src_dir}" ]]; then
        err "no skills directory found under ${repo} (looked for .claude/skills, skills, my-skills/skills, agents/skills)"
        exit 1
      fi
      ;;
  esac

  if [[ "${list_only}" -eq 1 ]]; then
    info "skills in ${src_dir}:"
    list_skills "${src_dir}"
    exit 0
  fi

  # Interactive source selection if mode was not set.
  if [[ -z "${mode}" ]]; then
    echo "Select source:"
    echo "  1) user scope (${USER_SKILL_DIR})"
    echo "  2) another repository"
    printf 'choice [1/2]: '
    local s
    read -r s
    case "${s}" in
      2)
        printf 'repository path: '
        read -r repo
        src_dir="$(resolve_repo_skills_dir "${repo}" || true)"
        if [[ -z "${src_dir}" ]]; then
          err "no skills directory found under ${repo}"
          exit 1
        fi
        ;;
      *)
        src_dir="${USER_SKILL_DIR}"
        ;;
    esac
  fi

  if [[ -z "${skill}" ]]; then
    skill="$(pick_skill "${src_dir}")" || exit 1
  fi

  copy_skill "${src_dir}/${skill}" "${skill}" "${force}"
}

main "$@"
