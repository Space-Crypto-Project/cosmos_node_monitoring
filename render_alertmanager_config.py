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
from typing import Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_ENV_FILE = ROOT / "config" / ".env"
DEFAULT_TEMPLATE_FILE = ROOT / "prometheus" / "alert_manager" / "alertmanager.yml"
DEFAULT_OUTPUT_FILE = ROOT / "config" / "alertmanager.runtime.yml"

ENVIRONMENT_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
INTERPOLATION = re.compile(r"\$\{|\$\(|`")


class ConfigurationError(ValueError):
    """Raised when the local monitoring configuration is not safe to render."""


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


def insert_global_smtp_settings(template: str, settings: Mapping[str, str]) -> str:
    lines = template.splitlines(keepends=True)
    try:
        global_index = next(index for index, line in enumerate(lines) if line == "global:\n")
    except StopIteration as error:
        raise ConfigurationError("Alertmanager template must define a global section") from error

    insertion_index = global_index + 1
    while insertion_index < len(lines) and (
        not lines[insertion_index].strip()
        or lines[insertion_index].startswith((" ", "\t"))
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


def append_receiver_email_settings(template: str, settings: Mapping[str, str]) -> str:
    lines = template.splitlines(keepends=True)
    receiver_start = next(
        (
            index
            for index, line in enumerate(lines)
            if line.rstrip("\r\n") in {"- name: 'node-monitoring'", '- name: "node-monitoring"'}
        ),
        None,
    )
    if receiver_start is None:
        raise ConfigurationError("Alertmanager template must define the node-monitoring receiver")

    receiver_end = len(lines)
    for index in range(receiver_start + 1, len(lines)):
        if lines[index].startswith("- name:"):
            receiver_end = index
            break

    receiver_lines = lines[receiver_start:receiver_end]
    if not any(line.lstrip().startswith("webhook_configs:") for line in receiver_lines):
        raise ConfigurationError("node-monitoring receiver must retain its webhook configuration")
    if any(line.lstrip().startswith("email_configs:") for line in receiver_lines):
        raise ConfigurationError("node-monitoring receiver already defines email_configs")

    email_lines = [
        "" if receiver_end == 0 or lines[receiver_end - 1].endswith("\n") else "\n",
        "  email_configs:\n",
        f"  - to: {yaml_string(settings['to'])}\n",
        "    send_resolved: true\n",
    ]
    return "".join(lines[:receiver_end] + email_lines + lines[receiver_end:])


def render_config(env_file: Path, template_file: Path, output_file: Path) -> None:
    values = parse_dotenv(env_file)
    settings = enabled_email_settings(values)
    try:
        rendered = template_file.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise ConfigurationError(f"Alertmanager template is missing: {template_file}") from error

    if settings:
        rendered = insert_global_smtp_settings(rendered, settings)
        rendered = append_receiver_email_settings(rendered, settings)

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
