#!/usr/bin/env bash
set -euo pipefail

cd /root/wuwa/mgt/backend
exec /usr/bin/python3 /root/wuwa/mgt/backend/server.py 8765
