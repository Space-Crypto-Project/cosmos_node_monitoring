# Repository Guidelines

## Project Structure & Module Organization

This repository provisions a Docker-based monitoring stack for Cosmos validators. Root-level `install_*.sh` scripts install exporters or the monitoring host; `add_validator*.sh` adds Prometheus scrape targets. Keep deployment orchestration in `docker-compose.yml` and shared alert text in `default.tmpl`.

Runtime configuration is grouped by service: `prometheus/` contains scrape definitions, alert rules, and Alertmanager configuration; `grafana/` contains provisioning and dashboard JSON; `alerta/` contains Alerta configuration. Store local secrets only in `config/.env` (ignored by Git); use `config/.env.example` for documented variable names.

## Build, Test, and Development Commands

There is no compiled application or automated test suite. Validate changes before deployment:

```bash
bash -n install_*.sh add_validator*.sh  # check Bash syntax
docker compose config                    # render and validate the stack
docker compose up -d                     # start the local stack
docker compose logs -f prometheus        # inspect a changed service
```

Use Docker Compose v2 (`docker compose`): the SMTP notification path relies on its secret support. Exercise an alert only on a disposable validator or test environment; never stop a production exporter merely to test a change.

## Coding Style & Naming Conventions

Write portable Bash with a Bash shebang, quoted variable expansions, and four-space indentation inside control blocks. Name executable scripts in lowercase snake case, such as `install_cosmos_exporter.sh`. Keep YAML indentation consistent with the surrounding file (two spaces) and preserve Prometheus/Grafana JSON structure and ordering where practical. Prefer `shellcheck` and `yamllint` when available, but do not add tool configuration without a repository need.

## Testing Guidelines

For shell edits, run `bash -n` and test the relevant script in an isolated VM or container with non-production addresses. For configuration edits, run `docker compose config`, then verify the affected service starts and review its logs. Include the exact validation performed in the pull request.

## Commit & Pull Request Guidelines

Recent history uses short imperative summaries (for example, `Update README.md` and `error fixed`). Use a clearer scoped imperative subject, such as `prometheus: add CometBFT scrape target`. Keep commits focused. PRs should state the operational effect, changed ports or environment variables, validation evidence, rollback considerations, and screenshots for Grafana dashboard changes. Never commit tokens, Telegram identifiers, private IPs, or `.env` values.
