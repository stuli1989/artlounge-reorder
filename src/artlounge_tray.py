import os
import socket
import subprocess
import sys
import threading
import time
from typing import Optional

try:
    from PIL import Image, ImageDraw
    import pystray
except ImportError:
    print(
        "Missing dependencies: pystray, pillow\n"
        "Install them in your venv, e.g.:\n"
        "  src\\venv\\Scripts\\pip install pystray pillow"
    )
    sys.exit(1)


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = PROJECT_ROOT
DASHBOARD_DIR = os.path.join(SRC_DIR, "dashboard")
VENV_PYTHON = os.path.join(SRC_DIR, "venv", "Scripts", "python.exe")


class ArtLoungeTrayApp:
    def __init__(self) -> None:
        self.backend_proc: Optional[subprocess.Popen] = None
        self.frontend_proc: Optional[subprocess.Popen] = None
        self.lock = threading.Lock()
        self.status_lock = threading.Lock()
        self.backend_ok: bool = False
        self.frontend_ok: bool = False
        self._health_monitor_running: bool = False

        # Pre-create icon images for different states
        self._icon_warn = self._create_icon_image((255, 140, 0, 255))  # orange
        self._icon_ok = self._create_icon_image((0, 180, 0, 255))      # green

        self.icon = pystray.Icon(
            "ArtLoungeReorder",
            self._icon_warn,
            "Art Lounge Reorder",
            menu=pystray.Menu(
                pystray.MenuItem("Start / Restart", self.on_start),
                pystray.MenuItem("Stop", self.on_stop),
                pystray.MenuItem("Open Dashboard", self.on_open_dashboard),
                pystray.MenuItem("Exit Tray", self.on_exit),
            ),
        )

    def _create_icon_image(self, fill_color) -> Image.Image:
        """Create a simple in-memory icon (circle with given fill color)."""
        size = 64
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        margin = 8
        draw.ellipse(
            (margin, margin, size - margin, size - margin),
            fill=fill_color,
            outline=(255, 255, 255, 255),
            width=2,
        )
        return image

    def _set_icon_state(self) -> None:
        """Update tray icon color based on current health."""
        try:
            with self.status_lock:
                healthy = self.backend_ok and self.frontend_ok
            new_icon = self._icon_ok if healthy else self._icon_warn
            if self.icon.icon is not new_icon:
                self.icon.icon = new_icon
                self.icon.title = (
                    "Art Lounge Reorder (running)"
                    if healthy
                    else "Art Lounge Reorder (starting / issue)"
                )
                self.icon.update()
        except Exception:
            # Never let UI update errors crash the tray
            pass

    # Status helpers ------------------------------------------------------

    @staticmethod
    def _port_is_open(port: int, host: str = "127.0.0.1") -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            try:
                sock.connect((host, port))
                return True
            except OSError:
                return False

    def _backend_running(self) -> bool:
        with self.lock:
            if self.backend_proc and self.backend_proc.poll() is None:
                return True
        # Fallback: check port in case backend was started outside the tray
        return self._port_is_open(8000)

    def _frontend_running(self) -> bool:
        with self.lock:
            if self.frontend_proc and self.frontend_proc.poll() is None:
                return True
        # Vite default port
        return self._port_is_open(5173)

    def _notify(self, title: str, message: str) -> None:
        try:
            self.icon.notify(message, title=title)
        except Exception:
            # Best-effort only; don't crash if notifications fail
            pass

    def _health_monitor_loop(self) -> None:
        """Background loop to track backend/frontend health and update icon."""
        self._health_monitor_running = True
        try:
            while self._health_monitor_running:
                backend = self._backend_running()
                frontend = self._frontend_running()
                with self.status_lock:
                    self.backend_ok = backend
                    self.frontend_ok = frontend
                self._set_icon_state()
                time.sleep(3.0)
        finally:
            self._health_monitor_running = False

    def _start_backend(self) -> None:
        with self.lock:
            if self.backend_proc and self.backend_proc.poll() is None:
                return

            if not os.path.exists(VENV_PYTHON):
                self._notify(
                    "Art Lounge",
                    "Could not find venv Python at venv\\Scripts\\python.exe.\n"
                    "Please create/activate the venv before starting.",
                )
                return

            cmd = [
                VENV_PYTHON,
                "-m",
                "uvicorn",
                "api.main:app",
                "--reload",
                "--port",
                "8000",
            ]
            try:
                self.backend_proc = subprocess.Popen(
                    cmd,
                    cwd=SRC_DIR,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            except FileNotFoundError:
                self._notify(
                    "Art Lounge",
                    "Failed to start backend (uvicorn not found). "
                    "Check that dependencies are installed in the venv.",
                )
            except Exception as exc:
                self._notify("Art Lounge", f"Error starting backend: {exc}")

    def _start_frontend(self) -> None:
        with self.lock:
            if self.frontend_proc and self.frontend_proc.poll() is None:
                return

            if not os.path.isdir(DASHBOARD_DIR):
                self._notify(
                    "Art Lounge",
                    "Dashboard directory not found. "
                    "Expected src\\dashboard with package.json.",
                )
                return

            # Use npm via cmd.exe so Windows can resolve npm.cmd correctly
            cmd = ["cmd.exe", "/c", "npm", "run", "dev"]
            try:
                self.frontend_proc = subprocess.Popen(
                    cmd,
                    cwd=DASHBOARD_DIR,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            except FileNotFoundError:
                self._notify(
                    "Art Lounge",
                    "Failed to start dashboard (npm not found).\n"
                    "Install Node.js and ensure npm is on your PATH.",
                )
            except Exception as exc:
                self._notify("Art Lounge", f"Error starting dashboard: {exc}")

    def _stop_backend(self) -> None:
        with self.lock:
            if self.backend_proc and self.backend_proc.poll() is None:
                self.backend_proc.terminate()
                try:
                    self.backend_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.backend_proc.kill()
            self.backend_proc = None

    def _stop_frontend(self) -> None:
        with self.lock:
            if self.frontend_proc and self.frontend_proc.poll() is None:
                self.frontend_proc.terminate()
                try:
                    self.frontend_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.frontend_proc.kill()
            self.frontend_proc = None

    # Tray menu callbacks -------------------------------------------------

    def on_start(self, _icon, _item) -> None:
        def do_start_or_restart() -> None:
            backend_running = self._backend_running()
            frontend_running = self._frontend_running()

            if backend_running or frontend_running:
                # Treat as restart for convenience
                self._notify("Art Lounge", "App is already running — restarting.")
                self._stop_backend()
                self._stop_frontend()
                # Small pause so ports free up
                time.sleep(1.0)
            else:
                self._notify("Art Lounge", "Starting local app...")

            # Starting or restarting: show warning state until health is confirmed
            with self.status_lock:
                self.backend_ok = False
                self.frontend_ok = False
            self._set_icon_state()

            self._start_backend()
            self._start_frontend()
            # Give the frontend a moment to boot before opening the browser
            self._open_dashboard_later()
            self._notify("Art Lounge", "App is running.")

        threading.Thread(target=do_start_or_restart, daemon=True).start()

    def on_stop(self, _icon, _item) -> None:
        def do_stop() -> None:
            was_running = self._backend_running() or self._frontend_running()

            if was_running:
                self._notify("Art Lounge", "Stopping local app...")
            else:
                # Even if we think it's not running, still try to clean up
                self._notify("Art Lounge", "App is not running, ensuring clean stop...")

            # Always attempt to stop any processes we started
            self._stop_backend()
            self._stop_frontend()

            if was_running:
                self._notify("Art Lounge", "App has been stopped.")
            else:
                self._notify("Art Lounge", "App was not running.")

            # Clear health flags so any final icon update (if visible) shows warning
            with self.status_lock:
                self.backend_ok = False
                self.frontend_ok = False
            self._set_icon_state()

            # Stop health monitor and remove tray icon entirely
            self._health_monitor_running = False
            self.icon.stop()

        threading.Thread(target=do_stop, daemon=True).start()

    def on_open_dashboard(self, _icon, _item) -> None:
        self._open_dashboard()

    def on_exit(self, icon, _item) -> None:
        # Stop processes then remove tray icon
        self._health_monitor_running = False
        self._stop_backend()
        self._stop_frontend()
        icon.stop()

    # Helpers --------------------------------------------------------------

    def _open_dashboard(self) -> None:
        import webbrowser

        webbrowser.open("http://localhost:5173", new=2)

    def _open_dashboard_later(self) -> None:
        # Small delay so that Vite dev server has time to bind to the port
        time.sleep(3)
        self._open_dashboard()

    # Public API -----------------------------------------------------------

    def run(self) -> None:
        # Start background health monitor
        threading.Thread(target=self._health_monitor_loop, daemon=True).start()
        self.icon.run()


def main() -> None:
    app = ArtLoungeTrayApp()
    app.run()


if __name__ == "__main__":
    main()

