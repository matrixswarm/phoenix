import uuid, time
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QGridLayout, QPushButton, QHBoxLayout
from matrix_gui.core.class_lib.packet_delivery.packet.standard.command.packet import Packet
from matrix_gui.core.panel.control_bar import PanelButton
from matrix_gui.core.emit_gui_exception_log import emit_gui_exception_log
from PyQt5.QtCore import QThread, QMetaObject, Qt, pyqtSlot, Q_ARG
from PyQt5.QtWidgets import QApplication
class Gameboard(QWidget):
    cache_panel = True

    def __init__(self, session_id, bus=None, node=None, session_window=None):
        super().__init__(session_window)

        try:
            self.session_id = session_id
            self.bus = bus
            self.node = node
            self.parent = session_window
            self._initialized = False

            if not self._initialized:
                self.last_player_pos = (0, 0)
                self.last_npc_list = []
                self.setLayout(self._build_layout())
                self._connect_signals()
                self._initialized = True

        except Exception as e:
            emit_gui_exception_log("Gameboard.__init__", e)

    def _build_layout(self):
        try:
            layout = QVBoxLayout()
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(10)

            # Title
            title = QLabel("🎮 NPC Simulator Panel")
            title.setAlignment(Qt.AlignCenter)
            title.setStyleSheet("font-weight: bold; font-size: 16px;")
            layout.addWidget(title)

            # Button row
            btn_row = QHBoxLayout()
            btn_row.setSpacing(6)
            buttons = [
                ("Start", self.start_stream_clicked),
                ("Stop", self.stop_stream_clicked),
                ("Hunt", self.hunt_clicked),
                ("Scatter", self.scatter_clicked),
                ("Ping", self.ping_clicked),
                ("Shield", self.shield_clicked),
                ("Lock", self.lock_clicked),
                ("Cowbell", self.cowbell_clicked)
            ]
            for label, handler in buttons:
                btn = QPushButton(label)
                btn.clicked.connect(handler)
                btn_row.addWidget(btn)
            layout.addLayout(btn_row)

            # Grid display
            self.grid_size = 20  # same as npc agent default
            self.grid = QGridLayout()
            self.grid.setSpacing(2)
            self.cells = []
            self.has_drawn = False
            for y in range(self.grid_size):
                row = []
                for x in range(self.grid_size):
                    cell = QLabel(" ")
                    cell.setFixedSize(20, 20)
                    cell.setAlignment(Qt.AlignCenter)
                    cell.setStyleSheet("border: 1px solid #333; background: #111; color: #fff;")
                    self.grid.addWidget(cell, y, x)
                    row.append(cell)
                self.cells.append(row)


            layout.addLayout(self.grid)
            return layout
        except Exception as e:
            emit_gui_exception_log("Gameboard._build_layout", e)

    def _update_grid(self, player_pos, npc_list):
        # Make sure we’re on the GUI thread
        if QThread.currentThread() != QApplication.instance().thread():
            print("[GRID] ⚠️ Update attempted from non-GUI thread. Scheduling safely.")
            QMetaObject.invokeMethod(
                self,
                "_update_grid_safe",
                Qt.QueuedConnection,
                Q_ARG(object, player_pos),
                Q_ARG(object, npc_list)
            )
            return

        # Already on GUI thread, call safe directly
        self._update_grid_safe(player_pos, npc_list)

    @pyqtSlot(object, object)
    def _update_grid_safe(self, player_pos, npc_list):
        try:
            grid_size = self.grid_size
            seen = set()

            # Clear grid
            for y in range(grid_size):
                for x in range(grid_size):
                    try:
                        if not self._is_valid_cell(x, y):
                            print(f"[GRID] 🚫 Skipping invalid NPC")
                            continue
                        self.cells[y][x].setText(" ")
                        self.cells[y][x].setStyleSheet("border: 1px solid #333; background: #111;")
                    except Exception as e:
                        print(f"[GRID] ❌ Failed to clear {x},{y} – {e}")

            # Draw player
            px, py = player_pos
            if 0 <= px < grid_size and 0 <= py < grid_size:
                self.cells[py][px].setText("@")
                self.cells[py][px].setStyleSheet("border: 1px solid #555; background: #444; color: #0f0;")

            # Draw NPCs
            for npc in npc_list:
                x = npc.get("x")
                y = npc.get("y")
                role = npc.get("role", "unknown")
                key = (x, y)

                if x is None or y is None:
                    print(f"[GRID] ⚠️ Skipping NPC with invalid coords: {npc}")
                    continue

                if 0 <= x < grid_size and 0 <= y < grid_size:
                    try:
                        if key in seen:
                            existing = self.cells[y][x].text()
                            if existing.isdigit():
                                self.cells[y][x].setText(str(int(existing) + 1))
                            else:
                                self.cells[y][x].setText("2")
                            continue

                        color = {
                            "scout": "#ff0",
                            "hunter": "#f00",
                            "follower": "#0cf"
                        }.get(role, "#fff")

                        if not self._is_valid_cell(x, y):
                            print(f"[GRID] 🚫 Skipping invalid NPC")
                            continue

                        self.cells[y][x].setText("o")
                        self.cells[y][x].setStyleSheet(f"border: 1px solid #444; background: #222; color: {color};")

                    except Exception as e:
                        print(f"[GRID] ❌ Failed to draw NPC at {x},{y} – {e}")
                else:
                    print(f"[GRID] 🚫 Out-of-bounds NPC: {npc}")

            self._overlap_warned = False

        except Exception as e:
            emit_gui_exception_log("Gameboard._update_grid", e)

    def _is_valid_cell(self, x, y):
        """Check if x and y are within grid bounds."""
        if x is None or y is None:
            return False
        return 0 <= x < self.grid_size and 0 <= y < self.grid_size

    def _connect_signals(self):
        if getattr(self, "_signals_connected", False):
            return
        scoped_handler = f"inbound.verified.npc_simulator.gameboard.response.{self.session_id}"
        self.bus.on(scoped_handler, self._handle_gameboard_response)
        print(f"[GAMEBOARD] 🎧 Listening on {scoped_handler}")
        print(f"[GAMEBOARD] ✅ Initialized panel for session {self.session_id}")

    # === Button Actions ===
    def hunt_clicked(self):
        self._send_action("hunt")

    def scatter_clicked(self):
        self._send_action("scatter")


    def ping_clicked(self): print("[NPC] Ping!")
    def shield_clicked(self): print("[NPC] Shield up!")
    def lock_clicked(self): print("[NPC] Lock!")
    def cowbell_clicked(self): print("[COWBELL] More Cowbell!!! 🚨🔔🐄")

    def _send_action(self, action):

        try:
            if action in ("start_npc_stream", "stop_npc_stream", "idle"):
                print(f"[NPC] 🚫 Blocked invalid action from _send_action(): '{action}'")
                return  # 🚫 Stop misrouted start/stop calls here

            uid = self.node.get("universal_id")
            token = str(uuid.uuid4())
            print(f"[NPC] Sending action '{action}' to agent {uid}")

            pk = Packet()
            payload = {
                "target_agent": uid,
                "session_id": self.session_id,
                "token": token,
                "return_handler": "npc_simulator.gameboard.response",
                "action": action
            }

            pk.set_data({
                "handler": "cmd_service_request",
                "ts": time.time(),
                "content": {
                    "service": "npc.swarm.control",
                    "payload": payload
                }
            })

            pk.set_payload_item("handler", "cmd_control_npcs")

            self.bus.emit(
                "outbound.message",
                session_id=self.session_id,
                channel="outgoing.command",
                packet=pk
            )
        except Exception as e:
            emit_gui_exception_log("Gameboard._send_action", e)

    def start_stream_clicked(self):
        self._send_command("cmd_start_npc_stream", service="npc.swarm.stream.start")

    def stop_stream_clicked(self):
        self._send_command("cmd_stop_npc_stream", service="npc.swarm.stream.stop")

    def _handle_gameboard_response(self, session_id, channel, source, payload, ts=None, **_):

        try:
            data = payload.get("content", {})
            print(f"[GAMEBOARD] 📨 Session={session_id} Data={data}")

            self.last_player_pos = data.get("player_pos", (0, 0))
            self.last_npc_list = data.get("npc_list", [])
            self.has_drawn = True  # mark that we’ve got a valid frame
            self._update_grid(self.last_player_pos, self.last_npc_list)
            self.update()  # Ask Qt to schedule a repaint
            self.repaint()  # Force an immediate repaint (for good measure)

        except Exception as e:
            emit_gui_exception_log("Gameboard._handle_gameboard_response", e)


    def showEvent(self, event):

        try:
            super().showEvent(event)
            if getattr(self, "has_drawn", False):  # only redraw if a real frame exists
                self._update_grid(self.last_player_pos, self.last_npc_list)
        except Exception as e:
            emit_gui_exception_log("Gameboard.showEvent", e)

    def get_panel_buttons(self):
        try:
            return [
                PanelButton("🎮", "NPC Panel", lambda: self.parent.show_specialty_panel(self))
            ]
        except Exception as e:
            emit_gui_exception_log("session_window._update_log_status_bar", e)

    def _send_command(self, cmd_handler, service, extra_payload=None):
        try:
            uid = self.node.get("universal_id")
            token = str(uuid.uuid4())

            pk = Packet()
            payload = {
                "target_agent": uid,
                "session_id": self.session_id,
                "return_handler": "npc_simulator.gameboard.response"
            }

            if extra_payload:
                payload.update(extra_payload)

            if cmd_handler == "cmd_start_npc_stream":
                payload["token"] = token

            pk.set_data({
                "handler": "cmd_service_request",
                "ts": time.time(),
                "content": {
                    "service": service,
                    "payload": payload
                }
            })

            pk.set_payload_item("handler", cmd_handler)

            self.bus.emit(
                "outbound.message",
                session_id=self.session_id,
                channel="outgoing.command",
                packet=pk
            )

        except Exception as e:
            emit_gui_exception_log("Gameboard._send_command", e)
