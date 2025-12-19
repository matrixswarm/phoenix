# Authored by Daniel F MacDonald and ChatGPT-5 (“The Generals”)
from PyQt6.QtWidgets import QComboBox, QFormLayout, QLineEdit
from .base_editor import BaseEditor

class Telegram(BaseEditor):

    def __init__(self, parent=None, new_conn=False, default_channel_options=None):
        super().__init__(parent, new_conn)


        self.default_channel = QComboBox()
        default_channel_options = default_channel_options or ["telegram", "outgoing.command"]
        self.default_channel.addItems(default_channel_options)

        self.label = QLineEdit(self.generate_default_label())
        self.chat_id = QLineEdit()
        self.bot_token = QLineEdit()
        self.bot_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.note = QLineEdit()

        layout = QFormLayout(self)
        layout.addRow("Label", self.label)
        layout.addRow("Chat ID", self.chat_id)
        layout.addRow("Bot Token", self.bot_token)
        layout.addRow("Note", self.note)
        layout.addRow("Default Channel", self.default_channel)
        layout.addRow("Serial", self.serial)


    def on_load(self, data):
        self.label.setText(data.get("label", ""))
        self.chat_id.setText(str(data.get("chat_id", "")))
        self.bot_token.setText(str(data.get("bot_token", "")))
        self.note.setText(data.get("note", ""))
        self.default_channel.setCurrentText(data.get("channel"))
        self.serial.setText(data.get("serial"))

    def deploy_fields(self):
        return {
            "chat_id": self.chat_id.text().strip(),
            "bot_token": self.bot_token.text().strip(),
            "channel": self.default_channel.currentText(),
        }

    def serialize(self):
        return {
            "label": self.label.text().strip(),
            "chat_id": self.chat_id.text().strip(),
            "bot_token": self.bot_token.text().strip(),
            "note": self.note.text().strip(),
            "channel": self.default_channel.currentText(),
            "serial": self.serial.text().strip(),
        }

    def is_validated(self):
        if not self.chat_id.text().strip():
            return False, "Chat ID is required."
        if not self.bot_token.text().strip():
            return False, "Bot Token is required."
        # Validate protocol
        if not self.serial.text().strip():
            return False, "Serial is required."
        if self.default_channel.currentText().strip() == "":
            return False, "Default channel is required."
        return True, ""
