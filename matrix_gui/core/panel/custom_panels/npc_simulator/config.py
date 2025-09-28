from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt
from matrix_gui.core.panel.control_bar import PanelButton

class Config(QWidget):
    def __init__(self, session_id, bus=None, node=None, session_window=None):
        super().__init__(session_window)
        self.session_id = session_id
        self.bus = bus
        self.node = node
        self.parent = session_window
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("⚙️ NPC Simulator Config")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 14px;")

        info = QLabel(f"Agent: {node.get('name')} | ID: {node.get('universal_id')}")
        info.setAlignment(Qt.AlignCenter)
        info.setStyleSheet("font-size: 12px; color: #ccc;")

        placeholder = QLabel("Config panel loaded.\nSettings UI to be implemented.")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("background: #222; border: 1px solid #555; padding: 20px;")

        layout.addWidget(title)
        layout.addWidget(info)
        layout.addWidget(placeholder)
        self.setLayout(layout)

    def get_panel_buttons(self):
        return [
            PanelButton("⚙️", "Settings", lambda: print("[NPC] Config clicked"))
        ]