#!/usr/bin/env python3
"""Render the local Alertmanager runtime configuration without executing .env."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Mapping, NamedTuple


ROOT = Path(__file__).resolve().parent
DEFAULT_ENV_FILE = ROOT / "config" / ".env"
DEFAULT_TEMPLATE_FILE = ROOT / "prometheus" / "alert_manager" / "alertmanager.yml"
DEFAULT_ALERT_RULES_FILE = ROOT / "prometheus" / "alerts" / "alert.rules"
DEFAULT_OUTPUT_FILE = ROOT / "config" / "alertmanager.runtime.yml"

ENVIRONMENT_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
INTERPOLATION = re.compile(r"\$\{|\$\(|`")
ALERT_NAME = re.compile(r"^\s*-\s+alert:\s*([A-Za-z_][A-Za-z0-9_]*)\s*$")
# Alertmanager duration components must appear once, from largest to smallest.
DURATION = re.compile(
    r"^(?=.+)(?:[0-9]+y)?(?:[0-9]+w)?(?:[0-9]+d)?(?:[0-9]+h)?"
    r"(?:[0-9]+m)?(?:[0-9]+s)?(?:[0-9]+ms)?$"
)


class ConfigurationError(ValueError):
    """Raised when the local monitoring configuration is not safe to render."""


class NotificationPolicy(NamedTuple):
    """The alert selection and delivery cadence for one notification channel."""

    alerts: tuple[str, ...] | None
    group_wait: str
    group_interval: str
    repeat_interval: str


def parse_dotenv(path: Path) -> dict[str, str]:
    """Read a deliberately small KEY=VALUE dotenv format without shell evaluation."""
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as error:
        raise ConfigurationError(f"Local configuration file is missing: {path}") from error

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ConfigurationError(f"{path}:{line_number}: expected KEY=VALUE")
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not ENVIRONMENT_KEY.fullmatch(key):
            raise ConfigurationError(f"{path}:{line_number}: invalid variable name {key!r}")

        value = raw_value.strip()
        if value.startswith(("'", '"')):
            quote = value[0]
            if len(value) < 2 or not value.endswith(quote):
                raise ConfigurationError(f"{path}:{line_number}: unterminated quoted value")
            value = value[1:-1]
        elif any(character.isspace() for character in value):
            raise ConfigurationError(
                f"{path}:{line_number}: quote values that contain whitespace"
            )
        if INTERPOLATION.search(value):
            raise ConfigurationError(
                f"{path}:{line_number}: shell interpolation is not supported in .env values"
            )
        values[key] = value
    return values


def yaml_string(value: str) -> str:
    """Return a YAML-compatible, double-quoted scalar without a YAML dependency."""
    return json.dumps(value, ensure_ascii=False)


def active_alert_names(path: Path) -> set[str]:
    """Read active Prometheus alert names from the repository's rule file."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as error:
        raise ConfigurationError(f"Prometheus alert rules are missing: {path}") from error
    names = {
        match.group(1)
        for line in lines
        if (match := ALERT_NAME.fullmatch(line)) is not None
    }
    if not names:
        raise ConfigurationError(f"Prometheus alert rules contain no alert names: {path}")
    return names


def selected_alerts(
    values: Mapping[str, str], key: str, default: str, available: set[str]
) -> tuple[str, ...] | None:
    """Validate a comma-separated alert list; ``all`` intentionally has no matcher."""
    raw_value = values.get(key, default).strip()
    if raw_value.lower() == "all":
        return None
    names = tuple(name.strip() for name in raw_value.split(",") if name.strip())
    if not names:
        raise ConfigurationError(f"{key} must be all or a comma-separated list of alert names")
    if len(set(names)) != len(names):
        raise ConfigurationError(f"{key} must not contain duplicate alert names")
    unknown = sorted(set(names) - available)
    if unknown:
        raise ConfigurationError(
            f"{key} contains alert names that are not active in prometheus/alerts/alert.rules: "
            + ", ".join(unknown)
        )
    return names


def duration(values: Mapping[str, str], key: str, default: str) -> str:
    """Validate Alertmanager duration syntax before it reaches the runtime file."""
    value = values.get(key, default).strip()
    if not DURATION.fullmatch(value):
        raise ConfigurationError(
            f"{key} must be an Alertmanager duration such as 0s, 5m, 1h, or 24h"
        )
    return value


def notification_policy(
    values: Mapping[str, str], prefix: str, alerts_default: str, available: set[str]
) -> NotificationPolicy:
    """Build one channel policy from its independent environment variables."""
    return NotificationPolicy(
        alerts=selected_alerts(values, f"{prefix}_ALERTS", alerts_default, available),
        group_wait=duration(values, f"{prefix}_GROUP_WAIT", "0s"),
        group_interval=duration(values, f"{prefix}_GROUP_INTERVAL", "5m"),
        repeat_interval=duration(
            values,
            f"{prefix}_REPEAT_INTERVAL",
            "1h" if prefix == "TELEGRAM" else "24h",
        ),
    )


def enabled_email_settings(values: Mapping[str, str]) -> dict[str, str] | None:
    enabled = values.get("EMAIL_NOTIFICATIONS_ENABLED", "false").lower()
    if enabled not in {"true", "false"}:
        raise ConfigurationError("EMAIL_NOTIFICATIONS_ENABLED must be true or false")
    if enabled == "false":
        return None
    required = (
        "EMAIL_SMTP_HOST",
        "EMAIL_SMTP_PORT",
        "EMAIL_SMTP_FROM",
        "EMAIL_SMTP_TO",
    )
    missing = [key for key in required if not values.get(key, "").strip()]
    if missing:
        raise ConfigurationError(
            "E-mail notifications are enabled but these variables are empty: "
            + ", ".join(missing)
        )
    port = values["EMAIL_SMTP_PORT"]
    if not port.isdecimal() or not 1 <= int(port) <= 65535:
        raise ConfigurationError("EMAIL_SMTP_PORT must be an integer from 1 to 65535")
    require_tls = values.get("EMAIL_SMTP_REQUIRE_TLS", "true").lower()
    if require_tls not in {"true", "false"}:
        raise ConfigurationError("EMAIL_SMTP_REQUIRE_TLS must be true or false")
    username = values.get("EMAIL_SMTP_USERNAME", "")
    password = values.get("EMAIL_SMTP_PASSWORD", "")
    if bool(username) != bool(password):
        raise ConfigurationError(
            "EMAIL_SMTP_USERNAME and EMAIL_SMTP_PASSWORD must be set together"
        )
    return {
        "host": values["EMAIL_SMTP_HOST"],
        "port": port,
        "from": values["EMAIL_SMTP_FROM"],
        "to": values["EMAIL_SMTP_TO"],
        "require_tls": require_tls,
        "username": username,
        "password": password,
    }


def matcher_lines(alerts: tuple[str, ...] | None) -> list[str]:
    """Return an Alertmanager matcher only when a channel excludes some alerts."""
    if alerts is None:
        return []
    expression = "^(?:" + "|".join(re.escape(name) for name in alerts) + ")$"
    return [
        "      matchers:\n",
        f"        - {yaml_string(f'alertname=~\"{expression}\"')}\n",
    ]


def route_lines(receiver: str, policy: NotificationPolicy, *, continue_to_next: bool) -> list[str]:
    lines = [
        f"    - receiver: {receiver}\n",
        "      group_by: ['...']\n",
        f"      group_wait: {policy.group_wait}\n",
        f"      group_interval: {policy.group_interval}\n",
        f"      repeat_interval: {policy.repeat_interval}\n",
        *matcher_lines(policy.alerts),
    ]
    if continue_to_next:
        lines.append("      continue: true\n")
    return lines


def insert_global_smtp_settings(template: str, settings: Mapping[str, str]) -> str:
    """Add SMTP fields to the template's single existing Alertmanager global block."""
    lines = template.splitlines(keepends=True)
    try:
        global_index = next(index for index, line in enumerate(lines) if line == "global:\n")
    except StopIteration as error:
        raise ConfigurationError("Alertmanager template must define a global section") from error

    insertion_index = global_index + 1
    while insertion_index < len(lines) and (
        not lines[insertion_index].strip() or lines[insertion_index].startswith((" ", "\t"))
    ):
        insertion_index += 1
    smarthost = f"{settings['host']}:{settings['port']}"
    smtp_lines = [
        f"  smtp_smarthost: {yaml_string(smarthost)}\n",
        f"  smtp_from: {yaml_string(settings['from'])}\n",
        f"  smtp_require_tls: {settings['require_tls']}\n",
    ]
    if settings["username"]:
        smtp_lines.extend(
            [
                f"  smtp_auth_username: {yaml_string(settings['username'])}\n",
                "  smtp_auth_password_file: \"/run/secrets/alertmanager_smtp_password\"\n",
            ]
        )
    return "".join(lines[:insertion_index] + smtp_lines + lines[insertion_index:])


def render_config_text(
    template: str,
    telegram_policy: NotificationPolicy,
    email_policy: NotificationPolicy | None,
    email_settings: Mapping[str, str] | None,
) -> str:
    """Append independent routes and receivers to the stable global/template settings."""
    if "global:" not in template or "templates:" not in template:
        raise ConfigurationError("Alertmanager template must define global and templates sections")
    if "\nroute:" in template or "\nreceivers:" in template:
        raise ConfigurationError("Alertmanager template routes and receivers are generated at runtime")

    if email_settings:
        template = insert_global_smtp_settings(template, email_settings)
    lines = [template.rstrip() + "\n\n"]
    lines.extend(
        [
            "route:\n",
            "  receiver: discard\n",
            "  routes:\n",
            *route_lines("telegram", telegram_policy, continue_to_next=bool(email_settings)),
        ]
    )
    if email_settings:
        if email_policy is None:
            raise ConfigurationError("E-mail policy is missing while e-mail is enabled")
        lines.extend(route_lines("email", email_policy, continue_to_next=False))
    lines.extend(
        [
            "\nreceivers:\n",
            "- name: discard\n",
            "- name: telegram\n",
            "  webhook_configs:\n",
            "  - send_resolved: true\n",
            "    url: 'http://alertmanager-bot:8080'\n",
        ]
    )
    if email_settings:
        lines.extend(
            [
                "- name: email\n",
                "  email_configs:\n",
                f"  - to: {yaml_string(email_settings['to'])}\n",
                "    send_resolved: true\n",
            ]
        )
    return "".join(lines)


def render_config(
    env_file: Path,
    template_file: Path,
    output_file: Path,
    alert_rules_file: Path = DEFAULT_ALERT_RULES_FILE,
) -> None:
    values = parse_dotenv(env_file)
    available_alerts = active_alert_names(alert_rules_file)
    telegram_policy = notification_policy(values, "TELEGRAM", "all", available_alerts)
    email_settings = enabled_email_settings(values)
    email_policy = (
        notification_policy(
            values,
            "EMAIL",
            "InstanceDown,IsJailed,ValidatorIsJailed",
            available_alerts,
        )
        if email_settings
        else None
    )
    try:
        template = template_file.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise ConfigurationError(f"Alertmanager template is missing: {template_file}") from error
    rendered = render_config_text(template, telegram_policy, email_policy, email_settings)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(env_file, 0o600)
    os.chmod(output_file.parent, 0o700)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=output_file.parent, delete=False
    ) as temporary_file:
        temporary_file.write(rendered)
        temporary_path = Path(temporary_file.name)
    # The rendered YAML contains no SMTP password. The private config directory
    # protects recipient metadata on the host, while Alertmanager's `nobody`
    # user can read this direct bind mount.
    os.chmod(temporary_path, 0o644)
    temporary_path.replace(output_file)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render the local Alertmanager configuration from config/.env."
    )
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE_FILE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_FILE)
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    try:
        render_config(arguments.env_file, arguments.template, arguments.output)
    except ConfigurationError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
