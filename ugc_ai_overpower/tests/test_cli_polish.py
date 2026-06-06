"""CLI polish tests: output, dashboard_launcher, and new subcommands.

22 tests total.
"""
from __future__ import annotations

import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# ══════════════════════════════════════════════════════════════════════
# output.py — 8 tests
# ══════════════════════════════════════════════════════════════════════


class TestOutput:
    def test_colorize_with_tty(self):
        from ugc_ai_overpower.cli.output import colorize, Colors
        # Force TTY
        with patch.object(sys.stdout, "isatty", return_value=True):
            result = colorize("hello", Colors.GREEN, bold=True)
            assert "\033[92m" in result
            assert "\033[1m" in result
            assert "hello" in result
            assert "\033[0m" in result

    def test_colorize_no_tty(self):
        from ugc_ai_overpower.cli.output import colorize, Colors
        with patch.object(sys.stdout, "isatty", return_value=False):
            result = colorize("hello", Colors.GREEN)
            assert result == "hello"

    def test_success_prefix(self):
        from ugc_ai_overpower.cli.output import success, Colors
        with patch.object(sys.stdout, "isatty", return_value=True):
            result = success("done")
            assert "✓" in result
            assert Colors.GREEN in result

    def test_error_prefix(self):
        from ugc_ai_overpower.cli.output import error, Colors
        with patch.object(sys.stdout, "isatty", return_value=True):
            result = error("failed")
            assert "✗" in result
            assert Colors.RED in result

    def test_warning_prefix(self):
        from ugc_ai_overpower.cli.output import warning, Colors
        with patch.object(sys.stdout, "isatty", return_value=True):
            result = warning("caution")
            assert "⚠" in result
            assert Colors.YELLOW in result

    def test_info_prefix(self):
        from ugc_ai_overpower.cli.output import info, Colors
        with patch.object(sys.stdout, "isatty", return_value=True):
            result = info("note")
            assert "ℹ" in result
            assert Colors.BLUE in result

    def test_header_renders_box(self):
        from ugc_ai_overpower.cli.output import header
        with patch.object(sys.stdout, "isatty", return_value=True):
            result = header("TEST")
            assert "┌" in result
            assert "┐" in result
            assert "│" in result
            assert "TEST" in result

    def test_progress_bar_lifecycle(self):
        from ugc_ai_overpower.cli.output import ProgressBar
        with patch.object(sys.stdout, "isatty", return_value=True):
            pb = ProgressBar(total=10, prefix="test", width=20)
            pb.update(3)
            assert pb.n == 3
            pb.finish()
            assert pb.n == 10
            assert pb._finished

    def test_table_renders(self):
        from ugc_ai_overpower.cli.output import table
        result = table(["A", "B"], [["1", "2"], ["3", "4"]])
        assert "┌" in result
        assert "A" in result
        assert "1" in result
        assert "4" in result
        assert "┘" in result

    


# ══════════════════════════════════════════════════════════════════════
# dashboard_launcher.py — 6 tests
# ══════════════════════════════════════════════════════════════════════


class TestDashboardLauncher:
    def test_dashboard_config_defaults(self):
        from ugc_ai_overpower.cli.dashboard_launcher import DashboardConfig
        cfg = DashboardConfig()
        assert cfg.host == "127.0.0.1"
        assert cfg.port == 8000
        assert cfg.reload is False
        assert cfg.workers == 1
        assert cfg.log_level == "info"

    def test_is_port_in_use_free(self):
        from ugc_ai_overpower.cli.dashboard_launcher import is_port_in_use
        # Port 0 is never in use (OS assigns random)
        with patch("socket.socket") as mock_sock:
            mock_instance = MagicMock()
            mock_sock.return_value.__enter__.return_value = mock_instance
            result = is_port_in_use(9999)
            assert result is False

    def test_is_port_in_use_taken(self):
        from ugc_ai_overpower.cli.dashboard_launcher import is_port_in_use
        with patch("socket.socket") as mock_sock:
            mock_instance = MagicMock()
            mock_instance.bind.side_effect = OSError("in use")
            mock_sock.return_value.__enter__.return_value = mock_instance
            result = is_port_in_use(9999)
            assert result is True

    def test_find_available_port(self):
        from ugc_ai_overpower.cli.dashboard_launcher import find_available_port
        # All ports free
        with patch(
            "ugc_ai_overpower.cli.dashboard_launcher.is_port_in_use",
            return_value=False,
        ):
            port = find_available_port(8000)
            assert port == 8000

    def test_find_available_port_skips_used(self):
        from ugc_ai_overpower.cli.dashboard_launcher import find_available_port
        used_ports = {8000, 8001}

        def side_effect(port, host="127.0.0.1"):
            return port in used_ports

        with patch(
            "ugc_ai_overpower.cli.dashboard_launcher.is_port_in_use",
            side_effect=side_effect,
        ):
            port = find_available_port(8000)
            assert port == 8002

    def test_launch_dashboard_port_in_use_exits(self):
        from ugc_ai_overpower.cli.dashboard_launcher import DashboardConfig, launch_dashboard
        with patch(
            "ugc_ai_overpower.cli.dashboard_launcher.is_port_in_use",
            return_value=True,
        ):
            with patch(
                "ugc_ai_overpower.cli.dashboard_launcher.find_available_port",
                return_value=8001,
            ):
                with pytest.raises(SystemExit) as exc:
                    launch_dashboard(DashboardConfig(port=8000))
                assert exc.value.code == 1

    def test_launch_dashboard_startup_error(self):
        from ugc_ai_overpower.cli.dashboard_launcher import DashboardConfig, launch_dashboard
        with patch(
            "ugc_ai_overpower.cli.dashboard_launcher.is_port_in_use",
            return_value=False,
        ):
            with patch(
                "ugc_ai_overpower.cli.dashboard_launcher.signal.signal",
            ):
                with patch("uvicorn.run", side_effect=Exception("startup failed")):
                    with pytest.raises(SystemExit) as exc:
                        launch_dashboard(DashboardConfig(port=9999))
                    assert exc.value.code == 1


# ══════════════════════════════════════════════════════════════════════
# New CLI subcommands — 8 tests
# ══════════════════════════════════════════════════════════════════════


class TestCLIStatusCommand:
    @patch.dict(os.environ, {
        "NOTION_TOKEN": "test",
        "MODAL_TOKEN_ID": "test",
        "MODAL_TOKEN_SECRET": "test",
        "FAL_KEY": "test",
    })
    @patch("ugc_ai_overpower.cli.output.sys.stdout.isatty", return_value=False)
    @patch("ugc_ai_overpower.core.content_bank_v2.ContentBankV2")
    def test_status_all_healthy(self, mock_bank, mock_tty):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = ["2024-01-01"]
        mock_bank.return_value._get_conn.return_value = mock_conn
        mock_bank.return_value._db_path = "/tmp/test.db"
        with patch.object(sys, "argv", ["main.py", "status"]):
            from ugc_ai_overpower.main import _cmd_status
            _cmd_status()

    @patch.dict(os.environ, {}, clear=True)
    @patch("ugc_ai_overpower.cli.output.sys.stdout.isatty", return_value=False)
    def test_status_all_missing(self, mock_tty):
        with patch.object(sys, "argv", ["main.py", "status"]):
            from ugc_ai_overpower.main import _cmd_status
            _cmd_status()

    @patch.dict(os.environ, {"NOTION_TOKEN": "test"})
    @patch("ugc_ai_overpower.cli.output.sys.stdout.isatty", return_value=False)
    @patch("ugc_ai_overpower.core.content_bank_v2.ContentBankV2")
    def test_status_json_output(self, mock_bank, mock_tty):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = None
        mock_bank.return_value._get_conn.return_value = mock_conn
        with patch.object(sys, "argv", ["main.py", "status", "--json"]):
            from ugc_ai_overpower.main import _cmd_status
            _cmd_status()


class TestCLIUICommand:
    @patch("ugc_ai_overpower.cli.dashboard_launcher.launch_dashboard")
    @patch("ugc_ai_overpower.cli.dashboard_launcher.is_port_in_use", return_value=False)
    def test_ui_default_args(self, mock_port, mock_launch):
        with patch.object(sys, "argv", ["main.py", "ui"]):
            from ugc_ai_overpower.main import _cmd_ui
            _cmd_ui()
            mock_launch.assert_called_once()

    @patch("ugc_ai_overpower.cli.dashboard_launcher.launch_dashboard")
    @patch("ugc_ai_overpower.cli.dashboard_launcher.is_port_in_use", return_value=False)
    def test_ui_custom_args(self, mock_port, mock_launch):
        with patch.object(sys, "argv", ["main.py", "ui", "--host", "0.0.0.0", "--port", "9000", "--reload", "--workers", "4"]):
            from ugc_ai_overpower.main import _cmd_ui
            _cmd_ui()
            mock_launch.assert_called_once()


class TestCLIDoEverything:
    @patch("ugc_ai_overpower.cli.output.sys.stdout.isatty", return_value=False)
    def test_do_everything_dry_run(self, mock_tty):
        with patch.object(sys, "argv", ["main.py", "do-everything", "--dry-run"]):
            from ugc_ai_overpower.main import _cmd_do_everything
            _cmd_do_everything()

    @patch("ugc_ai_overpower.cli.output.sys.stdout.isatty", return_value=False)
    @patch("ugc_ai_overpower.core.notion_sync.NotionDashboard")
    def test_do_everything_full_run(self, mock_notion, mock_tty):
        mock_nd = MagicMock()
        mock_nd.ready = True
        mock_notion.return_value = mock_nd
        with patch.object(sys, "argv", ["main.py", "do-everything", "--dry-run"]):
            from ugc_ai_overpower.main import _cmd_do_everything
            _cmd_do_everything()

    @patch("ugc_ai_overpower.cli.output.sys.stdout.isatty", return_value=False)
    def test_do_everything_no_args(self, mock_tty):
        """do-everything does not crash with no args."""
        with patch.object(sys, "argv", ["main.py", "do-everything"]):
            from ugc_ai_overpower.main import _cmd_do_everything
            _cmd_do_everything()
