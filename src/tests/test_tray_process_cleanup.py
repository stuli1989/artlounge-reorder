import threading
import unittest
from unittest.mock import Mock, patch

from artlounge_tray import ArtLoungeTrayApp


class _ImmediateThread:
    def __init__(self, target=None, daemon=None):
        self._target = target
        self.daemon = daemon

    def start(self):
        if self._target:
            self._target()


class TrayProcessCleanupTests(unittest.TestCase):
    @staticmethod
    def _make_bare_app() -> ArtLoungeTrayApp:
        app = ArtLoungeTrayApp.__new__(ArtLoungeTrayApp)
        app.lock = threading.Lock()
        app.status_lock = threading.Lock()
        app.backend_proc = None
        app.frontend_proc = None
        return app

    def test_stop_backend_always_attempts_port_cleanup(self):
        app = self._make_bare_app()
        app._kill_processes_on_port = Mock()

        ArtLoungeTrayApp._stop_backend(app)

        app._kill_processes_on_port.assert_called_once_with(8000)

    def test_stop_frontend_always_attempts_port_cleanup(self):
        app = self._make_bare_app()
        app._kill_processes_on_port = Mock()

        ArtLoungeTrayApp._stop_frontend(app)

        app._kill_processes_on_port.assert_called_once_with(5173)

    def test_stop_keeps_tray_icon_running(self):
        app = self._make_bare_app()
        app._backend_running = Mock(return_value=False)
        app._frontend_running = Mock(return_value=False)
        app._notify = Mock()
        app._stop_backend = Mock()
        app._stop_frontend = Mock()
        app._set_icon_state = Mock()
        app.backend_ok = True
        app.frontend_ok = True
        app._health_monitor_running = True
        app.icon = Mock()

        with patch("artlounge_tray.threading.Thread", _ImmediateThread):
            ArtLoungeTrayApp.on_stop(app, None, None)

        app.icon.stop.assert_not_called()
        app._stop_backend.assert_called_once()
        app._stop_frontend.assert_called_once()

    def test_port_scan_uses_dual_stack_netstat(self):
        completed = Mock(returncode=0, stdout="")
        with patch("artlounge_tray.subprocess.run", return_value=completed) as run_mock:
            ArtLoungeTrayApp._list_pids_listening_on_port(5173)

        cmd = run_mock.call_args[0][0]
        self.assertEqual(cmd, ["netstat", "-ano"])


if __name__ == "__main__":
    unittest.main()
