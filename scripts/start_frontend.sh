#!/usr/bin/env bash
set -euo pipefail

cd /root/wuwa/mgt

exec /usr/bin/env node /root/wuwa/mgt/scripts/start_frontend.js
