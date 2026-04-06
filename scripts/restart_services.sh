#!/usr/bin/env bash
set -euo pipefail

BACKEND_SERVICE="wuwa-mgt-backend.service"
FRONTEND_SERVICE="wuwa-mgt-frontend.service"
BACKEND_HEALTH_URL="http://127.0.0.1:8765/healthz"
FRONTEND_HEALTH_URL="http://127.0.0.1:3001/"

echo "[1/5] Building Go backend..."
/root/wuwa/mgt/scripts/build_backend.sh

echo "[2/5] Restarting services..."
systemctl restart "${BACKEND_SERVICE}"
systemctl restart "${FRONTEND_SERVICE}"

echo "[3/5] Checking service status..."
systemctl is-active --quiet "${BACKEND_SERVICE}" || {
  echo "Backend service is not active: ${BACKEND_SERVICE}" >&2
  exit 1
}
systemctl is-active --quiet "${FRONTEND_SERVICE}" || {
  echo "Frontend service is not active: ${FRONTEND_SERVICE}" >&2
  exit 1
}

echo "[4/5] Running health checks..."
backend_code="000"
frontend_code="000"
for _ in $(seq 1 30); do
  backend_code="$(curl --noproxy '*' -sS -o /tmp/mgt_backend_health.json -w '%{http_code}' "${BACKEND_HEALTH_URL}" || true)"
  frontend_code="$(curl --noproxy '*' -sS -o /tmp/mgt_frontend_index.html -w '%{http_code}' "${FRONTEND_HEALTH_URL}" || true)"
  if [[ "${backend_code}" == "200" && "${frontend_code}" == "200" ]]; then
    break
  fi
  sleep 1
done

if [[ "${backend_code}" != "200" ]]; then
  echo "Backend health check failed with HTTP ${backend_code}" >&2
  exit 1
fi
if [[ "${frontend_code}" != "200" ]]; then
  echo "Frontend health check failed with HTTP ${frontend_code}" >&2
  exit 1
fi

echo "[5/5] Done."
echo "Backend: ${BACKEND_SERVICE} (active)"
echo "Frontend: ${FRONTEND_SERVICE} (active)"
echo "Health: ${BACKEND_HEALTH_URL} -> ${backend_code}"
echo "Frontend: ${FRONTEND_HEALTH_URL} -> ${frontend_code}"
