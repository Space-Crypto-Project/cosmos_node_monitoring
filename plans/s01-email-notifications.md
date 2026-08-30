---
type: plan
slot: s01
slug: email-notifications
status: validated
command: coder-plan-auto
date: 2026-08-30
title: Add optional SMTP e-mail notifications
---
## Goal

Deliver every existing Alertmanager notification to Telegram and, when locally enabled, SMTP e-mail, without tracking SMTP credentials or recipients.

## Current state

- `prometheus/alert_manager/alertmanager.yml:7-24` routes all alerts to `node-monitoring`; that receiver currently has one resolved-notification webhook to `http://alertmanager-bot:8080` and no e-mail configuration.
- `docker-compose.yml:91-100` mounts `prometheus/alert_manager` read-only into Alertmanager and loads `/etc/alertmanager/alertmanager.yml`.
- `config/.env.example:1-2` defines only Telegram settings, `.gitignore:1` ignores `config/.env`, and `README.md:72-117` requires operators to copy/export this file before starting Docker Compose.
- `install_monitoring.sh:25-27` installs Python 3, but the repository has no renderer, e-mail configuration, tests, lint configuration, or monitoring-stack runner. Searched root scripts, `config/`, `prometheus/`, `docker-compose.yml`, and `README.md` for `smtp`, `email`, `email_configs`, `envsubst`, `run_monitoring`, and `docker compose up` wrappers.
- Alertmanager supports combined `webhook_configs` and `email_configs` in one receiver; e-mail requires a recipient and can inherit global SMTP settings. Reference: https://prometheus.io/docs/alerting/latest/configuration/

## Proposed implementation

1. **New `render_alertmanager_config.py`** - read the existing local `config/.env` with a deliberately narrow dotenv parser, validate the e-mail toggle and required SMTP values, and generate a YAML-safe `prometheus/alert_manager/alertmanager.runtime.yml`. Reuse the current route, receiver name, webhook URL, grouping, template path, and resolved-notification behaviour; append `email_configs` to that same receiver only when e-mail is enabled. Emit actionable errors before Docker is started for an enabled but incomplete SMTP configuration.
2. **New `run_monitoring.sh`** - call the renderer, then start Compose with `--env-file config/.env` so the current Telegram arguments and the renderer share one local configuration source. Prefer `docker compose`, with an explicit `docker-compose` fallback for the legacy command documented by the project.
3. **`docker-compose.yml`** - mount only the generated runtime Alertmanager configuration at the existing container path; retain the read-only mount and current service topology.
4. **`config/.env.example` and `.gitignore`** - add empty or safe e-mail/SMTP variable names and ignore only the generated runtime YAML. Keep e-mail disabled by default and never add a real address, host, username, or password to tracked files.
5. **`README.md`** - replace the shell-profile export and raw Compose startup instructions with the wrapper command; document enabling e-mail, the required SMTP variables, default TLS expectation, multi-recipient syntax, and a safe test procedure.
6. **New `tests/test_render_alertmanager_config.py`** - use Python's standard `unittest` and isolated temporary repository fixtures to verify disabled e-mail retains Telegram-only configuration, enabled e-mail adds a resolved-notification receiver with YAML-escaped values, and an enabled configuration missing a required SMTP value fails. The last fixture is the deliberate sabotage proving the new validation guard can fail.
7. **`AGENTS.md`** - copy the already-created contributor guide from the primary checkout into this feature worktree so both requested deliverables are preserved on the feature branch.

## Tests

- `python -m unittest tests/test_render_alertmanager_config.py`
- `bash -n run_monitoring.sh`
- Render from a disposable `config/.env` with e-mail disabled and enabled, then run `docker compose --env-file config/.env config`.
- Start Alertmanager only against a disposable SMTP endpoint or a disabled e-mail setting; inspect its logs/readiness rather than sending mail to a real recipient.

## Risks / unknowns

- SMTP provider hostname, port, sender, recipients, and authentication method are operator-specific and intentionally remain unresolved local configuration, not repository defaults.
- The repository currently uses `prom/alertmanager:latest`; this implementation validates generated syntax locally but does not alter the image-version policy.
- The renderer's narrow dotenv format will be documented; unsupported shell interpolation in `.env` values must fail rather than be evaluated.

## Rollback

Set `EMAIL_NOTIFICATIONS_ENABLED=false`, run `./run_monitoring.sh`, and restart Alertmanager. Reverting the feature commit restores the tracked Telegram-only configuration path.
