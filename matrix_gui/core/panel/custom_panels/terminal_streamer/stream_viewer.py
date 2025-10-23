# Authored by Daniel F MacDonald and ChatGPT-5 aka The Generals
import uuid, time
from PyQt6.QtWidgets import QWidget ,QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QLineEdit, QListWidget, QTextEdit
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QSplitter
from matrix_gui.core.class_lib.packet_delivery.packet.standard.command.packet import Packet
from matrix_gui.core.panel.control_bar import PanelButton
from matrix_gui.core.emit_gui_exception_log import emit_gui_exception_log
from matrix_gui.core.panel.custom_panels.interfaces.base_panel_interface import PhoenixPanelInterface
from collections import deque
from PyQt6.QtCore import QMetaObject, Qt, pyqtSlot

class StreamViewer(PhoenixPanelInterface):
    cache_panel = True

    def __init__(self, session_id, bus=None, node=None, session_window=None):
        super().__init__(session_id, bus, node=node, session_window=session_window)
        self.setLayout(self._build_layout())
        self._connect_signals()
        self.favorites = self.deployment.get("terminal_favorites", [])
        self._refresh_fav_list()
        self.auto_refresh = True
        self.scroll_btn.setChecked(True)
        self.scroll_btn.setText("Auto-Refresh: ON")
        self._pending_outputs = deque(maxlen=10)

    def _build_layout(self):
        try:
            layout = QVBoxLayout()

            # === Favorites ===
            self.fav_list = QListWidget()
            self.fav_list.itemDoubleClicked.connect(self._populate_from_favorite)

            self.del_btn = QPushButton("Delete")
            self.edit_btn = QPushButton("Edit")
            self.del_btn.clicked.connect(self._delete_favorite)
            self.edit_btn.clicked.connect(self._edit_favorite)

            fav_btn_row = QHBoxLayout()
            fav_btn_row.addWidget(self.del_btn)
            fav_btn_row.addWidget(self.edit_btn)

            fav_container = QWidget()
            fav_layout = QVBoxLayout(fav_container)
            fav_layout.addWidget(QLabel("⭐ Favorites"))
            fav_layout.addWidget(self.fav_list)
            fav_layout.addLayout(fav_btn_row)

            # === Terminal output ===
            self.output_box = QTextEdit()
            self.output_box.setReadOnly(True)
            self.output_box.setObjectName("OutputBox")

            # === Splitter (draggable divider) ===
            splitter = QSplitter(Qt.Orientation.Vertical)
            splitter.addWidget(fav_container)
            splitter.addWidget(self.output_box)
            splitter.setStretchFactor(1, 2)  # give more room to output box
            layout.addWidget(splitter)

            # === Command row ===
            cmd_row = QHBoxLayout()
            self.cmd_input = QLineEdit()
            self.refresh_input = QLineEdit()
            self.run_btn = QPushButton("Run")
            self.stop_btn = QPushButton("Stop")
            self.fav_btn = QPushButton("Add to Favorites")
            self.allowed_btn = QPushButton("List Allowed")
            self.scroll_btn = QPushButton("Auto-Scroll: ON")
            self.clear_btn = QPushButton("Clear")

            self.allowed_btn.clicked.connect(self._list_allowed)
            self.run_btn.clicked.connect(self._run_command)
            self.stop_btn.clicked.connect(self._stop_command)
            self.fav_btn.clicked.connect(self._add_to_favorites)
            self.scroll_btn.setCheckable(True)
            self.scroll_btn.setChecked(True)
            self.scroll_btn.clicked.connect(self._toggle_auto_scroll)
            self.clear_btn.clicked.connect(self._clear_output)

            cmd_row.addWidget(self.allowed_btn)
            cmd_row.addWidget(self.cmd_input)
            cmd_row.addWidget(self.refresh_input)
            cmd_row.addWidget(self.run_btn)
            cmd_row.addWidget(self.stop_btn)
            cmd_row.addWidget(self.fav_btn)
            cmd_row.addWidget(self.scroll_btn)
            cmd_row.addWidget(self.clear_btn)

            layout.addLayout(cmd_row)
            self._last_token = None
            return layout
        except Exception as e:
            emit_gui_exception_log("StreamViewer._build_layout", e)

    # --- CRUD ---
    def _refresh_fav_list(self):

        try:
            self.fav_list.clear()
            for fav in self.favorites:
                self.fav_list.addItem(f"{fav['cmd']} (refresh={fav.get('refresh', 0)})")
        except Exception as e:
            emit_gui_exception_log("StreamViewer._refresh_fav_list", e)

    def _add_to_favorites(self):
        try:
            cmd = self.cmd_input.text().strip()
            refresh = self.refresh_input.text().strip() or "0"
            if not cmd:
                return

            new_entry = {"cmd": cmd, "refresh": int(refresh)}
            self.favorites.append(new_entry)

            # sync into the canonical deployment
            self.session_window.deployment["terminal_favorites"] = self.favorites
            self.session_window.save_deployment_to_vault()
            self._refresh_fav_list()

        except Exception as e:
            emit_gui_exception_log("StreamViewer._add_to_favorites", e)

    def _populate_from_favorite(self, item):

        try:
            idx = self.fav_list.row(item)
            fav = self.favorites[idx]
            self.cmd_input.setText(fav["cmd"])
            self.refresh_input.setText(str(fav.get("refresh", 0)))
        except Exception as e:
            emit_gui_exception_log("StreamViewer._populate_from_favorite", e)

    def _stop_command(self):

        try:
            token = self._last_token = str(uuid.uuid4())
            pk = Packet()
            pk.set_data({
                "handler": "cmd_service_request",
                "ts": time.time(),
                "content": {
                    "service": "terminal.stream.stop",
                    "payload": {
                        "session_id": self.session_id,
                        "token": token,
                        "return_handler": "terminal_panel.update",
                        "stop": True
                    }
                }
            })
            self.bus.emit("outbound.message",
                          session_id=self.session_id,
                          channel="outgoing.command",
                          packet=pk)
        except Exception as e:
            emit_gui_exception_log("StreamViewer._stop_command", e)

    def _save_favorites(self):
        try:
            self.deployment["terminal_favorites"] = self.favorites
            if hasattr(self.session_window, "save_deployment_to_vault"):
                self.session_window.save_deployment_to_vault()
                print("Saving deployment to vault... ")
        except Exception as e:
            emit_gui_exception_log("StreamViewer._save_favorites", e)

    def on_deployment_updated(self, deployment):
        try:
            self.deployment = deployment
            self.favorites = deployment.get("terminal_favorites", [])
            self._refresh_fav_list()
        except Exception as e:
            emit_gui_exception_log("StreamViewer.on_deployment_updated", e)

    # --- Run Command ---
    def _run_command(self):
        try:
            cmd = self.cmd_input.text().strip()
            refresh = int(self.refresh_input.text().strip() or 0)
            if not cmd:
                return
            token = str(uuid.uuid4())

            pk = Packet()
            pk.set_data({
                "handler": "cmd_service_request",
                "ts": time.time(),
                "content": {
                    "service": "terminal.stream.start",
                    "payload": {
                        "command": cmd,
                        "refresh_sec": refresh,
                        "session_id": self.session_id,
                        "token": token,
                        "return_handler": "terminal_panel.update"
                    }
                }
            })
            self.bus.emit("outbound.message", session_id=self.session_id, channel="outgoing.command", packet=pk)
        except Exception as e:
            emit_gui_exception_log("StreamViewer._run_command", e)

    # --- Listen for results ---
    def _connect_signals(self):

        try:
            scoped = f"inbound.verified.terminal_panel.update.{self.session_id}"
            self.bus.on(scoped, self._handle_output)
        except Exception as e:
            emit_gui_exception_log("StreamViewer._connect_signals", e)

    def _disconnect_signals(self):
        try:
            scoped = f"inbound.verified.terminal_panel.update.{self.session_id}"
            self.bus.off(scoped, self._handle_output)
        except Exception as e:
            emit_gui_exception_log("StreamViewer._disconnect_signals", e)

    def _handle_output(self, session_id, channel, source, payload, **_):
        try:
            if not payload:
                return

            data = payload.get("content") or {}
            output = str(data.get("output") or "")
            token = data.get("token") or ""

            clear_needed = (
                    getattr(self, "auto_refresh", False)
                    and token
                    and getattr(self, "_last_token", None) != token
            )

            # enqueue data
            self._pending_outputs.append((output, clear_needed))
            # ask GUI thread to flush
            QMetaObject.invokeMethod(
                self,
                "_flush_pending_output",
                Qt.ConnectionType.QueuedConnection,
            )

        except Exception as e:
            emit_gui_exception_log("StreamViewer._handle_output", e)

    @pyqtSlot()
    def _flush_pending_output(self):
        if not self._pending_outputs:
            return
        output, clear_needed = self._pending_outputs.pop()
        self._pending_outputs.clear()

        if clear_needed:
            self.output_box.clear()
        self.output_box.append(output)
        if getattr(self, "auto_refresh", False):
            self.output_box.moveCursor(QTextCursor.MoveOperation.End)

    def _toggle_auto_scroll(self):
        self.auto_refresh = self.scroll_btn.isChecked()
        self.scroll_btn.setText("Auto-Refresh: ON" if self.auto_refresh else "Auto-Refresh: OFF")

    def _clear_output(self):
        try:
            self.output_box.clear()
        except Exception as e:
            emit_gui_exception_log("StreamViewer._clear_output", e)

    def get_panel_buttons(self):
        return [PanelButton("🖥️", "Terminal", lambda: self.session_window.show_specialty_panel(self))]

    def _list_allowed(self):
        try:
            token = str(uuid.uuid4())
            pk = Packet()
            pk.set_data({
                "handler": "cmd_service_request",
                "ts": time.time(),
                "content": {
                    "service": "terminal.allowed.list",
                    "payload": {
                        "session_id": self.session_id,
                        "token": token,
                        "return_handler": "terminal_panel.update"
                    }
                }
            })

            # clear output and wait for reply
            self.output_box.clear()
            self.output_box.append("Fetching allowed commands...\n")

            self.bus.emit(
                "outbound.message",
                session_id=self.session_id,
                channel="outgoing.command",
                packet=pk
            )
        except Exception as e:
            emit_gui_exception_log("StreamViewer._list_allowed", e)

    def _delete_favorite(self):
        try:
            row = self.fav_list.currentRow()
            if row >= 0 and row < len(self.favorites):
                self.favorites.pop(row)
                # sync with session_window deployment
                self.session_window.deployment["terminal_favorites"] = self.favorites
                self.session_window.save_deployment_to_vault()
                self._refresh_fav_list()
            else:
                print("[DEBUG] Delete ignored, no valid row selected")
        except Exception as e:
            emit_gui_exception_log("StreamViewer._delete_favorite", e)


    def _edit_favorite(self):
        try:
            row = self.fav_list.currentRow()
            if row >= 0:
                fav = self.favorites[row]
                # load into inputs
                self.cmd_input.setText(fav["cmd"])
                self.refresh_input.setText(str(fav.get("refresh", 0)))
                # mark which row is being edited
                self._editing_row = row
        except Exception as e:
            emit_gui_exception_log("StreamViewer._edit_favorite", e)