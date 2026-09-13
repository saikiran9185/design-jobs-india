#!/usr/bin/env bash
# Design Jobs India — local runner.
#   ./run.sh          start the web app at http://localhost:8000
#   ./run.sh ingest   pull fresh jobs from every source
#   ./run.sh probe    discover which companies have a public ATS board
#   ./run.sh contacts find studios' published careers emails
#   ./run.sh export   rebuild site/data/*.json for the static site
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "First run — creating environment..."
  uv venv --quiet
  uv pip install --quiet -r <(uv pip compile pyproject.toml --quiet 2>/dev/null || echo "") 2>/dev/null \
    || uv pip install --quiet fastapi "uvicorn[standard]" httpx pyyaml python-dotenv python-multipart
  [ -f .env ] || cp .env.example .env
fi
source .venv/bin/activate

case "${1:-serve}" in
  ingest) python -m backend.ingest "${@:2}" ;;
  probe)  python -m backend.probe ;;
  contacts) python -m backend.find_contacts ;;
  export) python -m backend.export_static ;;
  serve)
    echo ""
    echo "  Design Jobs India  →  http://localhost:8000"
    echo "  Ctrl-C to stop"
    echo ""
    exec uvicorn backend.app:app --host 127.0.0.1 --port 8000 --log-level warning
    ;;
  *) echo "usage: ./run.sh [serve|ingest|probe|contacts|export]"; exit 1 ;;
esac
