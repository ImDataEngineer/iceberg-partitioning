#!/usr/bin/env bash
# IAmDataEng — first-boot bootstrap for `storage.partitioned-lakehouse`.
#
# 1. Install Python deps
# 2. Pull + start MinIO and the Iceberg REST catalog (docker compose)
# 3. Wait for both health checks to go green
# 4. Generate the deterministic Parquet fixtures (~120k rows, 3 years)
#
# Designed to be re-runnable: `docker compose up -d` is idempotent and fixture
# regeneration is byte-stable thanks to a fixed seed.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "[1/4] Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "[2/4] Starting the local lakehouse stack (MinIO + Iceberg REST)..."
docker compose up -d

echo "[3/4] Waiting for services to be healthy..."
# We poll the public endpoints rather than `docker inspect` — same signal
# the test suite uses, no surprises between dev and CI.
for i in $(seq 1 60); do
  if curl -fsS http://localhost:9000/minio/health/live >/dev/null 2>&1 \
     && curl -fsS http://localhost:8181/v1/config >/dev/null 2>&1; then
    echo "  services ready (after ${i}s)"
    break
  fi
  if [ "$i" = "60" ]; then
    echo "  ERROR: services did not become healthy within 60s."
    docker compose logs --tail=50
    exit 1
  fi
  sleep 1
done

echo "[4/4] Generating deterministic Parquet fixtures..."
python -m fixtures.generate_fixtures

echo
echo "Setup done. Next steps:"
echo "  1. Read README.fr.md"
echo "  2. Implement src/create_table.py, src/load.py, src/time_travel_demo.py"
echo "  3. Run: pytest tests/ -v"
