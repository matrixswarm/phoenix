# Authored by Daniel F MacDonald and ChatGPT-5.1 (“The Generals”)
from PyQt6.QtWidgets import QFormLayout, QLineEdit, QComboBox
from .base_editor import BaseEditor

class Smtp(BaseEditor):
    """Outgoing SMTP editor."""

    def __init__(self, parent=None, new_conn=False, default_channel_options=None):
        super().__init__(parent, new_conn)

        self.default_channel = QComboBox()
        default_channel_options = default_channel_options or ["send.email","outgoing.command"]
        self.default_channel.addItems(default_channel_options)

        self.label = QLineEdit(self.generate_default_label())
        self.smtp_server = QLineEdit()
        self.smtp_port = QLineEdit()
        self.smtp_user = QLineEdit()
        self.smtp_pass = QLineEdit()
        self.smtp_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.smtp_to = QLineEdit()
        self.smtp_encryption = QComboBox()
        self.smtp_encryption.addItems(["SSL", "STARTTLS", "TLS", "None"])

        layout = QFormLayout(self)
        layout.addRow("Label", self.label)
        layout.addRow("SMTP Server", self.smtp_server)
        layout.addRow("SMTP Port", self.smtp_port)
        layout.addRow("Username", self.smtp_user)
        layout.addRow("Password", self.smtp_pass)
        layout.addRow("Send To", self.smtp_to)
        layout.addRow("Encryption", self.smtp_encryption)
        layout.addRow("Default Channel", self.default_channel)
        layout.addRow("Serial", self.serial)

    # Path override
    def get_directory_path(self):
        if self.label.text().lower().strip() == "email_bk":
            return ["config", "email_bk"]
        return ["config","email"]

    # --------------------------------
    def on_load(self, data):
        self.label.setText(data.get("label", ""))
        self.serial.setText(data.get("serial", ""))
        self.smtp_server.setText(data.get("smtp_server", ""))
        self.smtp_port.setText(str(data.get("smtp_port", "")))
        self.smtp_user.setText(data.get("smtp_username", ""))
        self.smtp_pass.setText(data.get("smtp_password", ""))
        self.smtp_to.setText(data.get("smtp_to", ""))
        self.smtp_encryption.setCurrentText(data.get("smtp_encryption", "SSL"))
        self.default_channel.setCurrentText(data.get("channel", ""))

    def deploy_fields(self):
        return {
            "smtp_server": self.smtp_server.text().strip(),
            "smtp_port": int(self.smtp_port.text() or 0),
            "smtp_username": self.smtp_user.text().strip(),
            "smtp_password": self.smtp_pass.text().strip(),
            "smtp_to": self.smtp_to.text().strip(),
            "smtp_encryption": self.smtp_encryption.currentText(),
            "channel": self.default_channel.currentText(),
        }

    # --------------------------------
    def serialize(self):
        self._ensure_serial()
        return {
            "serial": self.serial.text().strip(),
            "label": self.label.text().strip(),
            "smtp_server": self.smtp_server.text().strip(),
            "smtp_port": int(self.smtp_port.text() or 0),
            "smtp_username": self.smtp_user.text().strip(),
            "smtp_password": self.smtp_pass.text().strip(),
            "smtp_to": self.smtp_to.text().strip(),
            "smtp_encryption": self.smtp_encryption.currentText(),
            "channel": self.default_channel.currentText(),
        }

    # --------------------------------
    def is_validated(self):
        if not self.smtp_server.text().strip():
            return False, "SMTP Server required."
        if not self.smtp_port.text().isdigit():
            return False, "SMTP Port must be numeric."
        return True, ""
