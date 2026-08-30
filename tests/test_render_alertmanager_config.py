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

route:
  receiver: node-monitoring

receivers:
- name: 'node-monitoring'
  webhook_configs:
  - send_resolved: true
    url: 'http://alertmanager-bot:8080'
"""


class RenderAlertmanagerConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.env_file = self.root / "config" / ".env"
        self.template_file = self.root / "prometheus" / "alert_manager" / "alertmanager.yml"
        self.output_file = (
            self.root / "prometheus" / "alert_manager" / "alertmanager.runtime.yml"
        )
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

    def test_disabled_email_keeps_the_telegram_receiver_only(self) -> None:
        self.write_environment("EMAIL_NOTIFICATIONS_ENABLED=false\n")

        rendered = self.render()

        self.assertEqual(rendered, ALERTMANAGER_TEMPLATE)
        self.assertNotIn("email_configs:", rendered)
        self.assertIn("url: 'http://alertmanager-bot:8080'", rendered)

    def test_renderer_restricts_local_config_and_keeps_runtime_yaml_readable(self) -> None:
        self.write_environment("EMAIL_NOTIFICATIONS_ENABLED=false\n")

        with patch.object(renderer.os, "chmod") as chmod:
            self.render()

        self.assertEqual(
            [call.args[1] for call in chmod.call_args_list],
            [0o600, 0o700, 0o644],
        )

    def test_enabled_email_adds_smtp_and_resolved_receiver_configuration(self) -> None:
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
        self.assertIn("  email_configs:\n", rendered)
        self.assertIn(
            '  - to: "primary@example.invalid,backup@example.invalid"\n'
            "    send_resolved: true\n",
            rendered,
        )
        self.assertIn("  webhook_configs:\n", rendered)

    def test_enabled_email_after_a_template_without_a_final_newline_is_validly_separated(
        self,
    ) -> None:
        self.template_file.write_text(ALERTMANAGER_TEMPLATE.rstrip("\n"), encoding="utf-8")
        self.write_environment(
            "\n".join(
                [
                    "EMAIL_NOTIFICATIONS_ENABLED=true",
                    "EMAIL_SMTP_HOST=smtp.example.invalid",
                    "EMAIL_SMTP_PORT=587",
                    "EMAIL_SMTP_FROM=alerts@example.invalid",
                    "EMAIL_SMTP_TO=primary@example.invalid",
                    "",
                ]
            )
        )

        rendered = self.render()

        self.assertIn(
            "url: 'http://alertmanager-bot:8080'\n  email_configs:", rendered
        )

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

    def test_shell_interpolation_is_rejected_without_execution(self) -> None:
        self.write_environment("EMAIL_NOTIFICATIONS_ENABLED=${UNSAFE_VALUE}\n")

        with self.assertRaisesRegex(renderer.ConfigurationError, "shell interpolation"):
            self.render()


if __name__ == "__main__":
    unittest.main()
