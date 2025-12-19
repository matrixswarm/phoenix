# Authored by Daniel F MacDonald and ChatGPT-5 aka The Generals
# TREND SCOUT TOPIC FORGE PANEL — DB-backed Ideas → Curate → Fire (via Matrix service routing)

import time
import json
import uuid

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QGroupBox, QLineEdit, QTabWidget, QMessageBox,
    QComboBox, QListWidget, QListWidgetItem, QSplitter
)
from PyQt6.QtCore import Qt

from matrix_gui.core.panel.custom_panels.interfaces.base_panel_interface import PhoenixPanelInterface
from matrix_gui.core.class_lib.packet_delivery.packet.standard.command.packet import Packet
from matrix_gui.core.panel.control_bar import PanelButton
from matrix_gui.core.emit_gui_exception_log import emit_gui_exception_log


class TrendScout(PhoenixPanelInterface):
    """
    Commander Edition — TrendScout Topic Forge Panel

    Goals:
      • ALWAYS proxy through Matrix using cmd_service_request (service-manager resolution).
      • ALWAYS DB-backed (no JSON files).
      • Get 10 idea topics → user curates → Fire sends curated list to Sora.
      • Modify: select topic → give instruction → generate new 10 (replaces list).
      • Mode switch: manual/auto for TrendScout’s scheduled behavior.
      • Timer controls: show next scheduled execution + reset timer.

    Backend contract (single service string):
      service: "trend_scout.topic_forge"
      payload.action:
        - "generate_ideas"      {count}
        - "modify_ideas"        {base_topic, instruction, count}
        - "curate_add"          {idea_id}
        - "curate_add_all"      {batch_id}
        - "curate_remove"       {curated_id}
        - "curate_list"         {}
        - "fire"                {}
        - "mode_set"            {mode: "manual"|"auto"}
        - "mode_get"            {}
        - "timer_get"           {}
        - "timer_reset"         {}
    """

    cache_panel = True

    # === Matrix-resolved service name (must exist in TrendScout service-manager) ===
    SERVICE = "trend_scout.topic_forge"

    # === TrendScout will crypto_reply to this handler name ===
    ACK_HANDLER = "trend_scout_panel.topic_forge_ack"

    # === Bus topic for inbound verified callbacks ===
    BUS_ACK_TOPIC = "inbound.verified.trend_scout_panel.topic_forge_ack"

    def __init__(self, session_id, bus=None, node=None, session_window=None):
        super().__init__(session_id, bus, node=node, session_window=session_window)

        self._signals_connected = False

        # panel state
        self.current_batch_id = None
        self.last_ideas = []     # list[dict]
        self.last_curated = []   # list[dict]
        self._pending_tokens = set()

        layout = self._build_layout()
        self.setLayout(layout)

        self._connect_signals()

        # initial UI sync
        self._request_status_refresh()

        print("[TREND_FORGE] Topic Forge panel online.")

    # ---------------------------------------------------------
    # UI LAYOUT
    # ---------------------------------------------------------
    def _build_layout(self):
        root = QVBoxLayout()

        root.addWidget(QLabel("<b>TrendScout — Topic Forge</b>"))

        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        # =====================================================
        # TAB 1: TOPIC FORGE
        # =====================================================
        forge_tab = QWidget()
        forge_layout = QVBoxLayout(forge_tab)

        # ---- Controls row (mode + timers + get ideas)
        controls_box = QGroupBox("Controls")
        controls = QVBoxLayout(controls_box)

        # Mode row
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode:"))

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["manual", "auto"])
        self.btn_apply_mode = QPushButton("Apply Mode")
        self.btn_apply_mode.clicked.connect(self._on_apply_mode)

        self.lbl_mode_status = QLabel("current: ?")
        self.lbl_mode_status.setStyleSheet("color:#bbb;")

        mode_row.addWidget(self.mode_combo, stretch=0)
        mode_row.addWidget(self.btn_apply_mode, stretch=0)
        mode_row.addWidget(self.lbl_mode_status, stretch=1)

        controls.addLayout(mode_row)

        # Timer row
        timer_row = QHBoxLayout()
        self.lbl_next_run = QLabel("next idea run: ?")
        self.lbl_next_run.setStyleSheet("color:#bbb;")
        self.btn_timer_refresh = QPushButton("Refresh Timer")
        self.btn_timer_reset = QPushButton("Reset Timer")
        self.btn_timer_refresh.clicked.connect(self._on_timer_refresh)
        self.btn_timer_reset.clicked.connect(self._on_timer_reset)

        timer_row.addWidget(self.lbl_next_run, stretch=1)
        timer_row.addWidget(self.btn_timer_refresh)
        timer_row.addWidget(self.btn_timer_reset)

        controls.addLayout(timer_row)

        # Get ideas row
        ideas_row = QHBoxLayout()
        ideas_row.addWidget(QLabel("Ideas count:"))
        self.count_input = QLineEdit("10")
        self.count_input.setFixedWidth(60)

        self.btn_get_ideas = QPushButton("Get Ideas")
        self.btn_get_ideas.clicked.connect(self._on_get_ideas)

        self.btn_refresh_curated = QPushButton("Refresh Curated")
        self.btn_refresh_curated.clicked.connect(self._on_refresh_curated)

        ideas_row.addWidget(self.count_input)
        ideas_row.addWidget(self.btn_get_ideas)
        ideas_row.addWidget(self.btn_refresh_curated)
        ideas_row.addStretch(1)

        controls.addLayout(ideas_row)

        forge_layout.addWidget(controls_box)

        # ---- Main split: Ideas list + Curated list
        split = QSplitter()
        split.setOrientation(Qt.Orientation.Horizontal)

        # Left pane: Ideas
        ideas_pane = QWidget()
        ideas_lay = QVBoxLayout(ideas_pane)

        ideas_header = QHBoxLayout()
        ideas_header.addWidget(QLabel("<b>Idea Batch (10)</b>"))
        self.btn_add_selected = QPushButton("Add")
        self.btn_add_selected.clicked.connect(self._on_add_selected)
        self.btn_add_all = QPushButton("Add All")
        self.btn_add_all.clicked.connect(self._on_add_all)

        ideas_header.addStretch(1)
        ideas_header.addWidget(self.btn_add_selected)
        ideas_header.addWidget(self.btn_add_all)
        ideas_lay.addLayout(ideas_header)

        self.idea_list = QListWidget()
        self.idea_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.idea_list.itemSelectionChanged.connect(self._on_idea_selected)
        ideas_lay.addWidget(self.idea_list)

        # Modify section
        mod_box = QGroupBox("Modify Selected Idea (replaces the 10)")
        mod_lay = QVBoxLayout(mod_box)

        self.selected_topic_box = QLineEdit()
        self.selected_topic_box.setReadOnly(True)
        self.selected_topic_box.setPlaceholderText("Select an idea above…")

        self.modify_input = QTextEdit()
        self.modify_input.setPlaceholderText("Type how you want to modify this topic…")

        mod_btn_row = QHBoxLayout()
        self.btn_generate_replacement = QPushButton("Generate Replacement Batch")
        self.btn_generate_replacement.clicked.connect(self._on_generate_replacement)
        mod_btn_row.addStretch(1)
        mod_btn_row.addWidget(self.btn_generate_replacement)

        mod_lay.addWidget(QLabel("Selected topic:"))
        mod_lay.addWidget(self.selected_topic_box)
        mod_lay.addWidget(QLabel("Modification instruction:"))
        mod_lay.addWidget(self.modify_input)
        mod_lay.addLayout(mod_btn_row)

        ideas_lay.addWidget(mod_box)

        # Right pane: Curated
        curated_pane = QWidget()
        curated_lay = QVBoxLayout(curated_pane)

        curated_header = QHBoxLayout()
        curated_header.addWidget(QLabel("<b>Curated Sora List</b>"))

        # New Button: Add Prompt
        self.btn_add_prompt = QPushButton("➕ Add Prompt")
        self.btn_add_prompt.clicked.connect(self._on_add_prompt)
        curated_header.addWidget(self.btn_add_prompt)

        # Existing Remove Button
        self.btn_remove_curated = QPushButton("Remove")
        self.btn_remove_curated.clicked.connect(self._on_remove_curated)
        curated_header.addWidget(self.btn_remove_curated)

        curated_lay.addLayout(curated_header)

        self.curated_list = QListWidget()
        self.curated_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        curated_lay.addWidget(self.curated_list)

        fire_row = QHBoxLayout()

        # Label + textbox for duration
        fire_row.addWidget(QLabel("Video duration (sec):"))
        self.duration_input = QLineEdit("30")
        self.duration_input.setFixedWidth(60)
        fire_row.addWidget(self.duration_input)

        # Fire button
        self.btn_fire = QPushButton("🔥 Fire!")
        self.btn_fire.setStyleSheet("font-weight:bold;")
        self.btn_fire.clicked.connect(self._on_fire)
        fire_row.addStretch(1)
        fire_row.addWidget(self.btn_fire)
        curated_lay.addLayout(fire_row)
        split.addWidget(ideas_pane)
        split.addWidget(curated_pane)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 1)

        forge_layout.addWidget(split)

        # Activity log
        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        forge_layout.addWidget(QLabel("Activity Log:"))
        forge_layout.addWidget(self.output_box)

        self.tabs.addTab(forge_tab, "Topic Forge")

        # =====================================================
        # TAB 2: DEBUG
        # =====================================================
        debug_tab = QWidget()
        debug_lay = QVBoxLayout(debug_tab)

        self.preview_box = QTextEdit()
        self.preview_box.setReadOnly(True)
        debug_lay.addWidget(QLabel("Last Payload / Debug Info"))
        debug_lay.addWidget(self.preview_box)

        self.tabs.addTab(debug_tab, "Debug")

        return root

    def _on_add_prompt(self):
        from PyQt6.QtWidgets import QInputDialog

        text, ok = QInputDialog.getText(self, "Add Custom Prompt", "Enter your custom topic:")
        if ok and text.strip():
            topic = text.strip()

            # Optionally you can parse tags from brackets if you want, or leave empty
            idea = {
                "topic": topic,
                "tags": [],
                "description": ""  # Optional: extend input dialog if you want desc
            }

            item = QListWidgetItem(topic)
            item.setData(Qt.ItemDataRole.UserRole, idea)
            self.curated_list.addItem(item)

            self.output_box.append(f"🆕 Manually added prompt: '{topic}' to curated list.")

    # ---------------------------------------------------------
    # Packet sender (ALWAYS via Matrix cmd_service_request)
    # ---------------------------------------------------------
    def _send_service(self, action: str, extra: dict | None = None):
        """
        Always route via Matrix cmd_service_request so Matrix resolves
        'service' using TrendScout service-manager roles (like your macro pattern). :contentReference[oaicite:2]{index=2}
        """
        extra = extra or {}

        token = f"trendforge_{uuid.uuid4().hex[:10]}"
        self._pending_tokens.add(token)

        payload = {
            "action": action,
            "session_id": self.session_id,
            "return_handler": self.ACK_HANDLER,
            "token": token,
        }
        payload.update(extra)

        pk = Packet()
        pk.set_data({
            "handler": "cmd_service_request",
            "ts": time.time(),
            "content": {
                "service": self.SERVICE,
                "payload": payload
            }
        })

        # mirror to debug tab
        try:
            self.preview_box.setPlainText(json.dumps(pk.get_packet(), indent=2))
        except Exception:
            pass

        self.bus.emit(
            "outbound.message",
            session_id=self.session_id,
            channel="outgoing.command",
            packet=pk,
        )

        self.output_box.append(f"→ Sent action='{action}' via Matrix service='{self.SERVICE}' token={token}")

    # ---------------------------------------------------------
    # UI actions
    # ---------------------------------------------------------
    def _on_apply_mode(self):
        mode = (self.mode_combo.currentText() or "manual").strip().lower()
        if mode not in ("manual", "auto"):
            QMessageBox.warning(self, "Invalid Mode", "Mode must be manual or auto.")
            return
        self._send_service("mode_set", {"mode": mode})

    def _on_timer_refresh(self):
        self._send_service("timer_get")

    def _on_timer_reset(self):
        self._send_service("timer_reset")

    def _on_get_ideas(self):
        try:
            count = int(self.count_input.text().strip() or "10")
        except ValueError:
            QMessageBox.warning(self, "Invalid Count", "Count must be numeric.")
            return
        if count <= 0 or count > 50:
            QMessageBox.warning(self, "Invalid Count", "Use a count between 1 and 50.")
            return

        self.idea_list.clear()
        self.current_batch_id = None
        self.selected_topic_box.clear()
        self.modify_input.clear()

        self._send_service("generate_ideas", {"count": count})

    def _on_refresh_curated(self):
        self._send_service("curate_list")

    def _on_add_selected(self):
        item = self.idea_list.currentItem()
        if not item:
            QMessageBox.information(self, "No Selection", "Select an idea first.")
            return

        idea = item.data(Qt.ItemDataRole.UserRole)
        if not idea:
            return

        # Add to curated_list UI only
        new_item = QListWidgetItem(item.text())
        new_item.setData(Qt.ItemDataRole.UserRole, idea)
        self.curated_list.addItem(new_item)
        self.output_box.append(f"➕ Added '{idea.get('topic')}' to local curated list.")

    def _on_add_all(self):
        if not self.last_ideas:
            QMessageBox.information(self, "No Batch", "No ideas to add.")
            return
        for idea in self.last_ideas:
            it = QListWidgetItem(f"{idea.get('topic')}   [{', '.join(idea.get('tags', [])[:6])}]")
            it.setData(Qt.ItemDataRole.UserRole, idea)
            self.curated_list.addItem(it)
        self.output_box.append(f"➕ Added all {len(self.last_ideas)} ideas to local curated list.")

    def _on_remove_curated(self):
        row = self.curated_list.currentRow()
        if row >= 0:
            item = self.curated_list.takeItem(row)
            topic = (item.data(Qt.ItemDataRole.UserRole) or {}).get("topic", "?")
            self.output_box.append(f"❌ Removed '{topic}' from local curated list.")

    def _on_fire(self):
        # Collect curated ideas from the UI list
        curated_items = []
        for i in range(self.curated_list.count()):
            item = self.curated_list.item(i)
            idea = item.data(Qt.ItemDataRole.UserRole)
            if idea:
                curated_items.append({
                    "topic": idea.get("topic", ""),
                    "tags": idea.get("tags", []),
                    "description": idea.get("description", "")
                })

        if not curated_items:
            resp = QMessageBox.question(
                self,
                "Curated List Empty",
                "No items in the curated list. Fire anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if resp != QMessageBox.StandardButton.Yes:
                return

        # Pull duration from the textbox (default 30)
        try:
            duration_sec = int(self.duration_input.text().strip() or "30")
        except ValueError:
            duration_sec = 30

        self._send_service("fire", {
            "curated_batch": curated_items,
            "duration_sec": duration_sec
        })

    def _on_idea_selected(self):
        item = self.idea_list.currentItem()
        if not item:
            return
        idea = item.data(Qt.ItemDataRole.UserRole) or {}
        topic = (idea.get("topic") or "").strip()
        self.selected_topic_box.setText(topic)

    def _on_generate_replacement(self):
        instruction = self.modify_input.toPlainText().strip()
        if not instruction:
            QMessageBox.information(self, "No Instruction", "Type how to modify the topic first.")
            return

        selected_items = self.idea_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Select one or more ideas first.")
            return

        curated_batch = []
        for item in selected_items:
            idea = item.data(Qt.ItemDataRole.UserRole)
            if idea:
                curated_batch.append({
                    "base_topic": idea.get("topic"),
                    "instruction": instruction
                })

        count = max(1, min(int(self.count_input.text().strip() or "10"), 50))

        self._send_service("modify_ideas", {
            "curated_batch": curated_batch,
            "count": count
        })

    # ---------------------------------------------------------
    # ACK handler from TrendScout (via Matrix verified inbound)
    # ---------------------------------------------------------
    def _handle_topic_forge_ack(self, session_id, channel, source, payload, **_):
        try:
            if session_id != self.session_id:
                return

            content = payload.get("content", payload) or {}
            token = content.get("token")
            if token and token in self._pending_tokens:
                self._pending_tokens.discard(token)

            status = content.get("status", "ok")
            action = content.get("action", "unknown")

            # log
            msg = content.get("message") or ""
            if msg:
                self.output_box.append(f"✔ {action}: {msg}")
            else:
                self.output_box.append(f"✔ {action} (status={status})")

            # route updates
            if action in ("mode_get", "mode_set"):
                mode = content.get("mode") or content.get("data", {}).get("mode")
                if mode:
                    self.lbl_mode_status.setText(f"current: {mode}")
                    # sync combobox without triggering extra stuff
                    idx = self.mode_combo.findText(mode)
                    if idx >= 0:
                        self.mode_combo.setCurrentIndex(idx)

            if action in ("timer_get", "timer_reset"):
                nxt = content.get("next_idea_run") or content.get("data", {}).get("next_idea_run")
                if nxt:
                    self.lbl_next_run.setText(f"next idea run: {nxt}")

            if action in ("generate_ideas", "modify_ideas"):
                self.current_batch_id = content.get("batch_id") or content.get("data", {}).get("batch_id")
                ideas = content.get("ideas") or content.get("data", {}).get("ideas") or []
                self._render_ideas(ideas)

            if action in ("curate_list", "curate_add", "curate_add_all", "curate_remove", "fire"):
                curated = content.get("curated") or content.get("data", {}).get("curated")
                if curated is not None:
                    self._render_curated(curated)
                else:
                    # if backend doesn't return snapshot on write, we request it
                    if action != "curate_list":
                        self._send_service("curate_list")

            # keep debug pane helpful
            try:
                self.preview_box.setPlainText(json.dumps(content, indent=2))
            except Exception:
                pass

        except Exception as e:
            emit_gui_exception_log("TrendScout._handle_topic_forge_ack", e)

    # ---------------------------------------------------------
    # Render helpers
    # ---------------------------------------------------------
    def _render_ideas(self, ideas):
        self.last_ideas = ideas or []
        self.idea_list.clear()

        for idx, idea in enumerate(self.last_ideas):
            topic = (idea.get("topic") or "").strip()
            if not topic:
                topic = f"(untitled #{idx+1})"

            tags = idea.get("tags") or []
            desc = (idea.get("description") or "").strip()

            label = topic
            if tags:
                label = f"{topic}   [{', '.join(tags[:6])}]"

            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, idea)

            tooltip_parts = [topic]
            if tags:
                tooltip_parts.append("tags: " + ", ".join(tags))
            if desc:
                tooltip_parts.append("desc: " + (desc[:300] + ("…" if len(desc) > 300 else "")))
            it.setToolTip("\n".join(tooltip_parts))

            self.idea_list.addItem(it)

        self.output_box.append(f"🧠 Loaded {len(self.last_ideas)} idea(s). batch_id={self.current_batch_id or '?'}")

    def _render_curated(self, curated):
        self.last_curated = curated or []
        self.curated_list.clear()

        for idx, row in enumerate(self.last_curated):
            topic = (row.get("topic") or "").strip()
            if not topic:
                topic = f"(untitled #{idx+1})"
            tags = row.get("tags") or []

            label = topic
            if tags:
                label = f"{topic}   [{', '.join(tags[:6])}]"

            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, row)
            self.curated_list.addItem(it)

        self.output_box.append(f"📌 Curated list now {len(self.last_curated)} item(s).")

    # ---------------------------------------------------------
    # Status bootstrap
    # ---------------------------------------------------------
    def _request_status_refresh(self):
        # fetch mode + timer + curated snapshot
        self._send_service("mode_get")
        self._send_service("timer_get")
        self._send_service("curate_list")

    # ---------------------------------------------------------
    # Panel handling
    # ---------------------------------------------------------
    def get_panel_buttons(self):
        return [
            PanelButton("🎯", "Trend Topics", lambda: self.session_window.show_specialty_panel(self))
        ]

    def on_deployment_updated(self, deployment):
        # no-op
        pass

    # ---------------------------------------------------------
    # Bus Handlers (persistent)
    # ---------------------------------------------------------

    def _connect_signals(self):
        try:
            if not self._signals_connected:

                self.bus.on("inbound.verified.trend_scout_panel.topic_forge_ack", self._handle_topic_forge_ack)
                self._signals_connected = True

        except Exception as e:
            emit_gui_exception_log("CryptoAlert._connect_signals", e)

    def _disconnect_signals(self):
        pass

    def _on_close(self):

        try:
            if self._signals_connected:

                self.bus.off("inbound.verified.trend_scout_panel.topic_forge_ack", self._handle_topic_forge_ack)
                self._signals_connected = False

        except Exception as e:
            emit_gui_exception_log("CryptoAlert._disconnect_signals", e)
