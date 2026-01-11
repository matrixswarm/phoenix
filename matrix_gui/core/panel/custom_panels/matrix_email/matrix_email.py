# Authored by Daniel F MacDonald and ChatGPT-5 aka The Generals
import time
import json
from PyQt6.QtCore import QMetaObject, Q_ARG, Qt
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QTextEdit, QMessageBox
)
from matrix_gui.core.class_lib.packet_delivery.packet.standard.command.packet import Packet
from matrix_gui.core.panel.custom_panels.interfaces.base_panel_interface import PhoenixPanelInterface
from matrix_gui.core.emit_gui_exception_log import emit_gui_exception_log
from matrix_gui.core.panel.control_bar import PanelButton


class MatrixEmail(PhoenixPanelInterface):
    cache_panel = True

    def __init__(self, session_id, bus, node=None, session_window=None):
        super().__init__(session_id, bus, node=node, session_window=session_window)
        self.node = node
        self.setLayout(self._build_ui())

    def _build_ui(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel("📧 Matrix Email Configuration"))

        # --- Process Packets Toggle ---
        proc_row = QHBoxLayout()
        proc_row.addWidget(QLabel("Process Packets:"))
        self.proc_combo = QComboBox()
        self.proc_combo.addItems(["false", "true"])
        proc_row.addWidget(self.proc_combo)
        layout.addLayout(proc_row)

        # --- Save Config Button ---
        btn_row = QHBoxLayout()
        save_btn = QPushButton("💾 Save Config")
        save_btn.clicked.connect(self._save_config)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        # --- Output Console ---
        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        layout.addWidget(QLabel("Agent Response:"))
        layout.addWidget(self.output_box)

        return layout

    def _save_config(self):
        """Push live configuration update to matrix_email agent."""
        try:
            proc_packets = 1 if self.proc_combo.currentText().strip().lower() == "true" else 0

            new_cfg = {
                "push_live_config": 1,
                "process_packets": proc_packets,
            }

            pk = Packet()
            pk.set_data({
                "handler": "cmd_update_agent",
                "content": {
                    "target_universal_id": self.node.get("universal_id", "matrix_email"),
                    "config": new_cfg
                },
                "ts": time.time()
            })

            self.bus.emit(
                "outbound.message",
                session_id=self.session_id,
                channel="outgoing.command",
                packet=pk,
            )

            QMessageBox.information(self, "Saved", "Matrix Email configuration updated successfully.")
        except Exception as e:
            emit_gui_exception_log("MatrixEmailConfigPanel._save_config", e)

    def _refresh_status(self):
        """Ask the matrix_email agent for its current status."""
        try:
            pk = Packet()
            pk.set_data({
                "handler": "cmd_service_request",
                "ts": time.time(),
                "content": {
                    "service": "matrix_email.status",
                    "payload": {
                        "session_id": self.session_id,
                        "return_handler": "matrix_email_panel.status_ack",
                    }
                }
            })
            self.bus.emit(
                "outbound.message",
                session_id=self.session_id,
                channel="outgoing.command",
                packet=pk,
            )
            self.output_box.append("📡 Requesting Matrix Email status...\n")
        except Exception as e:
            emit_gui_exception_log("MatrixEmailConfigPanel._refresh_status", e)

    def _status_ack(self, session_id, channel, source, payload, **_):
        """Display status payload from matrix_email."""
        try:
            if session_id != self.session_id:
                return
            content = payload.get("content", payload)
            formatted = json.dumps(content, indent=2)
            QMetaObject.invokeMethod(
                self.output_box,
                "setPlainText",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, f"📨 Matrix Email Status:\n{formatted}")
            )
        except Exception as e:
            emit_gui_exception_log("MatrixEmailConfigPanel._status_ack", e)

    def _connect_signals(self):
        super()._connect_signals() if hasattr(super(), "_connect_signals") else None
        self.bus.on("inbound.verified.matrix_email_panel.status_ack", self._status_ack)

    def _disconnect_signals(self):
        super()._disconnect_signals() if hasattr(super(), "_disconnect_signals") else None
        self.bus.off("inbound.verified.matrix_email_panel.status_ack", self._status_ack)

    def _handle_result(self, session_id, channel, source, payload, ts):
        """Display returned response from the email agent."""
        try:
            content = payload.get("content", {})
            response = content.get("response", "(no response)")
            self.output_box.append("\n" + "=" * 40 + f"\n📧 Email Agent Reply:\n{response}")
        except Exception as e:
            emit_gui_exception_log("MatrixEmailConfigPanel._handle_result", e)

    def get_panel_buttons(self):
        return [PanelButton("📧", "Matrix Email", lambda: self.session_window.show_specialty_panel(self))]


