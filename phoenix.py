# Authored by Daniel F MacDonald and ChatGPT-5 aka The Generals
import os, sys, multiprocessing
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QMainWindow, QVBoxLayout, QApplication,
    QGraphicsDropShadowEffect, QMessageBox
)
#initialize bus
import matrix_gui.config.boot.boot
from multiprocessing import Process, Pipe
from matrix_gui.core.session_window import run_session
from PyQt5.QtCore import Qt, QPropertyAnimation
from PyQt5.QtGui import QColor
from matrix_gui.modules.vault.crypto.vault_handler import load_vault_singlefile
from matrix_gui.modules.vault.services.vault_singleton import VaultSingleton
from matrix_gui.modules.vault.services.vault_obj import VaultObj
from matrix_gui.core.emit_gui_exception_log import emit_gui_exception_log
from PyQt5.QtWidgets import QStatusBar, QLabel
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QIcon
from matrix_gui.core.splash import PhoenixSplash
from matrix_gui.modules.vault.ui.vault_popup import VaultPasswordDialog
from matrix_gui.modules.vault.ui.vault_init_dialog import VaultInitDialog
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton
from matrix_gui.core.event_bus import EventBus
from matrix_gui.core.phoenix_control_panel import PhoenixControlPanel
from matrix_gui.util.resolve_matrixswarm_base import resolve_matrixswarm_base
from matrix_gui.core.panel.home.phoenix_static_panel import PhoenixStaticPanel
from matrix_gui.config.boot.globals import get_sessions

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
        self.main_layout.addWidget(self.control_panel)
        self.control_panel.setVisible(False)  # hide until vault unlock
        self.control_panel.setEnabled(False)
        self.control_panel.request_vault_save.connect(self._handle_vault_save)
        self.control_panel.request_vault_load.connect(self._handle_vault_reload)

        #static panel
        self.static_panel = PhoenixStaticPanel()
        self.main_layout.addWidget(self.static_panel)
        self.static_panel.setVisible(False)

        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("color: #33ff33; background-color: #222; font-family: Consolas;")
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
        self.unlock_button.setStyleSheet("""
                QPushButton {
                    background-color: #222;
                    color: white;
                    font-size: 18px;
                    font-weight: bold;
                    border: 2px solid #888;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    border: 2px solid #fff;
                }
            """)
        self.unlock_button.clicked.connect(self.unlock_vault)
        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(self.unlock_button)
        button_row.addStretch()

        # Center the unlock button vertically
        self.main_layout.addStretch(1)
        self.main_layout.addLayout(button_row)
        self.main_layout.addStretch(1)

        self.session_commands = {}
        self.forward_listeners = {}

        self.main_layout.setStretchFactor(self.control_panel, 0)  # fixed top
        #self.main_layout.setStretchFactor(self.status_bar, 0)  # fixed bottom

        # Optional: decorate with glow
        shadow = QGraphicsDropShadowEffect(self.unlock_button)
        shadow.setColor(QColor( 0, 0, 255))
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 0)
        self.unlock_button.setGraphicsEffect(shadow)

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

        EventBus.on("vault.update", self._on_vault_update)
        EventBus.on("session.open.requested", self.launch_session)
        EventBus.on("vault.unlocked", self._on_vault_unlocked_ui_flip)
        EventBus.on("vault.reopen.requested", self._on_vault_reopen_requested)

        self._start_pipe_monitor()

        self.show()

    def launch_session(self, session_id: str, deployment: dict, vault_data: dict = None):

        try:
            parent_conn, child_conn = Pipe()
            p = Process(target=run_session, args=(session_id, child_conn))
            p.start()

            parent_conn.send({
                "type": "init",
                "session_id": session_id,
                "deployment": deployment,
                "vault_data": vault_data
            })

            self.session_processes.append({"proc": p, "conn": parent_conn})
            self._active_sessions.add(session_id)
            self.status_sessions.setText(f"Sessions: {len(self._active_sessions)}")

            print(f"[MIRV] Launched session {session_id}, pid={p.pid}")


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
            # Remove from process list
            self.session_processes = [s for s in self.session_processes if s["conn"] != conn]
            # Remove from active sessions
            self._active_sessions.discard(sess["proc"].pid)
            self.status_sessions.setText(f"Sessions: {len(self._active_sessions)}")
            print(f"[MIRV] 🧹 Cleaned up dead session pid={sess['proc'].pid}")
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
                print(f"[VAULT] ✅ Deployment {dep_id} updated from session")

                # Save vault to disk
                self._handle_vault_save(self.vault_data)

                # Broadcast updated deployment to all sessions (including origin)
                for sess in self.session_processes:
                    try:
                        sess["conn"].send({
                            "type": "deployment_updated",
                            "deployment_id": dep_id,
                            "deployment": dep,
                        })
                        print(f"[VAULT] 🔄 Broadcasted update to session {sess['proc'].pid}")
                    except Exception as e:
                        print(f"[VAULT][WARN] Failed to forward deployment update: {e}")


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

    def _on_vault_reopen_requested(self, **kwargs):
        """
        Close current vault → hide UI → emit 'vault.closed' → clear singleton → relaunch unlock flow.
        """
        # 1) Best-effort: stop background workers/sessions
        try:
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

        # 2) Hide UI
        try:
            if getattr(self, "control_panel", None):
                self.control_panel.setVisible(False)
        except Exception:
            pass

        # 3) Lifecycle event + clear singleton
        old_path = getattr(self, "vault_path", None)
        try:
            EventBus.emit("vault.closed", vault_path=old_path)
        except Exception:
            pass
        try:
            VaultSingleton.clear()
        except Exception:
            pass

        # 4) Reset cockpit state
        self.vault_loaded = False
        self.vault_data = None
        self.vault_password = None
        self.vault_path = None

        # 5) Flip back to "locked" and immediately start open/create flow
        self.unlock_button.setVisible(True)
        self.unlock_button.setEnabled(True)
        self.unlock_button.raise_()
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
                if init_dialog.exec_() != init_dialog.Accepted:
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
            if dialog.exec_() != dialog.Accepted:
                return
            # Do NOT reload or re-emit here; the dialog already emitted 'vault.unlocked'.
            return

        except Exception as e:
            emit_gui_exception_log("PhoenixCockpit.unlock_vault", e)


def show_with_splash(app, main_cls, delay=5000):  # 5 seconds
    splash = PhoenixSplash()
    splash.show()
    QTimer.singleShot(delay, lambda: _launch(app, splash, main_cls))

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

    sys.exit(app.exec_())