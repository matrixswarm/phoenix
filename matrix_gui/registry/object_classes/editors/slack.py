# Authored by Daniel F MacDonald and ChatGPT-5 (“The Generals”)
from PyQt6.QtWidgets import QComboBox, QFormLayout, QLineEdit
from .base_editor import BaseEditor

class Slack(BaseEditor):

    def __init__(self, parent=None, new_conn=False, default_channel_options=None):
        super().__init__(parent, new_conn)


        self.default_channel = QComboBox()
        default_channel_options = default_channel_options or ["slack"]
        self.default_channel.addItems(default_channel_options)

        self.label = QLineEdit(self.generate_default_label())
        self.webhook_url = QLineEdit()
        self.note = QLineEdit()
        layout = QFormLayout(self)
        layout.addRow("Label", self.label)
        layout.addRow("Webhook URL", self.webhook_url)
        layout.addRow("Note", self.note)
        layout.addRow("Default Channel", self.default_channel)
        layout.addRow("Serial", self.serial)

    def on_load(self, data):
        self.label.setText(data.get("label", ""))
        self.webhook_url.setText(data.get("webhook_url", ""))
        self.note.setText(data.get("note", ""))
        self.default_channel.setCurrentText(data.get("channel"))
        self.serial.setText(data.get("serial"))

    def deploy_fields(self):
        return {
            "webhook_url": self.webhook_url.text().strip(),
            "channel": self.default_channel.currentText(),
        }

    def get_directory_path(self):
        if self.label.text().lower().strip() == "slack_bk":
            return ["config", "slack_bk"]
        return ["config"]

    def serialize(self):
        return {
            "label": self.label.text().strip(),
            "webhook_url": self.webhook_url.text().strip(),
            "note": self.note.text().strip(),
            "channel": self.default_channel.currentText(),
            "serial": self.serial.text().strip(),
        }

    def is_validated(self):
        if not self.webhook_url.text().strip():
            return False, "Webhook URL required."

        if not self.webhook_url.text().startswith("http"):
            return False, "Webhook URL must begin with http/https."
        if not self.serial.text().strip():
            return False, "Serial is required."
        if self.default_channel.currentText().strip() == "":
            return False, "Default channel is required."
        return True, ""
