---
type: review
slot: s01
slug: email-notifications
status: request-changes
command: coder-plan-auto
date: 2026-08-30
title: SMTP e-mail notification review
---
## Review summary

- Diff class: 1 (outbound SMTP delivery and SMTP credential handling).
- Reviewer tours: 2 of 2, both on inherited `gpt-5.6` session model.
- Tour 1 verdict: `request changes`.
  - Fixed Alertmanager not applying a newly rendered configuration by restarting the service after each successful render.
  - Fixed a private runtime YAML being unreadable by the image user by removing the host-UID override, isolating the file from Prometheus, and redesigning password delivery.
- Tour 2 verdict: `request changes`.
  - Fixed the host-UID workaround preventing Alertmanager from writing `/alertmanager` by restoring the image's non-root identity.
  - The SMTP password is now an Alertmanager-only Docker Compose environment secret, read through `smtp_auth_password_file`; the rendered YAML no longer contains the password. The local config directory is restricted to the owner and the password remains only in ignored `config/.env`.
- No reviewer finding remains open. The final commit `6402375` includes corrections made after tour 2, so the last reviewer verdict predates those corrections; no third review was dispatched because the class-1 two-tour budget was exhausted.

## Validation

- `python -m unittest tests/test_render_alertmanager_config.py` passed: 6 tests, including the deliberate enabled-but-missing-SMTP-host failure and password exclusion from rendered YAML.
- `bash -n run_monitoring.sh install_monitoring.sh` passed.
- `docker compose --env-file config/.env.example config` passed. Docker reported only the repository's pre-existing obsolete Compose `version` warning.
- `git diff --check` and staged-diff privacy scans passed; no non-placeholder e-mail address appeared in the staged changes.

## Remaining limitation

Docker was unavailable for an image-level startup test in this workspace. The Compose secret design follows the Docker Compose environment-secret contract, while the Alertmanager image's built-in `nobody` identity is retained. The operator should perform the documented disposable SMTP startup test after deployment.
