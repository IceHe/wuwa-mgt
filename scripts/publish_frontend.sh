#!/usr/bin/env bash
set -euo pipefail

SRC_DIR="/root/wuwa/mgt/frontend/dist"
DST_DIR="/var/www/wuwa-mgt/dist"

if [[ ! -f "${SRC_DIR}/index.html" ]]; then
  echo "frontend dist is missing: ${SRC_DIR}/index.html" >&2
  exit 1
fi

mkdir -p "$(dirname "${DST_DIR}")"
rm -rf "${DST_DIR}"
cp -a "${SRC_DIR}" "${DST_DIR}"

