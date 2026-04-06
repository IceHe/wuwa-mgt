#!/usr/bin/env bash
set -euo pipefail

ROOT="/root/wuwa/mgt"
BACKEND_DIR="${ROOT}/backend"
BIN_DIR="${BACKEND_DIR}/bin"

mkdir -p "${BIN_DIR}"
cd "${BACKEND_DIR}"

export GOCACHE="${GOCACHE:-/tmp/go-build}"
export GOMODCACHE="${GOMODCACHE:-/tmp/go-mod-cache}"

go build -o "${BIN_DIR}/wuwa-mgt-backend" ./cmd/server
