#!/usr/bin/env bash
set -euo pipefail
PACKAGE_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ ${1:-} == --help || ${1:-} == -h ]]; then
  exec python3 "$PACKAGE_DIR/tools/manage.py" "$@"
fi
umask 077
mkdir -p "$PACKAGE_DIR/.runtime"
LOG_FILE="$PACKAGE_DIR/.runtime/$(date -u +%Y%m%dT%H%M%SZ)-$$.log"
exec > >(tee -a "$LOG_FILE") 2>&1
printf 'Command log: %s\n' "$LOG_FILE"
python3 "$PACKAGE_DIR/tools/manage.py" "$@"
