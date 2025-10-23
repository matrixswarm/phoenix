# Authored by Daniel F MacDonald and ChatGPT-5 aka The Generals
import sys
print("Python:", sys.version)
try:
    from PyQt6.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
    print("Qt version:", QT_VERSION_STR)
    print("PyQt version:", PYQT_VERSION_STR)
except Exception as e:
    print("PyQt import error:", e)
import os, sys, multiprocessing
from PyQt6.QtGui import QWindow
from PyQt6.QtWidgets import QVBoxLayout, QMainWindow, QApplication,QGraphicsDropShadowEffect, QMessageBox, QStackedWidget, QTabBar, QStatusBar, QLabel, QDialog, QTabWidget
from matrix_gui.core.session_window import run_session
from PyQt6.QtCore import QTimer, Qt, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QIcon
import matrix_gui.config.boot.boot #don't take this out, looks like it's not doing anything but it setups event listeners
from matrix_gui.modules.vault.crypto.vault_handler import load_vault_singlefile
from matrix_gui.modules.vault.services.vault_singleton import VaultSingleton
from matrix_gui.modules.vault.services.vault_obj import VaultObj
from matrix_gui.core.emit_gui_exception_log import emit_gui_exception_log
from matrix_gui.core.event_bus import SessionRegistry
from matrix_gui.core.splash import PhoenixSplash
from matrix_gui.modules.vault.ui.vault_popup import VaultPasswordDialog
from matrix_gui.modules.vault.ui.vault_init_dialog import VaultInitDialog
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from matrix_gui.core.event_bus import EventBus
from matrix_gui.core.phoenix_control_panel import PhoenixControlPanel
from matrix_gui.util.resolve_matrixswarm_base import resolve_matrixswarm_base
from matrix_gui.core.panel.home.phoenix_static_panel import PhoenixStaticPanel
from matrix_gui.config.boot.globals import get_sessions
from matrix_gui.core.utils.ui_toast import show_toast

class PhoenixCockpit(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("MatrixSwarm :: PHOENIX COCKPIT")
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(1000, 600)
        self.vault_loaded = False
        self.vault_path = None
        self.vault_password = None

        self.sessions = None

        #number of active sessions
        self._active_sessions = set()

        base = resolve_matrixswarm_base()
        self.default_vault_dir = base / "matrix_gui" / "vaults"
        self.default_vault_dir.mkdir(parents=True, exist_ok=True)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # === Main Layout: control + tab zone + feed ===
        self.main_layout = QVBoxLayout(self.central_widget)

        # CONTROL PANEL (Top)
        self.control_panel = PhoenixControlPanel()


        self.status_bar = QStatusBar()

        self.status_bar.setFixedHeight(24)

        # Window Icon
        logo_path = "matrix_gui/theme/main_panel_logo.png"
        self.setWindowIcon(QIcon(logo_path))

        # status bar
        self.status_vault = QLabel("Vault: 🔒")
        self.status_deployments = QLabel("Deployments: 0")
        self.status_sessions = QLabel("Sessions: 0")

        self.status_bar = QStatusBar()
        self.status_bar.addPermanentWidget(self.status_vault)
        self.status_bar.addPermanentWidget(self.status_deployments)
        self.status_bar.addPermanentWidget(self.status_sessions)
        self.setStatusBar(self.status_bar)

        # === Legacy Controls (optional override) ===
        self.unlock_button = QPushButton("🔐 UNLOCK")
        self.unlock_button.setFixedSize(160, 60)


        self.unlock_button.clicked.connect(self.unlock_vault)
        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(self.unlock_button)
        button_row.addStretch()

        # top controls
        self.main_layout.setStretchFactor(self.control_panel, 0)

        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.session_commands = {}
        self.forward_listeners = {}

        self.main_layout.setStretchFactor(self.control_panel, 0)  # fixed top
        #self.main_layout.setStretchFactor(self.status_bar, 0)  # fixed bottom

        self.tab_stack = QTabWidget()
        self.tab_stack.setTabsClosable(True)
        self.tab_stack.tabCloseRequested.connect(self._on_tab_close_requested)
        self.main_layout.addWidget(self.tab_stack)

        self.static_panel = PhoenixStaticPanel()
        self.static_panel.setObjectName("HomeTab")
        self.tab_stack.addTab(self.static_panel, " 🜂 Dashboard")

        self.tab_stack.tabBar().setTabButton(0, QTabBar.ButtonPosition.RightSide, None)

        # Optional: decorate with glow
        shadow = QGraphicsDropShadowEffect(self.unlock_button)
        shadow.setColor(QColor( 0, 0, 255))
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 0)
        self.unlock_button.setGraphicsEffect(shadow)

        # --- Locked screen ---
        self.stack = QStackedWidget()
        self.main_layout.addWidget(self.stack)

        # --- Locked screen ---
        self.locked_screen = QWidget()
        lock_layout = QVBoxLayout(self.locked_screen)
        lock_layout.addStretch()
        lock_layout.addWidget(self.unlock_button, alignment=Qt.AlignmentFlag.AlignCenter)
        lock_layout.addStretch()

        # --- Unlocked cockpit ---
        self.unlocked_screen = QWidget()
        cockpit_layout = QVBoxLayout(self.unlocked_screen)
        cockpit_layout.setContentsMargins(0, 0, 0, 0)
        cockpit_layout.setSpacing(0)
        cockpit_layout.addWidget(self.control_panel)
        cockpit_layout.addWidget(self.tab_stack)
        cockpit_layout.setStretchFactor(self.tab_stack, 1)
        cockpit_layout.setStretch(0, 0)  # control panel fixed height
        cockpit_layout.setStretch(1, 0)  # static panel fixed height
        cockpit_layout.setStretch(2, 1)  # tab stack eats remainder


        self.stack.addWidget(self.locked_screen)  # index 0
        self.stack.addWidget(self.unlocked_screen)  # index 1
        self.stack.setCurrentIndex(0)  # start locked



        self.anim = QPropertyAnimation(shadow, b"blurRadius")
        self.anim.setStartValue(20)
        self.anim.setEndValue(50)
        self.anim.setDuration(1000)
        self.anim.setLoopCount(-1)
        self.anim.start()

        self.vault_data = None
        self.vault_password = None
        self.vault_path = None
        self.sessions = None
        self.dispatcher = None

        #status bar
        #self.status_bar = QStatusBar()
        #self.status_bar.setStyleSheet("color: #33ff33; background-color: #111; font-family: Courier;")
        #self.status_bar.setFixedHeight(24)
        #self.main_layout.addWidget(self.status_bar)

        #self.status_bar.addPermanentWidget(QLabel("Matrix Ready"))
        #self.status_bar.addPermanentWidget(QLabel("WS: Connected"))

        self.session_processes = []

        EventBus.on("vault.closed", self._destroy_all_sessions)
        EventBus.on("vault.update", self._on_vault_update)
        EventBus.on("session.open.requested", self.launch_session)
        EventBus.on("vault.unlocked", self._on_vault_unlocked_ui_flip)
        EventBus.on("vault.reopen.requested", self._on_vault_reopen_requested)

        self._start_pipe_monitor()

        self.show()

    def launch_session(self, session_id: str, deployment: dict, vault_data: dict = None):
        try:
            from multiprocessing import Process, Pipe
            parent_conn, child_conn = Pipe()
            p = Process(target=run_session, args=(session_id, child_conn))
            p.start()

            # --- Immediately send the deployment to the child (no handshake waiting) ---
            parent_conn.send({
                "type": "init",
                "session_id": session_id,
                "deployment": deployment,
                "vault_data": vault_data
            })

            # Wait for child to report its native window id
            win_id = None
            for _ in range(40):
                if parent_conn.poll(0.2):
                    msg = parent_conn.recv()
                    if msg.get("type") == "window_ready" and msg.get("session_id") == session_id:
                        win_id = int(msg.get("win_id"))
                        break

            if not win_id:
                print(f"[MIRV] ❌ Session {session_id} did not report a window id.")
                return

            # Build the embedded container tab
            remote_window = QWindow.fromWinId(win_id)
            remote_window.setFlags(Qt.WindowType.FramelessWindowHint)
            container = QWidget.createWindowContainer(remote_window)
            container.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            container.setMinimumSize(800, 600)
            container.setStyleSheet("background-color: #111;")

            tab = QWidget()
            layout = QVBoxLayout(tab)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(container)

            label = f"{deployment.get('label', 'session')} ▸ {session_id[:6]}"
            idx = self.tab_stack.addTab(tab, label)
            self.tab_stack.setCurrentIndex(idx)

            # Track process and IPC for cleanup
            self.session_processes.append({
                "proc": p,
                "conn": parent_conn,
                "session_id": session_id,
                "tab_index": idx
            })
            self._active_sessions.add(session_id)
            self.status_sessions.setText(f"Sessions: {len(self._active_sessions)}")

            print(f"[MIRV] 🚀 Embedded session {session_id} (pid={p.pid}, winid={win_id})")

        except Exception as e:
            emit_gui_exception_log("PhoenixCockpit.launch_session", e)

    def _start_pipe_monitor(self):
        self.pipe_timer = QTimer(self)
        self.pipe_timer.timeout.connect(self._poll_pipes)
        self.pipe_timer.start(200)

    def _poll_pipes(self):
        try:
            for sess in list(self.session_processes):
                conn = sess["conn"]
                try:
                    if conn.poll():
                        msg = conn.recv()
                        self._handle_session_msg(msg, conn)
                except (BrokenPipeError, EOFError, OSError):
                    print(f"[MIRV] 🛑 Session pipe closed for pid={sess['proc'].pid}")
                    self._cleanup_session(sess, conn)
        except Exception as e:
            emit_gui_exception_log("PhoenixCockpit._poll_pipes", e)

    def _cleanup_session(self, sess, conn):
        try:
            self.session_processes = [s for s in self.session_processes if s["conn"] != conn]
            self._active_sessions.discard(sess.get("session_id"))
            self.status_sessions.setText(f"Sessions: {len(self._active_sessions)}")
            print(f"[MIRV] 🧹 Cleaned up dead session {sess.get('session_id')}")
        except Exception as e:
            print(f"[MIRV][WARN] Failed to cleanup session: {e}")

    def _handle_session_msg(self, msg, conn):
        """
        Handle messages coming back from session processes.
        Ensures session counter always stays accurate.
        """

        try:
            mtype = msg.get("type")
            sid = msg.get("session_id")

            if mtype == "ready":
                print(f"[MIRV] Session {sid} READY")

            elif mtype == "swarm_feed":
                event = msg.get("event")
                if not event:
                    print("[MIRV][WARN] swarm_feed message missing event dict:", msg)
                    return
                if self.static_panel:
                    self.static_panel.append_feed_event(event)

            elif mtype == "vault_update_request":
                dep = msg.get("deployment")
                dep_id = msg.get("deployment_id")
                if not dep or not dep_id:
                    print(f"[VAULT][WARN] vault_update_request missing fields: {msg}")
                    return

                # Ensure vault_data structure exists
                self.vault_data = self.vault_data or {}
                self.vault_data.setdefault("deployments", {})

                # Merge into vault_data under correct deployment ID
                self.vault_data["deployments"][dep_id] = dep
                print(f"[VAULT] Deployment {dep_id} updated from session")

                # Save vault to disk
                self._handle_vault_save(self.vault_data)



                # Broadcast updated deployment to all sessions (including origin)
                for sess in self.session_processes:
                    try:
                        print(f"[VAULT][DEBUG] Sending update to {sess['session_id']} (pid={sess['proc'].pid})")
                        #sess["conn"].send({
                        #    "type": "deployment_updated",
                        #    "deployment_id": dep_id,
                        #    "deployment": dep,
                        #})
                        print(f"[VAULT] 🔄 Broadcasted update to session {sess['proc'].pid}")
                    except Exception as e:
                        print(f"[VAULT][WARN] Failed to forward deployment update to session {sess['session_id']}: {e}")


            elif mtype == "telemetry":
                status = msg.get("status")
                if status in ("connected", "ready", "active"):
                    self._active_sessions.add(sid)
                elif status in ("exit", "disconnected", "error"):
                    self._active_sessions.discard(sid)


                # always sync sessions label
                self.status_sessions.setText(f"Sessions: {len(self._active_sessions)}")

            elif mtype == "register_cmd":
                control = msg["control"]
                action = msg["action"]
                ctx = get_sessions().get(sid)
                try:
                    mod_path = f"matrix_gui.core.factory.cmd.{control}.{action}"
                    mod = __import__(mod_path, fromlist=["*"])
                    class_name = "".join([p.capitalize() for p in action.split("_")]) + "Command"
                    CmdClass = getattr(mod, class_name)

                    existing = next((c for c in self.session_commands.get(sid, [])
                                     if isinstance(c, CmdClass)), None)

                    if not existing:
                        cmd = CmdClass(sid, conn, ctx.bus)
                        cmd.initialize()
                        self.session_commands.setdefault(sid, []).append(cmd)
                        print(f"[MIRV] ✅ Registered {action} for session {sid}")
                except Exception as e:
                    print(f"[MIRV][ERROR] Failed to register cmd={action}: {e}")

            elif mtype == "cmd":
                control = msg["control"]
                action = msg["action"]
                try:
                    mod_path = f"matrix_gui.core.factory.cmd.{control}.{action}"
                    mod = __import__(mod_path, fromlist=["*"])
                    class_name = "".join([p.capitalize() for p in action.split("_")]) + "Command"
                    CmdClass = getattr(mod, class_name)
                    existing = next((c for c in self.session_commands.get(sid, [])
                                     if isinstance(c, CmdClass)), None)
                    if existing:
                        existing.fire_event(**msg)
                        print(f"[MIRV] ✅ Executed {action} via {CmdClass.__name__}")
                except Exception as e:
                    print(f"[MIRV][ERROR] Failed to execute cmd={action}: {e}")


            elif mtype == "vault_update_request":

                dep = msg.get("deployment")
                dep_id = msg.get("deployment_id")

                if not dep or not dep_id:
                    print(f"[VAULT][WARN] vault_update_request missing fields: {msg}")
                    return

                # Replace the whole deployment, not shallow merge
                self.vault_data["deployments"][dep_id] = dep
                print(f"[VAULT] ✅ Deployment {dep_id} updated (favorites: {dep.get('terminal_favorites')})")
                self._handle_vault_save(self.vault_data)
                for sess in self.session_processes:
                    try:
                        sess["conn"].send({
                            "type": "deployment_updated",
                            "deployment_id": dep_id,
                            "deployment": dep,
                        })
                    except Exception as e:
                        print(f"[VAULT][WARN] Failed to broadcast: {e}")

            elif mtype == "ui_toast":

                message = msg.get("message", "Action completed.")
                QTimer.singleShot(0, lambda: show_toast(message))

            elif mtype == "exit":
                sid = msg.get("session_id")
                print(f"[MIRV] 🛑 Session {sid} requested exit")
                # remove from processes list
                self.session_processes = [s for s in self.session_processes if s["conn"] != conn]
                # remove from active sessions
                self._active_sessions.discard(sid)
                self.status_sessions.setText(f"Sessions: {len(self._active_sessions)}")

            else:
                print(f"[MIRV] Unknown msg {msg}")

        except Exception as e:
            emit_gui_exception_log("PhoenixCockpit._handle_session_msg", e)

    def _on_vault_unlocked_ui_flip(self, **kwargs):

        try:
            # stash vault for later
            self.vault_data = kwargs.get("vault_data")
            self.vault_password = kwargs.get("password")
            self.vault_path = kwargs.get("vault_path")

            #unlock button
            self.stack.setCurrentIndex(1)


            self.fade = QPropertyAnimation(self.unlocked_screen, b"windowOpacity")
            self.fade.setStartValue(0.0)
            self.fade.setEndValue(1.0)
            self.fade.setDuration(400)
            self.fade.setEasingCurve(QEasingCurve.Type.InOutQuad)
            self.fade.start()

            # hand vault to the panel (it also listens to vault.unlocked and will start sessions/dispatcher itself)
            self.control_panel.vault_data = self.vault_data
            self.control_panel.vault_path = self.vault_path
            self.control_panel.password = self.vault_password
            self.control_panel.deployments = getattr(self, "deployments", {})
            self.control_panel.connection_groups = getattr(self, "connection_groups", {})
            self.control_panel.directives = getattr(self, "directives", {})


            #static panel
            self.static_panel.vault_data = self.vault_data
            self.static_panel.vault_path = self.vault_path
            self.static_panel._refresh_deployment_summary()
            self.static_panel.setVisible(True)

            self.unlock_button.hide()
            self.control_panel.setVisible(True)
            self.control_panel.setEnabled(True)

            dep_count = len((self.vault_data or {}).get("deployments", {}))
            self.status_vault.setText("Vault: 🔓")
            self.status_deployments.setText(f"Deployments: {dep_count}")
            self.status_sessions.setText("Sessions: 0")  # reset at unlock

        except Exception as e:
            emit_gui_exception_log("PhoenixControlPanel.launch", e)

    def closeEvent(self, ev):
        try:

            print("[MIRV] Cockpit closing, nuking all session processes...")

            # Stop pipe polling first
            if hasattr(self, "pipe_timer") and self.pipe_timer.isActive():
                self.pipe_timer.stop()

            for sess in self.session_processes:
                proc = sess["proc"]
                try:
                    if proc.is_alive():
                        # try graceful close first
                        try:
                            sess["conn"].send({"type": "exit", "session_id": "ALL"})
                        except Exception:
                            pass
                        proc.terminate()
                        print(f"[MIRV] Terminated PID {proc.pid}")
                except Exception as e:
                    print(f"[MIRV][ERROR] Could not kill process: {e}")
            super().closeEvent(ev)

        except Exception as e:
            emit_gui_exception_log("PhoenixCockpit.closeEvent", e)

    def _handle_vault_save(self, vault_data):
        try:
            EventBus.emit("vault.update", data=vault_data,
                          password=self.vault_password,
                          vault_path=self.vault_path)
            print("[PHOENIX][_handle_vault_save] Vault saved via bus.")

        except Exception as e:
            QMessageBox.critical(self, "Save Failed", f"Vault save failed:\n{e}")

    def _on_vault_update(self, **kwargs):

        try:
            new_data = kwargs.get("data", self.vault_data) or {}
            self.vault_data = self.vault_data or {}
            self.vault_data.setdefault("deployments", {})

            for dep_id, dep_val in list(new_data.get("deployments", {}).items()):
                if dep_id not in self.vault_data["deployments"]:
                    print(f"[VAULT][WARN] Attempted update for missing deployment {dep_id}, ignoring.")
                    continue
                if not isinstance(dep_val, dict):
                    print(f"[VAULT] 🚮 Purged corrupt deployment {dep_id}")
                    continue
                self.vault_data["deployments"][dep_id] = dep_val

            dep_count = len(self.vault_data.get("deployments", {}))
            self.status_deployments.setText(f"Deployments: {dep_count}")
        except Exception as e:
            emit_gui_exception_log("PhoenixCockpit._on_vault_update", e)


    def _handle_vault_reload(self):
        EventBus.emit("vault.reopen.requested", save=False)

    # in PhoenixCockpit._destroy_all_sessions
    def _destroy_all_sessions(self, **_):
        for sess in list(self.session_processes):
            try:
                if sess["conn"]:
                    sess["conn"].send({"type": "exit"})
            except Exception:
                pass
            try:
                sess["proc"].terminate()
            except Exception:
                pass

        self.session_processes.clear()
        self._active_sessions.clear()

        # wipe global session containers and tabs
        SessionRegistry.clear()

        while self.tab_stack.count() > 1:
            self.tab_stack.removeTab(1)

        self.status_sessions.setText("Sessions: 0")
        print("[VAULT] All sessions and UI tabs destroyed after vault close.")

    def _on_vault_reopen_requested(self, **kwargs):
        """
        Close current vault → hide UI → emit 'vault.closed' → clear singleton → relaunch unlock flow.
        """
        try:
            # Stop dispatcher/sessions
            if getattr(self, "dispatcher", None):
                try:
                    self.dispatcher._stop = True
                except Exception:
                    pass
                self.dispatcher = None
            if getattr(self, "sessions", None):
                try:
                    self.sessions.clear_all()
                except Exception:
                    pass
                self.sessions = None
        except Exception:
            pass

        # Hide UI elements
        try:
            if getattr(self, "control_panel", None):
                self.control_panel.setVisible(False)
                self.control_panel.setEnabled(False)

            if getattr(self, "static_panel", None):
                self.static_panel.setVisible(False)

            # Optional: hide the status bar if you want it blank until unlock
            # self.status_bar.hide()
        except Exception as e:
            print(f"[UI] Failed to hide elements: {e}")

        # Notify and clear state
        old_path = getattr(self, "vault_path", None)
        EventBus.emit("vault.closed", vault_path=old_path)
        VaultSingleton.clear()

        # Reset state
        self.vault_loaded = False
        self.vault_data = None
        self.vault_password = None
        self.vault_path = None

        # Restore locked screen
        self.stack.setCurrentIndex(0)

        self.unlock_button.setVisible(True)
        self.unlock_button.setEnabled(True)
        self.unlock_button.raise_()

        # Status bar refresh
        self.status_vault.setText("Vault: 🔒")
        self.status_deployments.setText("Deployments: 0")
        self.status_sessions.setText("Sessions: 0")

        # Relaunch unlock flow (optional: prompt user immediately)
        self.unlock_vault()

        #6) Update status bar
        self.status_vault.setText("Vault: 🔒")
        self.status_deployments.setText("Deployments: 0")
        self.status_sessions.setText("Sessions: 0")

    def unlock_vault(self):
        """
        Lean vault open/create coordinator.
        - If no vaults exist: run create dialog, then initialize and emit 'vault.unlocked'.
        - Else: run VaultPasswordDialog; it should decrypt, set the singleton, and emit 'vault.unlocked'.
        Cockpit does not re-load or re-emit; it just coordinates UI.
        """
        # First-run: no vault directory contents → create one
        try:
            if not os.listdir(self.default_vault_dir):
                init_dialog = VaultInitDialog(self)
                if init_dialog.exec() != init_dialog.Accepted:
                    return  # user cancelled

                self.vault_path = init_dialog.vault_path
                self.vault_password = init_dialog.vault_password

                # Initialize once, set singleton, emit unlocked (keep payload for compatibility)
                try:
                    data = load_vault_singlefile(self.vault_password, self.vault_path)
                    try:
                        # If you have a concrete VaultObj, set it; else you can
                        # adapt this to your VaultSingleton API.
                        vobj = VaultObj(
                            path=self.vault_path,
                            vault=data,
                            password=self.vault_password,
                            encryptor=None,
                            decryptor=None,
                        )
                        VaultSingleton.set(vobj)
                    except Exception:
                        # Fallback: at least clear/set a minimal state if your singleton API differs
                        pass

                    EventBus.emit(
                        "vault.unlocked",
                        vault_data=data,
                        password=self.vault_password,
                        vault_path=self.vault_path
                    )
                except Exception as e:
                    QMessageBox.critical(self, "Vault Error", f"Failed to initialize vault:\n{str(e)}")
                return

            # Normal path: unlock dialog handles decrypt + singleton + event
            dialog = VaultPasswordDialog(self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            # Do NOT reload or re-emit here; the dialog already emitted 'vault.unlocked'.
            return

        except Exception as e:
            emit_gui_exception_log("PhoenixCockpit.unlock_vault", e)

    def _on_tab_close_requested(self, index: int):
        try:
            # Find the matching session record
            sess = next((s for s in self.session_processes if s.get("tab_index") == index), None)
            if not sess:
                self.tab_stack.removeTab(index)
                return

            conn, proc, sid = sess["conn"], sess["proc"], sess["session_id"]

            try:
                # Give the session a chance to exit gracefully
                conn.send({"type": "exit"})
            except Exception:
                pass

            # Kill if needed
            if proc.is_alive():
                proc.terminate()

            # Remove the tab and bookkeeping
            self.tab_stack.removeTab(index)
            self._active_sessions.discard(sid)
            self.status_sessions.setText(f"Sessions: {len(self._active_sessions)}")

            # Drop the session record
            self.session_processes = [s for s in self.session_processes if s is not sess]

            print(f"[MIRV] 🧹 Closed session {sid}")

        except Exception as e:
            emit_gui_exception_log("PhoenixCockpit._on_tab_close_requested", e)


def show_with_splash(app, main_cls, delay=4000):
    splash = PhoenixSplash()
    splash.show()

    def launch():
        splash.hide()
        cockpit = main_cls()
        cockpit.show()
        # give Qt compositor a full frame before freeing splash
        QTimer.singleShot(500, splash.deleteLater)

    QTimer.singleShot(delay, launch)



def _launch(app, splash, main_cls):
    splash.close()
    cockpit = main_cls()
    cockpit.show()

if __name__ == '__main__':
    multiprocessing.freeze_support()


    app = QApplication(sys.argv)

    # Load Hive stylesheet
    try:
        with open("matrix_gui/theme/icons.qss", "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
        with open("matrix_gui/theme/hive_theme.qss", "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    except Exception as e:
        print(f"[HIVE/STYLE] Failed to load stylesheet: {e}")

    show_with_splash(app, PhoenixCockpit, delay=4000)

    sys.exit(app.exec())