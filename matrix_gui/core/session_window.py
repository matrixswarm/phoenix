# Authored by Daniel F MacDonald and ChatGPT aka The Generals
import sys
import time
import datetime
import copy
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtWidgets import QStackedWidget
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QToolBar,
    QGroupBox, QLabel, QApplication
)
from matrix_gui.core.panel.control_bar import PanelButton
from matrix_gui.core.panel.agent_detail.agent_detail_panel import AgentDetailPanel
from matrix_gui.core.emit_gui_exception_log import emit_gui_exception_log
from matrix_gui.core.panel.log_panel.log_panel import LogPanel
from matrix_gui.core.panel.agent_tree.agent_tree import PhoenixAgentTree
from matrix_gui.modules.net.deployment_connector import _connect_single
from matrix_gui.core.dispatcher.inbound_dispatcher import InboundDispatcher
from matrix_gui.core.dispatcher.outbound_dispatcher import OutboundDispatcher
from matrix_gui.config.boot.globals import get_sessions
from matrix_gui.core.dialog.replace_agent_dialog import ReplaceAgentDialog
from matrix_gui.core.dialog.restart_agent_dialog import RestartAgentDialog
from matrix_gui.core.dialog.delete_agent_dialog import DeleteAgentDialog
from matrix_gui.core.panel.control_bar import ControlBar


def run_session(session_id, conn):

    try:
        msg = conn.recv()

        #deep copy, encase the vault is updated, you don't want to corrupt the vault data with
        # session data, updated node
        deployment = copy.deepcopy(msg.get("deployment"))

        # Create SessionContext + Bus wiring through deployment_connector
        ctx = _connect_single(deployment, deployment.get("id"))

        # Launch dispatchers (tied to ctx.bus)
        inbound = InboundDispatcher(ctx.bus)
        outbound = OutboundDispatcher(ctx.bus, get_sessions(), deployment)
        ctx.inbound, ctx.outbound = inbound, outbound

        # GUI launch
        app = QApplication(sys.argv)
        win = SessionWindow(
            session_id=ctx.id,
            cockpit_id=session_id,
            deployment=deployment,
            conn=conn,
            bus=ctx.bus,
            inbound=inbound,
            outbound=outbound
        )
        win.show()
        app.exec_()

    except Exception as e:
        emit_gui_exception_log("session_window.run_session", e)

class SessionWindow(QMainWindow):
    def __init__(self, session_id, cockpit_id, deployment, conn, bus, inbound, outbound):
        super().__init__()
        try:
            self.conn = conn
            self.session_id = session_id
            self.cockpit_id = cockpit_id
            self.deployment = deployment
            self.bus = bus
            self.inbound = inbound
            self.outbound = outbound

            self.active_log_token = None
            self.log_paused = False
            self.last_log_ts = None
            self.current_log_title = ""

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
            self.bus.on(f"inbound.verified.agent_log_view.update.{self.session_id}", self._handle_log_update)
            self.bus.on("gui.agent.selected", self._handle_agent_selected)
            self.bus.on("gui.log.token.updated", self._set_active_log_token)

        except Exception as e:
            emit_gui_exception_log("session_window.__init__", e)

    def _set_active_log_token(self, session_id, token, agent_title=None, **_):
        self.active_log_token = token
        self.current_log_title = agent_title or "Unknown"
        self.log_view.set_active_token(token)  # reset log panel
        self._update_log_status_bar()

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
            emit_gui_exception_log("session_window._update_log_status_bar", e)

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
            self.control_bar.clear_buttons()
            # add Home button at the end
            self.control_bar.add_button("🏠", "Home", self.show_default_panel)
            for btn in all_buttons:
                self.control_bar.add_button(btn.icon, btn.text, btn.handler)

            print("[DEBUG] Added Home button")
        else:
            print("[DEBUG] No specialty panel buttons to add; leaving toolbar unchanged")

    def _load_custom_panel(self, panel_name, node):
        try:
            mod_path, class_name = panel_name.rsplit(".", 1)

            # Normalize to PascalCase class name
            class_name = "".join(part.capitalize() for part in class_name.split("_"))

            # Import the full module, not just the package
            full_mod = f"matrix_gui.core.panel.custom_panels.{mod_path}.{panel_name.split('.')[-1]}"
            mod = __import__(full_mod, fromlist=[class_name])

            PanelClass = getattr(mod, class_name)
            return PanelClass(session_id=self.session_id, bus=self.bus, node=node)

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
            emit_gui_exception_log("session_window._update_log_status_bar", e)

    def show_default_panel(self):
        self.stacked.setCurrentWidget(self.default_panel)
        self.control_bar.reset_to_default()

    def show_specialty_panel(self, panel: QWidget):

        try:
            if self.stacked.currentWidget() == panel:
                print("[DEBUG] Panel already active, skipping reset")
                return
            if self.stacked.indexOf(panel) == -1:
                self.stacked.addWidget(panel)
            self.stacked.setCurrentWidget(panel)

            self.control_bar.clear_buttons()
            if hasattr(panel, "get_panel_buttons"):
                buttons = panel.get_panel_buttons()
                print(f"[DEBUG] get_panel_buttons returned {len(buttons)} items: {[b.text for b in buttons]}")
                for btn in buttons:
                    print(f"[DEBUG] Adding button: {btn.text} (icon={btn.icon})")
                    self.control_bar.add_button(btn.icon, btn.text, btn.handler)
            else:
                print("[DEBUG] Panel has no get_panel_buttons()")

            # Always add Home
            self.control_bar.add_button("🏠", "Home", self.show_default_panel)
            print("[DEBUG] Added Home button")
        except Exception as e:
            emit_gui_exception_log("session_window._update_log_status_bar", e)


    def _build_log_panel(self):

        try:
            box = QGroupBox("📄 Agent Logs")

            layout = QVBoxLayout()
            layout.setContentsMargins(6, 4, 6, 4)
            layout.setSpacing(4)

            # Status line inside the box
            from matrix_gui.theme.utils.hive_ui import StatusLabel
            self.log_status_label = StatusLabel("Agent Logs: —")
            layout.addWidget(self.log_status_label)

            # The actual log view
            self.log_view = LogPanel(self.bus, self)
            self.log_view.line_count_changed.connect(self._on_log_count_changed)
            layout.addWidget(self.log_view)

            box.setLayout(layout)
            return box
        except Exception as e:
            emit_gui_exception_log("session_window._update_log_status_bar", e)



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
            emit_gui_exception_log("session_window._update_log_status_bar", e)

    # --- Delete Agent ---
    def _launch_delete_agent_modal(self):

        try:
            deployment=copy.deepcopy(self.deployment)
            dlg = DeleteAgentDialog(session_id=self.session_id, bus=self.bus, conn=self.conn, deployment=deployment, parent=self)
            dlg.exec_()
        except Exception as e:
            emit_gui_exception_log("session_window._update_log_status_bar", e)

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
            emit_gui_exception_log("session_window._update_log_status_bar", e)


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
            emit_gui_exception_log("session_window._update_log_status_bar", e)

    def toggle_threads_panel(self):
        try:
            group = self.detail_panel.inspector_group
            visible = not group.isVisible()
            group.setVisible(visible)
            # Optionally: self.control_bar.threads_btn.setChecked(visible)
        except Exception as e:
            emit_gui_exception_log("session_window._update_log_status_bar", e)

    def _toggle_log_pause(self):

        try:
            self.log_paused = not self.log_paused
            # Optionally: self.control_bar.pause_btn.setChecked(self.log_paused)
            self._update_log_status_bar()
        except Exception as e:
            emit_gui_exception_log("session_window._update_log_status_bar", e)


    def _launch_restart_agent(self):

        try:
            deployment = copy.deepcopy(self.deployment)
            dlg = RestartAgentDialog(session_id=self.session_id, bus=self.bus, conn=self.conn, deployment=deployment ,parent=self)
            dlg.exec_()
        except Exception as e:
            emit_gui_exception_log("session_window._update_log_status_bar", e)


    def _launch_replace_agent_source(self):

        try:
            deployment=copy.deepcopy(self.deployment)
            dlg = ReplaceAgentDialog(session_id=self.session_id, bus=self.bus, conn=self.conn, deployment=deployment ,parent=self)
            dlg.exec_()
        except Exception as e:
            emit_gui_exception_log("session_window._update_log_status_bar", e)


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
            self.addToolBar(Qt.BottomToolBarArea, status_bar)
        except Exception as e:
            emit_gui_exception_log("session_window._update_log_status_bar", e)


    def closeEvent(self, ev):
        try:
            print(f"[SESSION] Window for {self.session_id} closing, notifying cockpit...")
            if self.conn:
                try:
                    self.conn.send({
                        "type": "exit",
                        "session_id": self.cockpit_id
                    })
                except Exception as e:
                    print(f"[SESSION][WARN] Could not notify cockpit: {e}")
        except Exception as e:
            emit_gui_exception_log("SessionWindow.closeEvent", e)
        finally:
            super().closeEvent(ev)