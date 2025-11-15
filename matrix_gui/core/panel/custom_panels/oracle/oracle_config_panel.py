import uuid, time
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit, QMessageBox, QWidget
)
from matrix_gui.core.class_lib.packet_delivery.packet.standard.command.packet import Packet
from matrix_gui.core.panel.custom_panels.interfaces.base_panel_interface import PhoenixPanelInterface
from matrix_gui.core.emit_gui_exception_log import emit_gui_exception_log
from matrix_gui.core.panel.control_bar import PanelButton

class OracleConfigPanel(PhoenixPanelInterface):
    cache_panel = True

    def __init__(self, session_id, bus, node=None, session_window=None):
        super().__init__(session_id, bus, node=node, session_window=session_window)
        self.setLayout(self._build_ui())
        self.node=node
        self._connect_signals()

    def _build_ui(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel("🔮 Oracle Configuration"))

        # --- API Key ---
        key_row = QHBoxLayout()
        key_row.addWidget(QLabel("API Key:"))
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        toggle_btn = QPushButton("👁")
        toggle_btn.setFixedWidth(30)
        toggle_btn.clicked.connect(self._toggle_key_visibility)
        key_row.addWidget(self.api_key_edit)
        key_row.addWidget(toggle_btn)
        layout.addLayout(key_row)

        # --- Model ---
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo", "custom"])
        model_row.addWidget(self.model_combo)
        layout.addLayout(model_row)

        # --- Response Mode ---
        resp_row = QHBoxLayout()
        resp_row.addWidget(QLabel("Response Mode:"))
        self.response_combo = QComboBox()
        self.response_combo.addItems(["terse", "verbose", "creative"])
        resp_row.addWidget(self.response_combo)
        layout.addLayout(resp_row)

        # --- Test Prompt ---
        layout.addWidget(QLabel("Test Prompt:"))
        self.prompt_box = QTextEdit()
        layout.addWidget(self.prompt_box)

        test_btn = QPushButton("Send Test Prompt")
        test_btn.clicked.connect(self._send_test_prompt)
        layout.addWidget(test_btn)

        # --- Save Buttons ---
        btn_row = QHBoxLayout()
        save_btn = QPushButton("💾 Save Config")
        save_btn.clicked.connect(self._save_config)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        # --- Output ---
        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        layout.addWidget(QLabel("Oracle Response:"))
        layout.addWidget(self.output_box)
        return layout

    def _toggle_key_visibility(self):
        mode = self.api_key_edit.echoMode()
        self.api_key_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if mode == QLineEdit.EchoMode.Password else QLineEdit.EchoMode.Password
        )

    def _save_config(self):
        try:
            api_key = self.api_key_edit.text().strip()
            model = self.model_combo.currentText()
            response_mode = self.response_combo.currentText()

            # Build config dict dynamically — only include non-empty fields
            new_cfg = {"model": model, "response_mode": response_mode}
            if api_key:
                new_cfg["api_key"] = api_key  # update only if provided

            pk = Packet()
            pk.set_data({
                "handler": "cmd_update_agent",
                "content": {
                    "target_universal_id": self.node.get("universal_id", "oracle"),
                    "config": new_cfg,
                    "push_live_config": True
                },
                "ts": time.time()
            })

            self.bus.emit("outbound.message",
                          session_id=self.session_id,
                          channel="outgoing.command",
                          packet=pk)
            QMessageBox.information(self, "Saved",
                                    "Oracle configuration update sent.\n"
                                    "(Empty API Key field leaves existing key unchanged.)")

        except Exception as e:
            emit_gui_exception_log("OracleConfigPanel._save_config", e)


    def _send_test_prompt(self):
        try:

            prompt = self.prompt_box.toPlainText().strip()
            if not prompt:
                QMessageBox.warning(self, "No Prompt", "Enter a prompt to test.")
                return

            pk = Packet()
            pk.set_data({
                "handler": "cmd_msg_prompt",
                "ts": time.time(),
                "content": {
                    "prompt": prompt,
                    "target_universal_id": "oracle",
                    "query_id": str(uuid.uuid4()),
                    "return_handler": "oracle_panel.result"
                }
            })
            self.bus.emit("outbound.message", session_id=self.session_id, channel="outgoing.command", packet=pk)
        except Exception as e:
            emit_gui_exception_log("OracleConfigPanel._send_test_prompt", e)

    def _connect_signals(self):
        self.bus.on(f"inbound.verified.oracle_panel.result.{self.session_id}", self._handle_oracle_result)

    def _disconnect_signals(self):
        self.bus.off(f"inbound.verified.oracle_panel.result.{self.session_id}", self._handle_oracle_result)

    def _handle_oracle_result(self, session_id, channel, source, payload, ts):
        try:
            content = payload.get("content", {})
            response = content.get("response", "(no response)")
            self.output_box.append(f"> {response}")
        except Exception as e:
            emit_gui_exception_log("OracleConfigPanel._handle_oracle_result", e)

    def get_panel_buttons(self):
        return [PanelButton("🔮", "Oracle Config", lambda: self.session_window.show_specialty_panel(self))]

