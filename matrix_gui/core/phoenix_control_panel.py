import uuid
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QMessageBox, QMenu
from PyQt6 import QtCore

from PyQt6.QtWidgets import QComboBox
from matrix_gui.core.event_bus import EventBus
from matrix_gui.modules.directive.directive_manager_dialog import DirectiveManagerDialog
from matrix_gui.modules.net.connection_manager_dialog import ConnectionManagerDialog
from matrix_gui.core.emit_gui_exception_log import emit_gui_exception_log
from PyQt6.QtWidgets import QFileDialog


class PhoenixControlPanel(QWidget):
    """
    Thin top-bar widget that lets the user unlock a vault, pick a
    deployment profile, and spin up a live Phoenix *SessionWindow*.

    Signals
    -------
    vault_updated(dict)
        Emitted after the connection-manager dialog mutates ``self.vault_data``.
    request_vault_save(dict)
        Ask the cockpit to persist the in-memory vault copy to disk.
    request_vault_load()
        Ask the cockpit to (re)load a vault from disk.
    """
    vault_updated = QtCore.pyqtSignal(dict)
    request_vault_save = QtCore.pyqtSignal(dict)
    request_vault_load = QtCore.pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(8)

        # === Primary Controls ===
        self.layout.addWidget(QLabel("Deployment:"))
        self.deployment_selector = QComboBox()
        self.layout.addWidget(self.deployment_selector)

        self.connect_btn = QPushButton("🔌 Connect")
        self.connect_btn.setObjectName("connect")
        self.connect_btn.clicked.connect(self.launch_deployment_dialog)
        self.layout.addWidget(self.connect_btn)

        self.conn_btn = QPushButton("🌐 Connections")
        self.conn_btn.setObjectName("connMgr")
        self.conn_btn.clicked.connect(self.launch_connection_manager)
        self.layout.addWidget(self.conn_btn)

        self.directives_btn = QPushButton("📄 Directives")
        self.directives_btn.setObjectName("document")
        self.directives_btn.clicked.connect(self.open_directive_manager)
        self.layout.addWidget(self.directives_btn)

        self.vault_btn = QPushButton("🔐 Vault")
        self.vault_btn.setObjectName("vault")
        self.vault_btn.clicked.connect(self.reopen_vault)
        self.layout.addWidget(self.vault_btn)

        # Stretch at end to push controls left
        self.layout.addStretch()

        # Wire events
        EventBus.on("vault.unlocked", self.on_vault_unlocked)
        EventBus.on("vault.update", self.on_vault_update)

    def refresh_deployments(self):
        """Populate the *Deployment* combobox from ``self.vault_data``.

        • Clears the list, then iterates over ``vault_data["deployments"]``
        • Skips malformed entries (non-dicts)
        • Any exception is logged via :func:`emit_gui_exception_log`.
        """
        try:
            self.deployment_selector.clear()
            deployments = (self.vault_data or {}).get("deployments", {})
            for dep_id, meta in deployments.items():
                if not isinstance(meta, dict):
                    continue  # skip bad entry
                label = meta.get("label", dep_id)
                self.deployment_selector.addItem(label, dep_id)
        except Exception as e:
            emit_gui_exception_log("PhoenixControlPanel.launch", e)

    def on_vault_update(self, **kwargs):
        """Handle a ``vault.update`` bus event.

        Parameters
        ----------
        **kwargs
            ``data`` – the fresh vault dict shoved in by the emitter.
        """
        try:
            self.vault_data = kwargs.get("data", self.vault_data)
            self.refresh_deployments()
        except Exception as e:
            emit_gui_exception_log("PhoenixControlPanel.on_vault_update", e)

    def launch_deployment_dialog(self):
        """Open a live session for the currently selected deployment.

        Validates that a vault is unlocked and the selected deployment exists,
        then emits the **session.open.requested** bus event with a brand-new
        UUID-4 ``session_id`` and the deployment metadata payload.
        """
        dep_id = self.deployment_selector.currentData()
        if not dep_id:
            QMessageBox.warning(self, "No Deployment", "Please select a deployment first.")
            return

        if not self.vault_data or "deployments" not in self.vault_data:
            QMessageBox.warning(self, "No Vault", "Vault data not loaded or invalid.")
            return

        deployment = self.vault_data["deployments"].get(dep_id)
        if not deployment:
            QMessageBox.warning(self, "Invalid Deployment", f"Deployment {dep_id} not found in vault.")
            return

        # Tag deployment with its vault id
        deployment["id"] = dep_id

        # Generate a unique session ID
        session_id = str(uuid.uuid4())

        # Emit session.open.requested with proper signature
        EventBus.emit(
            "session.open.requested",
            session_id=session_id,
            deployment=deployment,
            vault_data=self.vault_data
        )

    def launch_connection_manager(self):
        """Open the *ConnectionManagerDialog* for editing saved SSH profiles."""
        dlg = ConnectionManagerDialog(self.vault_data, self)
        dlg.exec()
        #self.refresh_deployments()
        self.vault_updated.emit(self.vault_data)


    def save_vault(self):
        """Persist the current in-memory vault to a user-chosen ``*.json`` file."""
        path, _ = QFileDialog.getSaveFileName(self, "Save Vault", filter="Vault JSON (*.json)")
        if path:
            import json
            with open(path, "w") as f:
                json.dump(self.vault_data, f, indent=2)
                QMessageBox.information(self, "Saved", f"Vault saved to {path}")

    def reopen_vault(self):
        """Close the active vault and trigger the cockpit’s re-unlock workflow."""
        reply = QMessageBox.question(
            self, "Close current vault?",
            "Are you sure you want to close this vault?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        EventBus.emit("vault.closed")
        EventBus.emit("vault.reopen.requested")

    # =========================================================
    # Vault lifecycle
    # =========================================================
    def on_vault_unlocked(self, **kwargs):
        """Receive the ``vault.unlocked`` signal and cache path / password."""
        self.vault_unlocked = True
        self.vault_data = kwargs.get("vault_data")
        self.password = kwargs.get("password")
        self.vault_path = kwargs.get("vault_path")


        #self.vault_data or {}
        self.refresh_deployments()
        # now that we have vault_data, start sessions + dispatcher
        #self.sessions = SessionManager(EventBus)
        #self.dispatcher = OutboundDispatcher(EventBus, self.sessions, vault=self.vault_data)
        #self.dispatcher.start()

    def open_directive_manager(self):
        dlg = DirectiveManagerDialog(
            vault_data=self.vault_data,
            password=self.password,
            vault_path=self.vault_path,
            parent=self
        )
        dlg.exec()

    def emit_save(self):
        self.request_vault_save.emit(self.vault_data)

    def emit_reload(self):
        self.request_vault_load.emit()
