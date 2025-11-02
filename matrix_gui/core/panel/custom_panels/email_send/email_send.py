# Authored by Daniel F MacDonald and ChatGPT-5 aka The Generals
import time
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QTextEdit, QMessageBox, QComboBox
)
from matrix_gui.core.panel.custom_panels.interfaces.base_panel_interface import PhoenixPanelInterface
from matrix_gui.core.class_lib.packet_delivery.packet.standard.command.packet import Packet
from matrix_gui.core.panel.control_bar import PanelButton
from matrix_gui.core.emit_gui_exception_log import emit_gui_exception_log

class EmailSend(PhoenixPanelInterface):
    cache_panel = True

    def __init__(self, session_id, bus=None, node=None, session_window=None):
        super().__init__(session_id, bus, node=node, session_window=session_window)
        self.setLayout(self._build_layout())
        self.node=node

    def _build_layout(self):
        layout = QVBoxLayout()

        # === Connection dropdown ===
        self.conn_selector = QComboBox()
        layout.addWidget(QLabel("Select Email Connection"))
        layout.addWidget(self.conn_selector)

        # === Email form ===
        self.smtp_host = QLineEdit()
        self.smtp_port = QLineEdit()
        self.smtp_user = QLineEdit()
        self.smtp_pass = QLineEdit()
        self.smtp_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.view_pass_btn = QPushButton("👁 View")
        self.view_pass_btn.setCheckable(True)
        self.view_pass_btn.setFixedWidth(70)
        self.view_pass_btn.toggled.connect(self._toggle_password_visibility)

        self.to_address = QLineEdit()
        self.subject = QLineEdit()
        self.body = QTextEdit()

        form_fields = [
            ("SMTP Host", self.smtp_host),
            ("SMTP Port", self.smtp_port),
            ("From (email)", self.smtp_user),
            (None, self._make_pass_row()),  # password + view button
            ("To (email)", self.to_address),
            ("Subject", self.subject),
        ]

        for label, widget in form_fields:
            if label:
                row = QHBoxLayout()
                row.addWidget(QLabel(label))
                row.addWidget(widget)
                layout.addLayout(row)
            else:
                layout.addLayout(widget)

        layout.addWidget(QLabel("Body:"))
        layout.addWidget(self.body)

        self.send_btn = QPushButton("📧 Send Email")
        self.send_btn.clicked.connect(self._send_email)
        layout.addWidget(self.send_btn)

        # when selecting a different saved connection, auto-fill fields
        self.conn_selector.currentIndexChanged.connect(self._on_connection_selected)

        # preload connections from vault (if accessible)
        self._load_email_connections()

        return layout

    def _make_pass_row(self):
        """Return a layout row containing password box + view button."""
        row = QHBoxLayout()
        row.addWidget(QLabel("Password"))
        row.addWidget(self.smtp_pass)
        row.addWidget(self.view_pass_btn)
        return row

    def _toggle_password_visibility(self, checked):
        self.smtp_pass.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )
        self.view_pass_btn.setText("🙈 Hide" if checked else "👁 View")

    def _load_email_connections(self):
        """
        Populate dropdown using only the node's deployment data.
        Each session knows only its own deployment, so we extract the
        email connection(s) from self.node if present.
        """
        try:
            self.conn_selector.clear()
            self._connections = {}

            # safety: if node is missing or malformed
            if not isinstance(self.node, dict):
                self.conn_selector.addItem("No email agent context", userData=None)
                return

            tags = self.node.get("tags", {})
            conn_tag = tags.get("connection") or {}
            proto = conn_tag.get("proto")

            if proto != "email":
                self.conn_selector.addItem("No email connection assigned", userData=None)
                return

            # Retrieve all fields directly from node
            data = self.node.get("config", {}).get("email", {}) or {}
            if not data:
                self.conn_selector.addItem("No email config found", userData=None)
                return

            label = conn_tag.get("vault_ref", self.node.get("name", "email_connection"))
            addr = data.get("smtp_username") or data.get("smtp_server", "unknown")
            display = f"{label} ({addr})"

            self.conn_selector.addItem(display, userData=(label, data))
            self._connections[label] = data

            # prefill immediately
            self._on_connection_selected(0)
            print(f"[EMAIL PANEL] Loaded email connection from node: {display}")

        except Exception as e:
            print(f"[EMAIL PANEL][ERROR] Failed to load email connections: {e}")

    def _temp_load_email_connections(self):
        """Populate dropdown from the vault snapshot embedded in the session deployment."""
        try:
            # Each session holds a copy of its deployment inside self.session_window.deployment
            # The cockpit embeds vault data into that message at session launch.
            # THIS IS GOING TO BE STRIPPED NEAR FUTURE, VIOLATES THE HOLLYWOOD PRINCIPLE; GOING TO IMPLY A SINGLETON
            vault_data = getattr(self.session_window, "deployment", {}) or {}

            # Look for the vault_data['vault_data'] fallback (depends on serialization at launch)

            # Try to resolve connection_manager from vault or embedded section
            conn_mgr = vault_data.get("connection_manager", {})

            email_conns = conn_mgr.get("email", {})
            self._connections = email_conns

            self.conn_selector.clear()
            if not email_conns:
                self.conn_selector.addItem("No email connections found", userData=None)
                return

            for conn_id, data in email_conns.items():
                label = data.get("label", conn_id)
                addr = data.get("smtp_username", "") or data.get("smtp_server", "")
                self.conn_selector.addItem(f"{label}  ({addr})", userData=(conn_id, data))

            # auto-select first
            self.conn_selector.setCurrentIndex(0)
            self._on_connection_selected(0)

            print(f"[EMAIL PANEL] Loaded {len(email_conns)} email connections from vault.")

        except Exception as e:
            print(f"[EMAIL PANEL][ERROR] Failed to load email connections: {e}")

    def _on_connection_selected(self, index):
        """Auto-fill SMTP fields when user selects a connection."""
        try:
            if index < 0:
                return
            data = self.conn_selector.itemData(index)
            if not data:
                return

            # userData can be (conn_id, cfg) or just cfg depending on how loaded
            if isinstance(data, tuple) and len(data) == 2:
                _, cfg = data
            elif isinstance(data, dict):
                cfg = data
            else:
                print(f"[EMAIL PANEL][WARN] Unknown connection data format: {data}")
                return

            # fill in all known SMTP/IMAP fields
            self.smtp_host.setText(str(cfg.get("smtp_server", "")))
            self.smtp_port.setText(str(cfg.get("smtp_port", "")))
            self.smtp_user.setText(str(cfg.get("smtp_username", "")))
            self.smtp_pass.setText(str(cfg.get("smtp_password", "")))

            # optional pre-fill for convenience
            if cfg.get("smtp_username"):
                self.to_address.setText(cfg.get("smtp_username", ""))
            else:
                self.to_address.clear()

            self.subject.clear()
            self.body.clear()

            print(f"[EMAIL PANEL] Populated fields from connection: {cfg.get('smtp_server')}")

        except Exception as e:
            print(f"[EMAIL PANEL][ERROR] Failed to populate fields: {e}")

    def _send_email(self):
        try:

            pk = Packet()
            pk.set_data({
                "handler": "cmd_service_request",
                "ts": time.time(),
                "content": {
                    "service": "send_email.send",
                    "payload": {
                        "smtp_host": self.smtp_host.text().strip(),
                        "smtp_port": self.smtp_port.text().strip(),
                        "from": self.smtp_user.text().strip(),
                        "password": self.smtp_pass.text().strip(),
                        "to": self.to_address.text().strip(),
                        "subject": self.subject.text().strip(),
                        "body": self.body.toPlainText().strip(),
                    }
                }
            })

            self.bus.emit("outbound.message", session_id=self.session_id,
                          channel="outgoing.command", packet=pk)

            QMessageBox.information(self, "Email Sent", "Email sent to agent for delivery.")

        except Exception as e:
            emit_gui_exception_log("EmailSend._send_email", e)
            QMessageBox.critical(self, "Error", f"Failed to send email: {e}")

    def _connect_signals(self):
        pass

    def _disconnect_signals(self):
        pass

    def get_panel_buttons(self):
        return [PanelButton("📧", "EmailSend", lambda: self.session_window.show_specialty_panel(self))]

    def on_deployment_updated(self, deployment):
        self.deployment = deployment
