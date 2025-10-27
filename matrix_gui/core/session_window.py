# Authored by Daniel F MacDonald and ChatGPT-5 aka The Generals
import sys
import time
import datetime
from pathlib import Path
import inspect

import copy
from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtWidgets import QStackedWidget
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QToolBar,
    QGroupBox, QLabel, QApplication
)
from matrix_gui.modules.net import deployment_connector
from matrix_gui.core.panel.control_bar import PanelButton
from matrix_gui.core.panel.agent_detail.agent_detail_panel import AgentDetailPanel
from matrix_gui.core.panel.crypto_alert.crypto_alert import CryptoAlertPanel
from matrix_gui.core.panel.delete_agent_panel import DeleteAgentPanel
from matrix_gui.theme.utils.hive_ui import StatusLabel
from matrix_gui.core.emit_gui_exception_log import emit_gui_exception_log
from matrix_gui.core.panel.log_panel.log_panel import LogPanel
from matrix_gui.core.panel.agent_tree.agent_tree import PhoenixAgentTree
from matrix_gui.modules.net.deployment_connector import _connect_single
from matrix_gui.core.dispatcher.inbound_dispatcher import InboundDispatcher
from matrix_gui.core.dispatcher.outbound_dispatcher import OutboundDispatcher
from matrix_gui.config.boot.globals import get_sessions
from matrix_gui.core.panel.restart_agent_panel import RestartAgentPanel
from matrix_gui.core.panel.replace_agent_panel import ReplaceAgentPanel
from matrix_gui.core.panel.hotswap_agent_panel import HotswapAgentPanel
from matrix_gui.core.panel.inject_agent_panel import InjectAgentPanel
from matrix_gui.core.panel.control_bar import ControlBar


def run_session(session_id, conn):

    app = QApplication.instance() or QApplication(sys.argv)

    # --- Dynamically locate and load the global Hive theme ---
    try:

        # Find the directory where this file (session_window.py) lives
        current_file = Path(inspect.getfile(inspect.currentframe())).resolve()

        # Walk upward until we hit the "matrix_gui" folder, then add /theme/hive_theme.qss
        for parent in current_file.parents:
            if parent.name == "matrix_gui":
                theme_path = parent / "theme" / "hive_theme.qss"
                break
        else:
            theme_path = Path.cwd() / "matrix_gui" / "theme" / "hive_theme.qss"

        if theme_path.exists():
            with open(theme_path, "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())
            print(f"[SESSION][INFO] Loaded theme dynamically from {theme_path}")
        else:
            print(f"[SESSION][WARN] Theme file not found at {theme_path}")

    except Exception as e:
        print("[SESSION][ERROR] Failed to load theme dynamically:", e)

    try:

        msg = conn.recv()
        deployment = copy.deepcopy(msg.get("deployment"))
        ctx = _connect_single(deployment, deployment.get("id"))
        inbound = InboundDispatcher(ctx.bus)
        outbound = OutboundDispatcher(ctx.bus, get_sessions(), deployment)
        ctx.inbound, ctx.outbound = inbound, outbound

        print(f"[DEBUG] Bus ID for session {session_id}: {id(ctx.bus)}")

        win = SessionWindow(
            deployment_id=deployment.get("id"),
            session_id=ctx.id,
            cockpit_id=session_id,
            deployment=deployment,
            conn=conn,
            bus=ctx.bus,
            inbound=inbound,
            outbound=outbound,
            ctx=ctx
        )

        # Add QTimer for pipe polling
        def poll_conn():
            if conn.poll():
                msg = conn.recv()
                if msg.get("type") == "deployment_updated":
                    win.handle_deployment_update(msg["deployment_id"], msg["deployment"])

        timer = QTimer()
        timer.timeout.connect(poll_conn)
        timer.start(200)  # every 200 ms

        # make window embeddable and not auto-activate
        win.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.SubWindow)
        win.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        win.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors, True)
        win.create()  # physically create the native handle without showing yet
        wid = int(win.winId())
        conn.send({"type": "window_ready", "session_id": session_id, "win_id": wid})
        win.show()


        try:
            app.exec()
        except Exception as e:
            import traceback
            print("[SESSION][FATAL] Exception in session loop:")
            traceback.print_exc()
        finally:
            try:
                conn.send({"type": "exit", "session_id": session_id})
            except Exception as inner:
                print(f"[SESSION][FATAL] Failed to signal exit: {inner}")


    except Exception as e:
        emit_gui_exception_log("session_window.run_session", e)


class SessionWindow(QMainWindow):
    def __init__(self, deployment_id, session_id, cockpit_id, deployment, conn, bus, inbound, outbound, ctx):
        super().__init__()
        try:

            self.deployment_id=deployment_id

            self._hb_timer = QTimer(self)
            self._hb_timer.timeout.connect(self._send_heartbeat)
            self._hb_timer.start(2000)  # every 2 seconds

            self.conn = conn
            self.session_id = session_id
            self.cockpit_id = cockpit_id
            self.deployment = deployment
            self.bus = bus
            self.inbound = inbound
            self.outbound = outbound
            self.ctx = ctx
            self._panel_cache = {}

            self.active_log_token = None
            self.log_paused = False
            self.last_log_ts = None
            self.current_log_title = ""

            # refs to Panels
            self._restart_agent_panel=None
            self._replace_panel=None
            self._hotswap_panel=None
            self._inject_panel = None
            self._delete_agent_panel=None

            self.resize(1000, 700)
            self.setMinimumHeight(650)

            # Panels
            self.tree_wrapper = self._build_tree_panel()
            self.inspector_wrapper = self._build_inspector_panel()
            self.console_wrapper = self._build_log_panel()
            self.console_wrapper.setObjectName("logs")

            # Status bar
            self.status_label = QLabel("Status: Initializing...")
            self._setup_status_bar()

            # Window Icon
            logo_path = "matrix_gui/theme/panel_logo.png"
            self.setWindowIcon(QIcon(logo_path))

            # Build the default cockpit panel (tree + inspector + logs)
            self.default_panel = QWidget()
            default_layout = QHBoxLayout()
            self.default_panel.setLayout(default_layout)
            self._setup_main_layout(default_layout)  # reuses existing builder
            default_layout.setContentsMargins(0, 0, 0, 0)
            default_layout.setSpacing(0)

            # Stacked widget for extensibility
            self.stacked = QStackedWidget()
            self.stacked.addWidget(self.default_panel)  # index 0 = default cockpit view
            self.setCentralWidget(self.stacked)

            # Control Bar
            self.control_bar = ControlBar(self)
            self.setIconSize(QSize(24, 24))
            self.setMinimumHeight(36)

            self.log_view.line_count_changed.connect(self._on_log_count_changed)

            #session window title
            label = self.deployment.get("label", "unknown")
            self.setWindowTitle(f"Matrix | deployment: {label} | session-id: {self.session_id}")

            # Events
            self.bus.on("channel.status", self._handle_channel_status)
            self.bus.on(f"inbound.verified.agent_log_view.update", self._handle_log_update)
            self.bus.on("gui.agent.selected", self._handle_agent_selected)
            self.bus.on("gui.log.token.updated", self._set_active_log_token)

        except Exception as e:
            emit_gui_exception_log("session_window.__init__", e)

    def _send_heartbeat(self):
        try:
            if self.conn:
                self.conn.send({"type": "heartbeat", "session_id": self.cockpit_id})
        except (BrokenPipeError, OSError):
            print("[SESSION][HEARTBEAT] Pipe lost; shutting down session.")
            self._hb_timer.stop()
            return



    def _set_active_log_token(self, session_id, token, agent_title=None, **_):
        try:
            self.active_log_token = token
            self.current_log_title = agent_title or "Unknown"
            self.log_view.set_active_token(token)  # reset log panel
            self._update_log_status_bar()
        except Exception as e:
            emit_gui_exception_log("session_window._set_active_log_token", e)

    def _handle_channel_status(self, session_id, channel, status, info=None, **_):
        try:
            msg = f"{channel}: {status}"
            self.status_label.setText(f"Status: {msg}")
        except Exception as e:
            emit_gui_exception_log("session_window._handle_channel_status", e)

    # --- Builders ---
    def _build_tree_panel(self):
        try:
            box = QGroupBox("Agent Tree")

            layout = QVBoxLayout()
            layout.setContentsMargins(6, 4, 6, 4)  # (L, T, R, B)
            layout.setSpacing(4)
            deployment = copy.deepcopy(self.deployment)
            self.tree = PhoenixAgentTree(session_id=self.session_id, bus=self.bus, conn=self.conn, deployment=deployment, parent=self)
            layout.addWidget(self.tree)
            box.setLayout(layout)
            return box
        except Exception as e:
            emit_gui_exception_log("session_window._build_tree_panel", e)

    def _handle_agent_selected(self, session_id, node, panels=None, **_):
        if not panels:
            # No specialty panels -> stay where you are
            return

        all_buttons = []

        for panel_name in panels:
            panel = self._load_custom_panel(panel_name, node)
            if panel and hasattr(panel, "get_panel_buttons"):
                panel_buttons = panel.get_panel_buttons() or []
                if panel_buttons:
                    print(f"[DEBUG] {panel_name} returned {len(panel_buttons)} buttons")
                    # Defer showing panel until its button is clicked
                    for btn in panel_buttons:
                        # wrap handler so it switches panel when clicked
                        def make_handler(real_handler, p=panel):
                            def _wrapped():
                                if real_handler:
                                    real_handler()
                                self.stacked.setCurrentWidget(p)

                            return _wrapped

                        all_buttons.append(PanelButton(btn.icon, btn.text, make_handler(btn.handler, panel)))
            else:
                print(f"[DEBUG] {panel_name} has no usable buttons, ignoring")

        # Only update toolbar if we actually collected something
        if all_buttons:
            self.control_bar.clear_secondary_buttons()
            self.control_bar.add_secondary_buttons(all_buttons)
        else:
            self.control_bar.clear_secondary_buttons()

    def _load_custom_panel(self, panel_name, node):
        try:
            cache_key = panel_name

            if cache_key in getattr(self, "_panel_cache", {}):
                return self._panel_cache[cache_key]

            mod_path, class_name = panel_name.rsplit(".", 1)
            class_name = "".join(part.capitalize() for part in class_name.split("_"))
            full_mod = f"matrix_gui.core.panel.custom_panels.{mod_path}.{panel_name.split('.')[-1]}"

            try:
                mod = __import__(full_mod, fromlist=[class_name])
            except ModuleNotFoundError:
                print(f"[WARNING][UI] Custom panel '{panel_name}' not found — skipping.")
                return None

            PanelClass = getattr(mod, class_name)
            panel = PanelClass(session_id=self.session_id, bus=self.bus, node=node, session_window=self)

            if getattr(PanelClass, "cache_panel", False):
                self._panel_cache[cache_key] = panel

            return panel

        except Exception as e:
            emit_gui_exception_log("SessionWindow._load_custom_panel", e)
            return None

    def _build_inspector_panel(self):

        try:
            self.detail_panel = AgentDetailPanel(session_id=self.session_id, bus=self.bus)
            self.detail_panel.inspector_group.setVisible(False)
            self.detail_panel.config_group.setVisible(False)
            return self.detail_panel
        except Exception as e:
            emit_gui_exception_log("session_window._build_inspector_panel", e)

    def show_default_panel(self):
        """
        Return to the main cockpit view without resetting the whole toolbar.
        """
        try:
            self.stacked.setCurrentWidget(self.default_panel)
            # Only clear the secondary rack — keep the default top row
            if hasattr(self, "control_bar"):
                self.control_bar.clear_secondary_buttons()
        except Exception as e:
            emit_gui_exception_log("SessionWindow.show_default_panel", e)

    def show_specialty_panel(self, panel: QWidget):

        try:
            if self.stacked.currentWidget() == panel:
                print("[DEBUG] Panel already active, skipping reset")
                return
            if self.stacked.indexOf(panel) == -1:
                self.stacked.addWidget(panel)
            self.stacked.setCurrentWidget(panel)

            self.control_bar.clear_secondary_buttons()

            if hasattr(panel, "get_panel_buttons"):
                buttons = panel.get_panel_buttons()
                for btn in buttons:
                    self.control_bar.add_secondary_buttons([btn])
            else:
                self.control_bar.hide_secondary_row()

            # Always keep the main rack visible
            self.control_bar.show_secondary_row()

            # Always add Home
            self.control_bar.add_prefix_button("🔙", "Main", self.show_default_panel)
            print("[DEBUG] Added Home button")
        except Exception as e:
            emit_gui_exception_log("session_window.show_specialty_panel", e)


    def _build_log_panel(self):

        try:
            box = QGroupBox("📄 Agent Logs")

            layout = QVBoxLayout()
            layout.setContentsMargins(6, 4, 6, 4)
            layout.setSpacing(4)

            # Status line inside the box
            self.log_status_label = StatusLabel("Agent Logs: —")
            layout.addWidget(self.log_status_label)

            # The actual log view
            self.log_view = LogPanel(self.bus, self)
            self.log_view.line_count_changed.connect(self._on_log_count_changed)
            layout.addWidget(self.log_view)

            box.setLayout(layout)
            return box
        except Exception as e:
            emit_gui_exception_log("session_window._build_log_panel", e)



    def _setup_main_layout(self, main_layout):
        try:
            right_column = QVBoxLayout()
            right_column.setContentsMargins(0, 0, 0, 0)
            right_column.setSpacing(0)
            right_column.addWidget(self.detail_panel.inspector_group)
            right_column.addWidget(self.detail_panel.config_group)
            right_column.addWidget(self.console_wrapper)

            right_panel = QWidget()
            right_panel.setLayout(right_column)
            right_column.setContentsMargins(0, 0, 0, 0)
            right_column.setSpacing(0)

            main_layout.addWidget(self.tree_wrapper)
            main_layout.addWidget(right_panel)
            main_layout.setStretch(0, 1)
            main_layout.setStretch(1, 3)
        except Exception as e:
            emit_gui_exception_log("session_window._setup_main_layout", e)

  
    # --- Log Update ---
    def _handle_log_update(self, session_id, channel, source, payload, **_):
        try:
            content = payload.get("content", {})
            token = content.get("token")
            lines = content.get("lines", [])


            if not lines:
                return

            # Token check
            if token != self.log_view.get_active_token():
                return

            if not self.log_paused:
                self.log_view.append_log_lines(lines)
                self.last_log_ts = time.time()

            self._update_log_status_bar()
        except Exception as e:
            emit_gui_exception_log("session_window._handle_log_update", e)


    def _on_log_count_changed(self, count: int):
        self._last_log_count = count
        self._update_log_status_bar()

    def toggle_config_panel(self):
        try:
            group = self.detail_panel.config_group
            visible = not group.isVisible()
            group.setVisible(visible)
            # Optionally: self.control_bar.config_btn.setChecked(visible)
        except Exception as e:
            emit_gui_exception_log("session_window.toggle_config_panel", e)

    def toggle_threads_panel(self):
        try:
            group = self.detail_panel.inspector_group
            visible = not group.isVisible()
            group.setVisible(visible)
            # Optionally: self.control_bar.threads_btn.setChecked(visible)
        except Exception as e:
            emit_gui_exception_log("session_window.toggle_threads_panel", e)

    def _toggle_log_pause(self):

        try:
            self.log_paused = not self.log_paused
            # Optionally: self.control_bar.pause_btn.setChecked(self.log_paused)
            self._update_log_status_bar()
        except Exception as e:
            emit_gui_exception_log("session_window._toggle_log_pause", e)

    def _launch_restart_agent(self, uid: str = None):
        try:
            if not isinstance(self._restart_agent_panel, RestartAgentPanel):
                self._restart_agent_panel = RestartAgentPanel(
                    session_id=self.session_id,
                    bus=self.bus,
                    conn=self.conn,
                    deployment=self.deployment,
                    parent=self
                )
            self._restart_agent_panel.launch(uid)
        except Exception as e:
            emit_gui_exception_log("session_window._launch_restart_agent_panel", e)

        # --- Delete Agent ---

    def _launch_delete_agent(self, uid: str = None):

        try:
            if not isinstance(self._delete_agent_panel, DeleteAgentPanel):
                self._delete_agent_panel = DeleteAgentPanel(
                    session_id=self.session_id,
                    bus=self.bus,
                    conn=self.conn,
                    deployment=self.deployment,
                    parent=self
                )
            self._delete_agent_panel.launch(uid)
        except Exception as e:
            emit_gui_exception_log("session_window._launch_delete_agent_modal", e)


    def _launch_replace_agent_source(self):
        try:

            if not isinstance(self._replace_panel, ReplaceAgentPanel):
                self._replace_panel = ReplaceAgentPanel(
                    session_id=self.session_id,
                    bus=self.bus,
                    conn=self.conn,
                    deployment=self.deployment,
                    parent=self
                )
            self._replace_panel.launch()
        except Exception as e:
            emit_gui_exception_log("session_window._launch_replace_agent_source", e)

    def _launch_hotswap_agent_modal(self, uid: str = None):
        try:

            if not isinstance(self._hotswap_panel, HotswapAgentPanel):

                self._hotswap_panel = HotswapAgentPanel(
                    session_id=self.session_id,
                    bus=self.bus,
                    conn=self.conn,
                    deployment=self.deployment,
                    parent=self
                )
            tree_data=self.tree.get_rendered_tree()
            self._hotswap_panel.launch(tree_data, uid)

        except Exception as e:
            emit_gui_exception_log("SessionWindow._launch_hotswap_agent_modal", e)

    def _launch_inject_agent_modal(self, uid: str = None):
        try:

            if not isinstance(self._inject_panel, InjectAgentPanel):

                self._inject_panel = InjectAgentPanel(
                    session_id=self.session_id,
                    bus=self.bus,
                    conn=self.conn,
                    deployment=self.deployment,
                    parent=self
                )

            self._inject_panel.launch(uid)

        except Exception as e:
            emit_gui_exception_log("SessionWindow._launch_inject_agent_modal", e)

    def show_crypto_alert_panel(self):
        if "crypto_alert_panel" not in self._panel_cache:
            panel = CryptoAlertPanel(
                session_id=self.session_id,
                bus=self.bus,
                session_window=self
            )
            self._panel_cache["crypto_alert_panel"] = panel
            self.stacked.addWidget(panel)
        else:
            panel = self._panel_cache["crypto_alert_panel"]

        self.show_specialty_panel(panel)


    def _update_log_status_bar(self):
        try:
            time_str = (
                datetime.datetime.fromtimestamp(self.last_log_ts).strftime("%H:%M:%S")
                if self.last_log_ts else "—"
            )
            mode = "⏸️ Paused" if self.log_paused else "📡 Live"
            label = self.current_log_title or "Unknown"

            # Show log status on the inside label (not the border)
            count = getattr(self, "_last_log_count", 0)
            self.log_status_label.setText(
                f"Agent Logs: {label} ({mode} at {time_str} – {count} lines)"
            )

        except Exception as e:
            emit_gui_exception_log("session_window._update_log_status_bar", e)

    # --- Other unchanged methods ---
    def _send_cmd(self, cmd): pass
    def _setup_status_bar(self):

        try:
            status_bar = QToolBar("Session Status", self)
            status_bar.setMovable(False)
            status_bar.addWidget(self.status_label)
            self.addToolBar(Qt.ToolBarArea.BottomToolBarArea, status_bar)
        except Exception as e:
            emit_gui_exception_log("session_window._update_log_status_bar", e)

    def save_deployment_to_vault(self):
        try:
            if self.conn:
                self.conn.send({
                    "type": "vault_update_request",
                    "deployment_id": self.deployment_id,
                    "deployment": self.deployment,
                })
                print(f"[DEBUG] Sending favorites for {self.deployment_id}: {self.deployment.get('terminal_favorites')}")
        except Exception as e:
            emit_gui_exception_log("SessionWindow.save_deployment_to_vault", e)

    def handle_deployment_update(self, dep_id, deployment):
        try:
            self.deployment = deployment

            if hasattr(self, "_panel_cache"):

                for panel in self._panel_cache.values():
                    if hasattr(panel, "on_deployment_updated"):
                        panel.on_deployment_updated(deployment)
        except Exception as e:
            emit_gui_exception_log("SessionWindow.handle_deployment_update", e)

    def closeEvent(self, event):
        print(f"[SESSION] {self.cockpit_id} closing, destroying session")
        try:
            if self.conn:
                try:
                    self.conn.send({
                        "type": "exit",
                        "session_id": self.cockpit_id
                    })
                except (BrokenPipeError, OSError):
                    print("[SESSION][EXIT] Pipe already closed – skipping exit signal.")
                finally:
                    self.conn.close()
            deployment_connector.destroy_session(self.session_id)

        except Exception as e:
            emit_gui_exception_log("SessionWindow.closeEvent.destroy_session", e)
        super().closeEvent(event)


