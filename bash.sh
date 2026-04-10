#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Starting backend with uvicorn from ${ROOT_DIR}/backend"
(
  cd "${ROOT_DIR}/backend"
  python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
) &
BACKEND_PID=$!

echo "Starting frontend with npm run dev from ${ROOT_DIR}/frontend"
(
  cd "${ROOT_DIR}/frontend"
  npm run dev
) &
FRONTEND_PID=$!

cleanup() {
  echo "Stopping services..."
  kill "${BACKEND_PID}" "${FRONTEND_PID}" 2>/dev/null || true
}

trap cleanup INT TERM
wait "${BACKEND_PID}" "${FRONTEND_PID}"
