# Authored by Daniel F MacDonald and ChatGPT-5.1 (“The Generals”)
from PyQt6.QtWidgets import QFormLayout, QLineEdit, QComboBox
from .base_editor import BaseEditor

class Imap(BaseEditor):
    """Incoming IMAP editor."""

    def __init__(self, parent=None, new_conn=False, default_channel_options=None):
        super().__init__(parent, new_conn)

        self.default_channel = QComboBox()
        default_channel_options = default_channel_options or ["receive.email","payload.reception"]
        self.default_channel.addItems(default_channel_options)

        self.label = QLineEdit(self.generate_default_label())
        self.in_server = QLineEdit()
        self.in_port = QLineEdit()
        self.in_user = QLineEdit()
        self.in_pass = QLineEdit()
        self.in_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.in_encryption = QComboBox()
        self.in_encryption.addItems(["SSL", "STARTTLS", "TLS", "None"])

        layout = QFormLayout(self)
        layout.addRow("Label", self.label)
        layout.addRow("Server", self.in_server)
        layout.addRow("Port", self.in_port)
        layout.addRow("Username", self.in_user)
        layout.addRow("Password", self.in_pass)
        layout.addRow("Encryption", self.in_encryption)
        layout.addRow("Default Channel", self.default_channel)
        layout.addRow("Serial", self.serial)

    # Path override
    def get_directory_path(self):
        if self.label.text().lower().strip() == "backup":
            return ["config", "email_bk"]
        return ["config","email"]

    def deploy_fields(self):
        return {
            "incoming_server": self.in_server.text().strip(),
            "incoming_port": int(self.in_port.text() or 0),
            "incoming_username": self.in_user.text().strip(),
            "incoming_password": self.in_pass.text().strip(),
            "incoming_encryption": self.in_encryption.currentText(),
            "channel": self.default_channel.currentText(),
        }

    def on_load(self, data):
        self.label.setText(data.get("label", ""))
        self.serial.setText(data.get("serial", ""))
        self.in_server.setText(data.get("incoming_server", ""))
        self.in_port.setText(str(data.get("incoming_port", "")))
        self.in_user.setText(data.get("incoming_username", ""))
        self.in_pass.setText(data.get("incoming_password", ""))
        self.in_encryption.setCurrentText(data.get("incoming_encryption", "SSL"))
        self.default_channel.setCurrentText(data.get("channel", ""))

    def serialize(self):
        self._ensure_serial()
        return {
            "serial": self.serial.text().strip(),
            "label": self.label.text().strip(),
            "incoming_server": self.in_server.text().strip(),
            "incoming_port": int(self.in_port.text() or 0),
            "incoming_username": self.in_user.text().strip(),
            "incoming_password": self.in_pass.text().strip(),
            "incoming_encryption": self.in_encryption.currentText(),
            "channel": self.default_channel.currentText(),
        }

    def is_validated(self):
        if not self.in_server.text().strip():
            return False, "IMAP Server required."
        if not self.in_port.text().isdigit():
            return False, "IMAP Port must be numeric."
        return True, ""
