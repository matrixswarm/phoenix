import uuid, time
from matrix_gui.core.class_lib.packet_delivery.packet.standard.command.packet import Packet
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QGridLayout
from PyQt5.QtCore import Qt
from matrix_gui.core.panel.control_bar import PanelButton

class Gameboard(QWidget):
    def __init__(self, session_id, bus=None, node=None, parent=None):
        super().__init__(parent)
        self.session_id = session_id
        self.bus = bus
        self.node = node

        layout = QVBoxLayout(self)

        title = QLabel("🎮 NPC Simulator Gameboard")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Simple 5x5 grid
        grid = QGridLayout()
        for r in range(5):
            for c in range(5):
                cell = QLabel(f"{r},{c}")
                cell.setAlignment(Qt.AlignCenter)
                cell.setStyleSheet("border: 1px solid #444; padding: 8px;")
                grid.addWidget(cell, r, c)
        layout.addLayout(grid)

        self.setLayout(layout)

    def get_panel_buttons(self):
        return [

            PanelButton("matrix_gui/resources/icons/panel/npc_simulator/gameboard/hunt.png", "Hunt", self.hunt_clicked),
            PanelButton("matrix_gui/resources/icons/panel/npc_simulator/gameboard/scatter.png", "Scatter", self.scatter_clicked),
            PanelButton("matrix_gui/resources/icons/panel/npc_simulator/gameboard/ping.png", "Ping", self.ping_clicked),
            PanelButton("matrix_gui/resources/icons/panel/npc_simulator/gameboard/shield.png", "Shield", self.shield_clicked),
            #PanelButton("matrix_gui/resources/icons/panel/npc_simulator/gameboard/crown.png", "Crown", self.crown_clicked),
            PanelButton("matrix_gui/resources/icons/panel/npc_simulator/gameboard/lock.png", "Lock", self.lock_clicked),
            PanelButton("matrix_gui/resources/icons/panel/npc_simulator/gameboard/cowbell.png", "Cowbell", self.cowbell_clicked),
        ]

    # Handlers
    def hunt_clicked(self):
        print("[NPC] Hunt!")

        uid = self.node.get("universal_id")
        token = str(uuid.uuid4())

        pk = Packet()
        pk.set_data({
            "handler": "cmd_service_request",
            "ts": time.time(),
            "content": {
                "service": "npc.swarm.control",
                "payload": {
                    "target_agent": uid,
                    "session_id": self.session_id,
                    "token": token,
                    "action": "hunt",
                    "return_handler": "npc_simulator.gameboard.response"
                }
            }
        })

        # Wire up a response listener once
        self.bus.on("npc_simulator.gameboard.response", self._handle_gameboard_response)

        self.bus.emit(
            "outbound.message",
            session_id=self.session_id,
            channel="outgoing.command",
            packet=pk
        )
        print(f"[GAMEBOARD] Sent hunt to {uid} with token={token}")

    def _handle_gameboard_response(self, payload, **_):
        print(f"[GAMEBOARD] 📨 Response received: {payload}")
        # You can update the UI grid, show a message, etc.
        # Example: if payload contains NPC positions:
        # self._update_grid(payload.get("npc_positions", []))

    def scatter_clicked(self): print("[NPC] Scatter!")
    def ping_clicked(self): print("[NPC] Ping!")
    def shield_clicked(self): print("[NPC] Shield up!")
    #def crown_clicked(self): print("[NPC] Crown!")
    def lock_clicked(self): print("[NPC] Lock!")
    def cowbell_clicked(self):
        print("[COWBELL] More Cowbell!!! 🚨🔔🐄")
        # TODO: play sound, animate, or alert all agents!