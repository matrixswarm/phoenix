# Commander & ChatGPT — Victory Always Edition
# MULTIPLEXER PANEL — Switch outbound transport channels
from PyQt6.QtWidgets import QVBoxLayout, QLabel, QComboBox, QGroupBox, QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog
from matrix_gui.core.emit_gui_exception_log import emit_gui_exception_log
class MultiplexerPanel(QDialog):
    """
    Transport Multiplexer UI Panel
    --------------------------------
    Provides 2 dropdowns:
      • payload.reception   (incoming)
      • outgoing.command    (outgoing)

    Incoming is fixed to matrix_websocket (greyed out).
    Outgoing defaults to matrix_https but adds matrix_email if deployed.
    """

    def __init__(self, session_id, bus, node, session_window):
        super().__init__(session_window)
        try:
            self.session_id = session_id
            self.bus = bus
            self.node = node
            self.session_window = session_window
            self.deployment = session_window.deployment

            self.setWindowTitle("Multiplexer")
            self.setMinimumSize(400, 200)
            self.setModal(False)  # Non-blocking



            layout = QVBoxLayout(self)
            layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            # Title
            title = QLabel("⚡ Transport Multiplexer")
            title.setStyleSheet("font-size: 18px; font-weight: bold;")
            layout.addWidget(title)

            # ------------------------------
            # Incoming Transport (reception)
            # ------------------------------
            incoming_group = QGroupBox("Incoming Transport (payload.reception)")
            ig_layout = QVBoxLayout()
            incoming_group.setLayout(ig_layout)

            self.incoming_dropdown = QComboBox()
            self.incoming_dropdown.addItem("matrix_websocket (contact swarm@matrixswarm.com)")
            self.incoming_dropdown.setEnabled(False)

            ig_layout.addWidget(self.incoming_dropdown)
            layout.addWidget(incoming_group)

            # ------------------------------
            # Outgoing Transport (commands)
            # ------------------------------
            outgoing_group = QGroupBox("Outgoing Transport (outgoing.command)")
            og_layout = QVBoxLayout()
            outgoing_group.setLayout(og_layout)

            self.outgoing_dropdown = QComboBox()

            # Default: matrix_https
            self.outgoing_dropdown.addItem("matrix_https")

            # Add matrix_email if present in deployment
            agents = self.deployment.get("agents", [])
            agent_names = [a.get("name", "").lower() for a in agents]
            if "matrix_email" in agent_names:
                self.outgoing_dropdown.addItem("matrix_email")

            og_layout.addWidget(self.outgoing_dropdown)

            # Apply Button
            apply_btn = QPushButton("Apply Transport Route")
            apply_btn.clicked.connect(self._apply_route)
            og_layout.addWidget(apply_btn)

            layout.addWidget(outgoing_group)

            layout.addStretch(1)

            close_btn = QPushButton("Close")
            close_btn.clicked.connect(self.close)
            layout.addWidget(close_btn)

        except Exception as e:
            emit_gui_exception_log("MultiplexerPanel.__init__", e)

    # ----------------------------------------------------------
    # APPLY TRANSPORT SELECTION
    # ----------------------------------------------------------
    def _apply_route(self):
        try:
            selected = self.outgoing_dropdown.currentText().strip()

            outbound = self.session_window.outbound_dispatcher
            outbound.preferred_channel = selected

            # Resolve the actual universal_id of the selected transport
            for a in self.deployment.get("agents", []):
                if a.get("name", "").lower() == selected.lower():
                    outbound.set_outbound_connector(a)
                    break

                self.session_window.outgoing_badge.setText(f"Outgoing: {selected}  ⚪")

            self.session_window.status_label.setText(
                f"Status: Outgoing command transport set to {selected}"
            )

            print(f"[MULTIPLEXER] Outgoing transport updated → {selected}")

        except Exception as e:
            emit_gui_exception_log("MultiplexerPanel._apply_route", e)

    def sync_with_current_connector(self):
        """
        Sync dropdown selection to match the actual active outbound connector.
        Handles both proto name ('smtp', 'https') and agent name ('matrix_email', 'matrix_https').
        """
        try:
            outbound = getattr(self.session_window, "outbound_dispatcher", None)
            if not outbound:
                print("[MULTIPLEXER] No outbound dispatcher found.")
                return

            agent = outbound.get_outbound_connection()
            if not agent or not isinstance(agent, dict):
                print("[MULTIPLEXER] No active agent found.")
                return

            connection = agent.get("connection",{})
            if not connection or not isinstance(connection, dict):
                print("[MULTIPLEXER] No active outbound connector found.")
                return

            current_proto = (connection.get("proto") or "").lower()

            # Try to extract the agent name (matrix_email, matrix_https, etc.)
            agent_name = agent.get("name", "").lower()

            print(f"[MULTIPLEXER][SYNC] active proto={current_proto}, agent={agent_name}")

            matched = False
            for i in range(self.outgoing_dropdown.count()):
                item = self.outgoing_dropdown.itemText(i).strip().lower()
                # broaden match to catch both proto and agent names
                if (
                        current_proto in item
                        or item.endswith(current_proto)
                        or (agent_name and agent_name in item)
                ):
                    self.outgoing_dropdown.setCurrentIndex(i)
                    matched = True
                    break

            if not matched:
                print(f"[MULTIPLEXER][SYNC] No dropdown match for proto={current_proto} agent={agent_name}")
            else:
                print(f"[MULTIPLEXER][SYNC] Dropdown synced → {self.outgoing_dropdown.currentText()}")

        except Exception as e:
            emit_gui_exception_log("MultiplexerPanel.sync_with_current_connector", e)

