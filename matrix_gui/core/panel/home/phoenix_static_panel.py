import json, time
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QGroupBox
from matrix_gui.core.class_lib.feed.feed_formatter import FeedFormatter
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QMenu
from PyQt6.QtCore import Qt
from matrix_gui.core.emit_gui_exception_log import emit_gui_exception_log
from matrix_gui.core.event_bus import EventBus
class PhoenixStaticPanel(QWidget):
    """
    Home HUD after vault unlock:
      - Vault info (path + status)
      - Deployment summary
      - Swarm feed (ops console)
      - Quick ping box
    """
    def __init__(self, vault_data=None, vault_path=None, parent=None):
        super().__init__(parent)
        self.vault_data = vault_data or {}
        self.vault_path = vault_path

        layout = QVBoxLayout(self)

        self.deployment_tree = QTreeWidget()

        self.deployment_tree.setHeaderHidden(True)

        self.deployment_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        self.deployment_tree.customContextMenuRequested.connect(self._on_deployment_context_menu)
        layout.addWidget(self.deployment_tree)


        self._refresh_deployment_summary()

        # === Swarm Feed ===
        self.feed = QTextEdit()
        self.feed.setReadOnly(True)
        layout.addWidget(self.feed)


        # === Deployments summary ===
        deploy_box = QGroupBox("Deployments")
        deploy_layout = QVBoxLayout()
        deploy_layout.addWidget(self.deployment_tree)
        deploy_box.setLayout(deploy_layout)
        layout.addWidget(deploy_box)

        # === Swarm Feed ===
        feed_box = QGroupBox("🛰️ Swarm Feed")
        feed_layout = QVBoxLayout()
        feed_layout.addWidget(self.feed)
        feed_box.setLayout(feed_layout)
        layout.addWidget(feed_box)

        # === Wire EventBus ===
        #EventBus.on("connection.status", self._on_connection_status)
        #EventBus.on("inbound.verified", self._on_inbound_message)

    def _refresh_deployment_summary(self):

        try:
            self.deployment_tree.clear()
            deployments = (self.vault_data or {}).get("deployments", {})
            for dep_id, meta in deployments.items():
                if not isinstance(meta, dict):
                    continue
                label = meta.get("label", dep_id)
                dep_item = QTreeWidgetItem([f"📦 {label}"])
                dep_item.setData(0, Qt.ItemDataRole.UserRole, {"dep_id": dep_id, "meta": meta})
                self.deployment_tree.addTopLevelItem(dep_item)

                for agent in meta.get("agents", []):
                    uid = agent.get("universal_id")
                    conn = agent.get("connection", {})
                    proto = conn.get("proto", "?")
                    host = conn.get("host", "?")
                    port = conn.get("port", "?")
                    child = QTreeWidgetItem([f"{uid} ({proto}) {host}:{port}"])
                    dep_item.addChild(child)
        except Exception as e:
            emit_gui_exception_log("PhoenixStaticPanel._on_connection_status", e)

    def _on_connection_status(self, session_id, channel, status, info, **_):
        try:
            line = f"[{channel}] {status} :: sess={session_id} :: {info}"
            self.feed.append(line)
        except Exception as e:
            emit_gui_exception_log("PhoenixStaticPanel._on_connection_status", e)

    def append_feed_event(self, event: dict):
        """Append a formatted event to the Swarm Feed console."""
        try:
            msg = FeedFormatter.format(event)
            self.feed.append(msg)
        except Exception as e:
            self.feed.append(f"[FEED][ERROR] Could not format event: {e}")

    def _on_inbound_message(self, session_id: str, channel: str, source: str, payload: dict, ts: float, **_):
        try:
            t = time.strftime("%H:%M:%S", time.localtime(ts))
            snippet = json.dumps(payload.get("content", payload), separators=(",", ":"), sort_keys=True)[:160]
            line = f"[{t}] ({channel}) {source} » sess={session_id} :: {snippet}"
            self.feed.append(line)
        except Exception as e:
            emit_gui_exception_log("PhoenixStaticPanel._on_inbound_message", e)

    def _on_deployment_context_menu(self, pos):

        try:
            item = self.deployment_tree.itemAt(pos)
            if not item:
                return

            data = item.data(0, Qt.ItemDataRole.UserRole)
            if not data:
                return  # only top-level deployment nodes

            menu = QMenu(self)
            act_connect = menu.addAction("🔌 Connect")
            act_connect.triggered.connect(lambda: self._connect_deployment(data))
            menu.exec(self.deployment_tree.viewport().mapToGlobal(pos))

        except Exception as e:
            emit_gui_exception_log("PhoenixStaticPanel._on_deployment_context_menu", e)

    def _connect_deployment(self, data):
        try:
            dep_id = data["dep_id"]
            meta = data["meta"]
            print(f"[COCKPIT] Connecting to deployment {dep_id}…")

            EventBus.emit("session.open.requested", dep_id, meta, self.vault_data)
        except Exception as e:
            emit_gui_exception_log("PhoenixStaticPanel._connect_deployment", e)