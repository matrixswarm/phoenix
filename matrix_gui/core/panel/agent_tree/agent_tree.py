# Authored by Daniel F MacDonald and ChatGPT 5 aka The Generals
import uuid, time, hashlib, json, datetime
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy, QHeaderView, QTreeWidget, QTreeWidgetItem, QLabel
from matrix_gui.core.emit_gui_exception_log import emit_gui_exception_log
from matrix_gui.core.class_lib.packet_delivery.packet.standard.command.packet import Packet
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QMenu
from collections import deque
from threading import RLock


class PhoenixAgentTree(QWidget):
    def __init__(self, session_id, vault_data=None, bus=None, conn=None, deployment=None, parent=None):
        super().__init__(parent)
        try:
            self.vault_data = vault_data or {}
            self.bus = bus
            self.conn=conn
            self.deployment=deployment
            self.session_id = session_id
            self.parent = parent  # optional
            self.active_log_token = None  # can be used locally or emitted via signal
            self._update_queue = deque(maxlen=10)
            self._update_timer = QTimer(self)
            self._update_timer.timeout.connect(self._process_queue)
            self._update_timer.start(200)  # check every 200ms
            self._render_lock = RLock()
            self._updating = False

            # === Layout
            layout = QVBoxLayout()
            layout.setContentsMargins(6, 4, 0, 4)

            layout.setSpacing(4)
            self.setLayout(layout)

            self.status_label = QLabel("⏳ Loading…")
            self.status_label.setObjectName("status")  # use same QSS rule as log status
            layout.addWidget(self.status_label)

            self._last_payload_hash = None
            self._last_tree_update_ts = None

            self.flip_tripping_threshold = 1

            # === Agent tree widget
            self.tree = QTreeWidget()
            self.tree.setColumnCount(1)
            self.tree.setHeaderHidden(True)
            self.tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            self.tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
            self.tree.itemClicked.connect(self._on_tree_item_clicked)

            #context menu, right click, popup
            self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.tree.customContextMenuRequested.connect(self._on_context_menu)
            self.tree.setContentsMargins(0, 0, 0, 0)

            layout.addWidget(self.tree)

            self._rendered_tree_root={} #holds udated agent tree

            # === Agent detail panel

            layout.setStretch(0, 0)  # status label
            layout.setStretch(1, 3)  # tree

            self.tree.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

            self.tree.setMinimumHeight(180)


            # === Bind to session bus updates
            if self.bus:
                self.bus.on(
                    f"inbound.verified.agent_tree_master.update",
                    self._handle_tree_update
                )
                print(f"[AGENT_TREE] Subscribed to bus: inbound.verified.agent_tree_master.update")

        except Exception as e:
            emit_gui_exception_log("PhoenixAgentTree.__init__", e)

    def get_rendered_tree(self):
        return self._rendered_tree_root

    def _on_tree_item_clicked(self, item):

        if self._updating:
            print("[TREE] ⚠️ Click ignored during update window.")
            return

        try:

            with self._render_lock:

                node = item.data(0, Qt.ItemDataRole.UserRole)
                if not isinstance(node, dict):
                    return

                uid = node.get("universal_id")
                if not uid or not self.bus:
                    return

                token = str(uuid.uuid4())
                self.active_log_token = token
                #self.detail_panel.set_agent_data(node)

                pk = Packet()
                pk.set_data({
                    "handler": "cmd_service_request",
                    "ts": time.time(),
                    "content": {
                        "service": "hive.log_streamer",
                        "payload": {
                            "target_agent": uid,
                            "session_id": self.session_id,
                            "token": token,
                            "follow": True,
                            "return_handler": "agent_log_view.update"
                        }
                    }
                })

                ui_cfg = node.get("config", {}).get("ui", {})
                panels = ui_cfg.get("panel", [])

                self.bus.emit("gui.agent.selected", session_id=self.session_id, node=node, panels=panels)
                self.bus.emit("gui.log.token.updated", session_id=self.session_id, token=token, agent_title=node.get("name", uid))
                self.bus.emit("outbound.message", session_id=self.session_id, channel="outgoing.command", packet=pk)

                print(f"[AGENT_TREE] 🔍 Sent fetch_logs for agent {uid} with token={token}")

        except Exception as e:
            emit_gui_exception_log("PhoenixAgentTree._on_tree_item_clicked", e)

    def _process_queue(self):
        if not self._update_queue:
            return
        payload = self._update_queue.pop()  # take latest, discard older
        try:
            self._render_tree(payload.get("content", {}))
            self._update_status_label()
            QTimer.singleShot(0, self.tree.expandAll)
        except Exception as e:
            emit_gui_exception_log("PhoenixAgentTree._process_queue", e)

    def _handle_tree_update(self, payload, **_):

        try:
            self._update_queue.append(payload)
            content = payload.get("content", {})
            new_hash = self._compute_payload_hash(content)

            if new_hash == self._last_payload_hash:
                self._last_tree_update_ts = time.time()
                self._update_status_label()
                return

            if isinstance(content, dict):
                self._rendered_tree_root = content

            self._last_payload_hash = new_hash
            self._last_tree_update_ts = time.time()
            self._render_tree(content)
            self._update_status_label()

            QTimer.singleShot(0, self.tree.expandAll)

        except Exception as e:
            emit_gui_exception_log("PhoenixAgentTree._handle_tree_update", e)

    def _update_status_label(self):
        try:
            ts = self._last_tree_update_ts or time.time()
            time_str = datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S")
            self.status_label.setText(f"Updated at {time_str}")
        except Exception as e:
            emit_gui_exception_log("PhoenixAgentTree._update_status_label", e)

    def _render_tree(self, tree_data):

        if self._updating:
            return  # skip if already mid-update
        try:
            self._updating = True
            # remember which node is currently selected
            selected = None
            current = self.tree.currentItem()
            if current and hasattr(current, "node_data"):
                selected = current.node_data.get("universal_id")

            with self._render_lock:
                self.tree.blockSignals(True)
                self.tree.setUpdatesEnabled(False)
                self.tree.clear()


            def build(parent, node):
                if not isinstance(node, dict):
                    return

                # Extract base name and children
                base = node.get("universal_id") or "Unnamed"
                children = node.get("children", [])
                child_count = len(children)

                # Flip-trip check
                flip_count = (
                    node.get("agent_status", {})
                    .get("spawn", {})
                    .get("count", 0)
                )

                flip_marker = ""
                if flip_count > self.flip_tripping_threshold:  # threshold, tweak as you like
                    flip_marker = f"    ⚠"

                # Icon + Title
                ui_cfg = node.get("config", {}).get("ui", {})
                tree_ui = ui_cfg.get("agent_tree", {})

                emoji = tree_ui.get("emoji")
                icon_path = tree_ui.get("icon")

                # Decide prefix
                if emoji:
                    prefix = emoji
                elif icon_path:
                    # for now just show the icon path text, or use QIcon if you wire it in
                    prefix = "🖼"
                else:
                    prefix = "🧬" if children else "🔹"

                # Build title
                if children:
                    title = f"{prefix} {base} ({child_count}){flip_marker}"
                else:
                    title = f"{prefix} {base}{flip_marker}"

                # Create the tree item
                item = QTreeWidgetItem([title])
                item.setData(0, Qt.ItemDataRole.UserRole, node)

                # Tooltip if marked
                if flip_count > self.flip_tripping_threshold:
                    item.setToolTip(0, f"This agent flip-tripped {flip_count} times.")

                # Bold font if it has children
                font = item.font(0)
                if children:
                    font.setBold(True)
                item.setFont(0, font)

                # Attach to parent or root
                if parent:
                    parent.addChild(item)
                else:
                    self.tree.addTopLevelItem(item)

                # Recurse
                for child in children:
                    build(item, child)


            build(None, tree_data)
            if selected:
                self._reselect_by_uid(selected)

        except Exception as e:
            emit_gui_exception_log("PhoenixAgentTree._render_tree", e)

        finally:
            self.tree.setUpdatesEnabled(True)
            self.tree.blockSignals(False)
            self._updating = False

    def _reselect_by_uid(self, uid):
        self.tree.setFocus(Qt.FocusReason.OtherFocusReason)
        def recurse(parent):
            for i in range(parent.childCount()):
                item = parent.child(i)
                if getattr(item, "node_data", {}).get("universal_id") == uid:
                    self.tree.setCurrentItem(item)
                    self.tree.scrollToItem(item)
                    return True
                if recurse(item):
                    return True
            return False

        # search from top level
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            if getattr(top, "node_data", {}).get("universal_id") == uid:
                self.tree.setCurrentItem(top)
                self.tree.scrollToItem(top)
                return
            if recurse(top):
                return

    def closeEvent(self, event):
        try:
            if self.bus:
                self.bus.off(
                    f"inbound.verified.agent_tree_master.update",
                    self._handle_tree_update
                )
                print(f"[AGENT_TREE] Unsubscribed from agent_tree_master.update")
            super().closeEvent(event)
        except Exception as e:
            emit_gui_exception_log("PhoenixAgentTree.closeEvent", e)
    def _build_node(self, parent_item, node):
        try:
            name, health = self._format_display(node)
            item = QTreeWidgetItem([name, health])
            item.setData(0, Qt.ItemDataRole.UserRole, node)
            parent_item.addChild(item)

            for child in node.get("children", []):
                self._build_node(item, child)

        except Exception as e:
            emit_gui_exception_log("PhoenixAgentTree._build_node", e)

    def _format_display(self, node: dict):
        try:
            name = node.get("name", "unnamed")
            spawn = node.get("agent_status", {}).get("spawn", {})
            cnt = spawn.get("count", 0)
            symbol = f"⚡{cnt}" if cnt else ""
            return name, symbol
        except Exception as e:
            emit_gui_exception_log("PhoenixAgentTree._format_display", e)

    def _compute_payload_hash(self, payload: dict):
        try:
            def prune(d):
                if isinstance(d, dict):
                    return {k: prune(v) for k, v in d.items() if k != "agent_status"}
                elif isinstance(d, list):
                    return [prune(i) for i in d]
                return d

            cleaned = prune(payload)
            serialized = json.dumps(cleaned, sort_keys=True)
            return hashlib.md5(serialized.encode()).hexdigest()
        except Exception as e:
            emit_gui_exception_log("PhoenixAgentTree._compute_payload_hash", e)
            return None

    def _on_context_menu(self, pos):

        try:
            item = self.tree.itemAt(pos)
            if not item:
                return
            node = item.data(0, Qt.ItemDataRole.UserRole)
            if not isinstance(node, dict):
                return

            uid = node.get("universal_id")
            if not uid or uid == "matrix":  # don’t allow nuking Matrix itself
                return

            menu = QMenu(self)
            act_delete = menu.addAction(f"☠ Delete {uid}")
            act_delete.triggered.connect(lambda: self.parent._launch_delete_agent(uid))

            act_restart = menu.addAction(f"🔁 Restart {uid}")
            act_restart.triggered.connect(lambda: self.parent._launch_restart_agent(uid))

            act_hotswap = menu.addAction(f"🔥 Hotswap {uid}")
            act_hotswap.triggered.connect(lambda: self.parent._launch_hotswap_agent_modal(uid))

            act_inject = menu.addAction(f"🧬 Inject under {uid}")
            act_inject.triggered.connect(lambda: self.parent._launch_inject_agent_modal(uid))

            menu.exec(self.tree.viewport().mapToGlobal(pos))
        except Exception as e:
            emit_gui_exception_log("PhoenixAgentTree._on_context_menu", e)


