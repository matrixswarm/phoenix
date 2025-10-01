from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt
from matrix_gui.core.panel.control_bar import PanelButton
from matrix_gui.core.panel.custom_panels.interfaces.base_panel_interface import PhoenixPanelInterface

class Config(PhoenixPanelInterface):
    cache_panel = True

    def __init__(self, session_id, bus=None, node=None, session_window=None):
        super().__init__(session_id, bus, node=node, session_window=session_window)
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

    def _connect_signals(self):
        pass  # no live signals yet

    def _disconnect_signals(self):
        pass  # nothing to disconnect

    def get_panel_buttons(self):
        return [PanelButton("⚙️", "Settings", lambda: self.session_window.show_specialty_panel(self))]

    def on_deployment_updated(self, deployment):
        self.deployment = deployment
        print("[CONFIG] 🔄 Deployment updated")