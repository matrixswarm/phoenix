# Authored by Daniel F MacDonald and ChatGPT-5 (“The Generals”)
from PyQt6.QtWidgets import QFormLayout, QLineEdit, QComboBox
from .base_editor import BaseEditor

class Discord(BaseEditor):

    def __init__(self, parent=None, new_conn=False, default_channel_options=None):
        super().__init__(parent, new_conn)

        self.label = QLineEdit(self.generate_default_label())
        self.default_channel = QComboBox()
        default_channel_options = default_channel_options or ["alerts"]
        self.default_channel.addItems(default_channel_options)

        self.channel_id = QLineEdit()
        self.bot_token = QLineEdit()
        self.bot_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.note = QLineEdit()

        layout = QFormLayout(self)
        layout.addRow("Label", self.label)
        layout.addRow("Channel ID", self.channel_id)
        layout.addRow("Bot Token", self.bot_token)
        layout.addRow("Note", self.note)
        layout.addRow("Default Channel", self.default_channel)
        layout.addRow("Serial", self.serial)

    # Path override
    def get_directory_path(self):
        if self.label.text().lower().strip() == "backup":
            return ["config", "discord_bk"]
        return ["config"]

    def on_load(self, data):
        self.label.setText(data.get("label", ""))
        self.channel_id.setText(str(data.get("channel_id", "")))
        self.bot_token.setText(data.get("bot_token", ""))
        self.note.setText(data.get("note", ""))
        self.default_channel.setCurrentText(data.get("channel", "alerts"))
        self.serial.setText(data.get("serial", ""))

    def deploy_fields(self):  # :contentReference[oaicite:0]{index=0}
        return {
            "channel_id": self.channel_id.text().strip(),
            "bot_token": self.bot_token.text().strip(),
            "serial": self.serial.text().strip()
        }

    def serialize(self):
        return {
            "label": self.label.text().strip(),
            "channel_id": self.channel_id.text().strip(),
            "bot_token": self.bot_token.text().strip(),
            "note": self.note.text().strip(),
            "channel": self.default_channel.currentText(),
            "serial": self.serial.text().strip(),
        }

    def is_validated(self):
        if not self.channel_id.text().strip():
            return False, "Channel ID is required."
        if not self.bot_token.text().strip():
            return False, "Bot Token is required."
        if not self.serial.text().strip():
            return False, "Serial is required."
        if self.default_channel.currentText().strip() == "":
            return False, "Default channel is required."
        return True, ""
