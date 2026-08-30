---
type: research
slot: s01
slug: email-notifications
status: captured
command: coder-plan-auto
date: 2026-08-30
title: Email notification research
---
## Research summary

- `prometheus/alert_manager/alertmanager.yml:1-24` defines one `node-monitoring` receiver. The route's default receiver and child route both select it; it currently contains only the `http://alertmanager-bot:8080` webhook with resolved notifications enabled.
- `docker-compose.yml:91-100` bind-mounts that file into the Alertmanager container and starts it with `--config.file=/etc/alertmanager/alertmanager.yml`.
- `config/.env.example:1-2` contains only Telegram values, while `.gitignore:1` ignores the local `config/.env`. `README.md:72-117` tells operators to copy/export that file and run `docker-compose up -d`.
- `install_monitoring.sh:25-27` installs Python 3, so a dependency-free renderer can run on the documented monitoring host. It does not currently render Alertmanager configuration or start the stack.
- No test directory, package manifest, shell lint configuration, or Alertmanager configuration test is tracked. The existing configuration is mounted read-only, so SMTP credentials must not be placed in the tracked YAML.
- Reuse audit: the existing `node-monitoring` receiver, local `.env` convention, and Alertmanager mount are the canonical extension points. Search scope: root scripts, `config/`, `prometheus/`, `docker-compose.yml`, and `README.md`; no SMTP/email renderer, receiver, or test helper exists.
- Official Alertmanager documentation confirms that a receiver may combine `webhook_configs` and `email_configs`; e-mail uses SMTP settings, a required `to` field, and can send resolved notifications. It also confirms that malformed configuration is rejected on reload. Source: https://prometheus.io/docs/alerting/latest/configuration/
