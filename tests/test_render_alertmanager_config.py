from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPOSITORY_ROOT / "render_alertmanager_config.py"
SPECIFICATION = importlib.util.spec_from_file_location("renderer", MODULE_PATH)
assert SPECIFICATION and SPECIFICATION.loader
renderer = importlib.util.module_from_spec(SPECIFICATION)
SPECIFICATION.loader.exec_module(renderer)


ALERTMANAGER_TEMPLATE = """global:
  resolve_timeout: 1m

templates:
- 'templates/*'
"""


class RenderAlertmanagerConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.env_file = self.root / "config" / ".env"
        self.template_file = self.root / "prometheus" / "alert_manager" / "alertmanager.yml"
        self.output_file = self.root / "config" / "alertmanager.runtime.yml"
        self.env_file.parent.mkdir(parents=True)
        self.template_file.parent.mkdir(parents=True)
        self.template_file.write_text(ALERTMANAGER_TEMPLATE, encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write_environment(self, content: str) -> None:
        self.env_file.write_text(content, encoding="utf-8")

    def render(self) -> str:
        renderer.render_config(self.env_file, self.template_file, self.output_file)
        return self.output_file.read_text(encoding="utf-8")

    def test_default_telegram_policy_preserves_historical_behavior(self) -> None:
        self.write_environment("EMAIL_NOTIFICATIONS_ENABLED=false\n")

        rendered = self.render()

        self.assertIn("    - receiver: telegram\n", rendered)
        self.assertIn("      group_wait: 0s\n", rendered)
        self.assertIn("      group_interval: 5m\n", rendered)
        self.assertIn("      repeat_interval: 1h\n", rendered)
        self.assertIn("    url: 'http://alertmanager-bot:8080'\n", rendered)
        self.assertIn("  - send_resolved: true\n", rendered)
        self.assertNotIn("alertname=~", rendered)
        self.assertNotIn("- name: email\n", rendered)

    def test_renderer_restricts_local_config_and_keeps_runtime_yaml_readable(self) -> None:
        self.write_environment("EMAIL_NOTIFICATIONS_ENABLED=false\n")

        with patch.object(renderer.os, "chmod") as chmod:
            self.render()

        self.assertEqual(
            [call.args[1] for call in chmod.call_args_list],
            [0o600, 0o700, 0o644],
        )

    def test_enabled_email_has_a_separate_default_route_and_keeps_telegram(self) -> None:
        self.write_environment(
            "\n".join(
                [
                    "EMAIL_NOTIFICATIONS_ENABLED=true",
                    "EMAIL_SMTP_HOST=smtp.example.invalid",
                    "EMAIL_SMTP_PORT=587",
                    'EMAIL_SMTP_FROM="alerts:ops@example.invalid"',
                    "EMAIL_SMTP_TO=primary@example.invalid,backup@example.invalid",
                    "EMAIL_SMTP_USERNAME=monitoring",
                    'EMAIL_SMTP_PASSWORD="test-password:#value"',
                    "EMAIL_SMTP_REQUIRE_TLS=true",
                    "",
                ]
            )
        )

        rendered = self.render()

        self.assertIn('smtp_smarthost: "smtp.example.invalid:587"', rendered)
        self.assertIn('smtp_from: "alerts:ops@example.invalid"', rendered)
        self.assertIn(
            'smtp_auth_password_file: "/run/secrets/alertmanager_smtp_password"',
            rendered,
        )
        self.assertNotIn("test-password:#value", rendered)
        self.assertIn("      continue: true\n", rendered)
        self.assertIn("    - receiver: email\n", rendered)
        self.assertIn("      repeat_interval: 24h\n", rendered)
        self.assertIn(
            '        - "alertname=~\\"^(?:InstanceDown|IsJailed|ValidatorIsJailed)$\\""\n',
            rendered,
        )
        self.assertIn('- name: email\n  email_configs:\n', rendered)
        self.assertIn(
            '  - to: "primary@example.invalid,backup@example.invalid"\n'
            "    send_resolved: true\n",
            rendered,
        )

    def test_channel_policies_can_be_configured_independently(self) -> None:
        self.write_environment(
            "\n".join(
                [
                    "TELEGRAM_ALERTS=InstanceDown",
                    "TELEGRAM_GROUP_WAIT=30s",
                    "TELEGRAM_GROUP_INTERVAL=10m",
                    "TELEGRAM_REPEAT_INTERVAL=6h",
                    "EMAIL_NOTIFICATIONS_ENABLED=true",
                    "EMAIL_SMTP_HOST=smtp.example.invalid",
                    "EMAIL_SMTP_PORT=587",
                    "EMAIL_SMTP_FROM=alerts@example.invalid",
                    "EMAIL_SMTP_TO=primary@example.invalid",
                    "EMAIL_ALERTS=NodeDiskFull,NodeOutOfMemory",
                    "EMAIL_GROUP_WAIT=0s",
                    "EMAIL_GROUP_INTERVAL=1h",
                    "EMAIL_REPEAT_INTERVAL=48h",
                    "",
                ]
            )
        )

        rendered = self.render()

        self.assertIn('        - "alertname=~\\"^(?:InstanceDown)$\\""\n', rendered)
        self.assertIn("      group_wait: 30s\n", rendered)
        self.assertIn("      group_interval: 10m\n", rendered)
        self.assertIn("      repeat_interval: 6h\n", rendered)
        self.assertIn(
            '        - "alertname=~\\"^(?:NodeDiskFull|NodeOutOfMemory)$\\""\n',
            rendered,
        )
        self.assertIn("      group_interval: 1h\n", rendered)
        self.assertIn("      repeat_interval: 48h\n", rendered)

    def test_enabled_email_missing_smtp_host_fails_before_writing_runtime_config(self) -> None:
        # Deliberate sabotage: remove one required value and prove the guard rejects it.
        self.write_environment(
            "\n".join(
                [
                    "EMAIL_NOTIFICATIONS_ENABLED=true",
                    "EMAIL_SMTP_HOST=",
                    "EMAIL_SMTP_PORT=587",
                    "EMAIL_SMTP_FROM=alerts@example.invalid",
                    "EMAIL_SMTP_TO=primary@example.invalid",
                    "",
                ]
            )
        )

        with self.assertRaisesRegex(renderer.ConfigurationError, "EMAIL_SMTP_HOST"):
            self.render()

        self.assertFalse(self.output_file.exists())

    def test_unknown_alert_name_fails_before_output_is_replaced(self) -> None:
        # Deliberate sabotage: a stale name must not silently disable notifications.
        self.write_environment("TELEGRAM_ALERTS=AlertThatDoesNotExist\n")
        self.output_file.write_text("known-good-runtime-config\n", encoding="utf-8")

        with self.assertRaisesRegex(renderer.ConfigurationError, "AlertThatDoesNotExist"):
            self.render()

        self.assertEqual(
            self.output_file.read_text(encoding="utf-8"), "known-good-runtime-config\n"
        )

    def test_invalid_duration_fails_before_output_is_replaced(self) -> None:
        # Deliberate sabotage: unsupported durations must not reach Alertmanager.
        self.write_environment(
            "\n".join(
                [
                    "EMAIL_NOTIFICATIONS_ENABLED=true",
                    "EMAIL_SMTP_HOST=smtp.example.invalid",
                    "EMAIL_SMTP_PORT=587",
                    "EMAIL_SMTP_FROM=alerts@example.invalid",
                    "EMAIL_SMTP_TO=primary@example.invalid",
                    "EMAIL_REPEAT_INTERVAL=every-day",
                    "",
                ]
            )
        )
        self.output_file.write_text("known-good-runtime-config\n", encoding="utf-8")

        with self.assertRaisesRegex(renderer.ConfigurationError, "EMAIL_REPEAT_INTERVAL"):
            self.render()

        self.assertEqual(
            self.output_file.read_text(encoding="utf-8"), "known-good-runtime-config\n"
        )

    def test_repeated_or_disordered_duration_fails_before_output_is_replaced(self) -> None:
        # Deliberate sabotage: Alertmanager must not receive ambiguous repeated units.
        for value in ("1h1h", "5m1h", "1m1m"):
            with self.subTest(value=value):
                self.write_environment(f"TELEGRAM_REPEAT_INTERVAL={value}\n")
                self.output_file.write_text("known-good-runtime-config\n", encoding="utf-8")

                with self.assertRaisesRegex(
                    renderer.ConfigurationError, "TELEGRAM_REPEAT_INTERVAL"
                ):
                    self.render()

                self.assertEqual(
                    self.output_file.read_text(encoding="utf-8"),
                    "known-good-runtime-config\n",
                )

    def test_disabled_email_ignores_invalid_email_policy(self) -> None:
        self.write_environment(
            "\n".join(
                [
                    "EMAIL_NOTIFICATIONS_ENABLED=false",
                    "EMAIL_ALERTS=AlertThatDoesNotExist",
                    "EMAIL_REPEAT_INTERVAL=every-day",
                    "",
                ]
            )
        )

        rendered = self.render()

        self.assertIn("    - receiver: telegram\n", rendered)
        self.assertNotIn("- name: email\n", rendered)

    def test_shell_interpolation_is_rejected_without_execution(self) -> None:
        self.write_environment("EMAIL_NOTIFICATIONS_ENABLED=${UNSAFE_VALUE}\n")

        with self.assertRaisesRegex(renderer.ConfigurationError, "shell interpolation"):
            self.render()


if __name__ == "__main__":
    unittest.main()
