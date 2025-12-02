# Authored by Daniel F MacDonald and ChatGPT-5.1 aka The Generals
# CONTENT LAB PANEL – Oracle + TrendScout Edition

import time
import json

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QGroupBox, QLineEdit, QTabWidget,
    QMessageBox, QComboBox
)
from PyQt6.QtCore import Qt

from matrix_gui.core.panel.custom_panels.interfaces.base_panel_interface import PhoenixPanelInterface
from matrix_gui.core.class_lib.packet_delivery.packet.standard.command.packet import Packet
from matrix_gui.core.panel.control_bar import PanelButton
from matrix_gui.core.emit_gui_exception_log import emit_gui_exception_log


class TrendScout(PhoenixPanelInterface):
    """
    Commander Edition – Content Lab Panel

    New job:
      • No scraping.
      • Send content generation requests to TrendScout (which talks to Oracle).
      • TrendScout inserts rows into the `content_ideas` table.
      • Panel shows simple acks + optional previews.
    """

    cache_panel = True

    def __init__(self, session_id, bus=None, node=None, session_window=None):
        super().__init__(session_id, bus, node=node, session_window=session_window)

        self._signals_connected = False

        layout = self._build_layout()
        self.setLayout(layout)

        self._connect_signals()

        print("[CONTENT_LAB] Commander Edition panel online.")

    # ---------------------------------------------------------
    # UI LAYOUT
    # ---------------------------------------------------------
    def _build_layout(self):
        layout = QVBoxLayout()

        layout.addWidget(QLabel("<b>Content Lab – TrendScout / Oracle</b>"))

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # === Tab 1: Generator ===
        gen_tab = QWidget()
        gen_lay = QVBoxLayout(gen_tab)

        cfg_box = QGroupBox("Generation Settings")
        cfg_lay = QVBoxLayout(cfg_box)

        # Mode selector
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Tutorial Ideas",
            "Funny Stories",
            "Emotional Posts (future)"
        ])
        mode_row.addWidget(self.mode_combo)
        cfg_lay.addLayout(mode_row)

        # Theme / seed text
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Theme / Seed:"))
        self.theme_input = QLineEdit()
        self.theme_input.setPlaceholderText("e.g. cute animals + horror + social media virality")
        theme_row.addWidget(self.theme_input)
        cfg_lay.addLayout(theme_row)

        # Count
        count_row = QHBoxLayout()
        count_row.addWidget(QLabel("Count:"))
        self.count_input = QLineEdit("20")
        count_row.addWidget(self.count_input)
        cfg_lay.addLayout(count_row)

        gen_lay.addWidget(cfg_box)

        # --- Buttons ---
        btn_row = QHBoxLayout()
        self.btn_generate = QPushButton("Generate & Store")
        self.btn_generate.clicked.connect(self._generate_and_store)
        btn_row.addWidget(self.btn_generate)

        gen_lay.addLayout(btn_row)

        # --- Output / log ---
        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        gen_lay.addWidget(QLabel("Activity Log:"))
        gen_lay.addWidget(self.output_box)

        self.tabs.addTab(gen_tab, "Generator")

        # === Tab 2: Debug / Preview ===
        preview_tab = QWidget()
        prev_lay = QVBoxLayout(preview_tab)

        self.preview_box = QTextEdit()
        self.preview_box.setReadOnly(True)
        prev_lay.addWidget(QLabel("Last Payload / Debug Info"))
        prev_lay.addWidget(self.preview_box)

        self.tabs.addTab(preview_tab, "Debug")

        return layout

    # ---------------------------------------------------------
    # GENERATION TRIGGER
    # ---------------------------------------------------------
    def _resolve_mode(self):
        """
        Map human label → internal mode string.
        """
        text = self.mode_combo.currentText()
        if text.startswith("Tutorial"):
            return "tutorial"
        if text.startswith("Funny"):
            return "funny_story"
        if text.startswith("Emotional"):
            return "emotional"  # future
        return "tutorial"

    def _generate_and_store(self):
        try:
            mode = self._resolve_mode()
            theme = self.theme_input.text().strip()
            count_str = self.count_input.text().strip() or "20"

            try:
                count = int(count_str)
            except ValueError:
                QMessageBox.warning(self, "Invalid Count", "Count must be numeric.")
                return

            self.output_box.clear()
            self.output_box.append(f"⏳ Sending content request to TrendScout...\n")
            self.output_box.append(f"- Mode: {mode}\n- Theme: {theme or '(default)'}\n- Count: {count}\n")

            token = f"content_{int(time.time())}"

            pk = Packet()
            pk.set_data({
                "handler": "cmd_service_request",
                "ts": time.time(),
                "content": {
                    "service": "hive.trend_scout.content",
                    "payload": {
                        "mode": mode,
                        "theme": theme,
                        "count": count,
                        "session_id": self.session_id,
                        "token": token,
                        "return_handler": "trend_ingest_panel.content_ack",
                    },
                },
            })

            self.bus.emit(
                "outbound.message",
                session_id=self.session_id,
                channel="outgoing.command",
                packet=pk,
            )

            self.btn_generate.setEnabled(False)

        except Exception as e:
            emit_gui_exception_log("ContentLab._generate_and_store", e)
            QMessageBox.critical(self, "Error", str(e))

    # ---------------------------------------------------------
    # CALLBACK FROM TRENDSCOUT
    # ---------------------------------------------------------
    def _handle_content_ack(self, session_id, channel, source, payload, **_):
        try:
            if session_id != self.session_id:
                return

            content = payload.get("content", {})
            mode = content.get("mode", "unknown")
            inserted = content.get("inserted", 0)
            extra = content.get("extra", {})

            self.output_box.append("\n✅ TrendScout ACK received:")
            self.output_box.append(f"- Mode: {mode}")
            self.output_box.append(f"- Inserted: {inserted}")

            if extra:
                self.preview_box.setPlainText(json.dumps(extra, indent=2))

        except Exception as e:
            emit_gui_exception_log("ContentLab._handle_content_ack", e)
        finally:
            self.btn_generate.setEnabled(True)

    # ---------------------------------------------------------
    # PANEL HANDLING
    # ---------------------------------------------------------
    def get_panel_buttons(self):
        return [
            PanelButton("📊", "Content Lab", lambda: self.session_window.show_specialty_panel(self))
        ]

    def on_deployment_updated(self, deployment):
        # no-op for now
        pass

    # ---------------------------------------------------------
    # Bus Handlers (persistent)
    # ---------------------------------------------------------
    def _connect_signals(self):

        try:
            if not self._signals_connected:

                # TrendScout will crypto_reply with this handler name
                self.bus.on(
                    f"inbound.verified.trend_ingest_panel.content_ack",
                    self._handle_content_ack,
                )
                self._signals_connected = True

        except Exception as e:
            emit_gui_exception_log("ContentLab._connect_signals", e)

    def _disconnect_signals(self):

        try:
            if self._signals_connected:
                self._signals_connected = False
                self.bus.off(
                    f"inbound.verified.trend_ingest_panel.content_ack",
                    self._handle_content_ack,
                )
        except Exception as e:
            emit_gui_exception_log("ContentLab._disconnect_signals", e)
