import os, base64
from .base_editor import BaseEditor

class SymmetricEncryption(BaseEditor):
    """Commander Edition – autogen symmetric AES key editor"""

    def __init__(self, parent=None, new_conn=False, default_channel_options=None):
        super().__init__(parent, new_conn)
        self.bundle = {
            "key": base64.b64encode(os.urandom(32)).decode(),
            "type": "aes",
        }

    def get_directory_path(self):
        return ["config", "security", "symmetric_encryption"]

    def get_deployment_path(self, universal_id):
        return ["certs", universal_id, "symmetric_encryption"]


    def on_load(self, data: dict):
        pass

    def is_autogen(self) -> bool:
        return True

    def deploy_fields(self):
        return self.bundle.copy()

    def serialize(self):
        return {}

    def is_validated(self):
        return True
