#!/usr/bin/env bash
# Only for disposable hosted CI. Enter delegated subtree BEFORE dropping privileges.
set -euo pipefail
: "${AEROBROWSE_CGROUP_ROOT:?delegated cgroup missing}"
sudo bash -c '
  root="$1"; uid="$2"; gid="$3"; shift 3
  echo $$ > "$root/driver/cgroup.procs"
  exec env AEROBROWSE_CGROUP_ROOT="$root" setpriv --reuid "$uid" --regid "$gid" --init-groups "$@"
' _ "$AEROBROWSE_CGROUP_ROOT" "$(id -u)" "$(id -g)" "$@"
