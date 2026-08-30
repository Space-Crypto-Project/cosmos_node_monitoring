#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir"

if [[ ! -f config/.env ]]; then
    echo "Missing config/.env. Copy config/.env.example and set the local values first." >&2
    exit 1
fi

python3 render_alertmanager_config.py

if docker compose version >/dev/null 2>&1; then
    docker compose --env-file config/.env up -d "$@"
    docker compose --env-file config/.env restart alertmanager
else
    echo "Docker Compose v2 is required for Alertmanager SMTP secrets." >&2
    exit 1
fi
