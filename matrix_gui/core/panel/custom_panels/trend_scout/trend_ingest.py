# Authored by Daniel F MacDonald and ChatGPT-5.1 aka The Generals
# THE ULTIMATE TRENDSCRAPER INGEST PANEL
# Phoenix Native – Scraper Process Controlled by SessionWindow

import time
import json
import traceback

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QGroupBox, QCheckBox, QLineEdit, QTabWidget,
    QMessageBox, QComboBox
)
from PyQt6.QtCore import QTimer, Qt

from matrix_gui.core.panel.custom_panels.interfaces.base_panel_interface import PhoenixPanelInterface
from matrix_gui.core.class_lib.packet_delivery.packet.standard.command.packet import Packet
from matrix_gui.core.panel.control_bar import PanelButton
from matrix_gui.core.emit_gui_exception_log import emit_gui_exception_log
from matrix_gui.core.event_bus import EventBus


class TrendIngest(PhoenixPanelInterface):
    """
    Commander Edition — Battle-Ready Trend Ingestion Panel
    Talks to scraper subsystem via:
        EventBus.emit("scraper.run.requested", ...)
    Receives:
        "scrape.completed"
        "scrape.failed"
        "scrape.log"
    """

    cache_panel = True

    def __init__(self, session_id, bus=None, node=None, session_window=None):
        super().__init__(session_id, bus, node=node, session_window=session_window)

        # Options
        self.auto_mode = False
        self.auto_push = True
        self.scrape_interval_hours = 3

        # Filters
        self.keyword_include = ""
        self.keyword_exclude = ""
        self.score_threshold = 0

        # Per-source toggles
        self.source_flags = {
            "youtube": True,
            "x": True,
            "google_trends": True,
            "reddit": False,        # reserved
            "tiktok": False,        # reserved
            "instagram": False      # reserved
        }

        self.raw_data = {}
        self.topics_buffer = []
        self.last_scrape_ts = None

        # Signals
        self._signals_connected = False

        # Build UI
        layout = self._build_layout()
        self.setLayout(layout)

        self._start_timers()

        print("[TREND_INGEST] Commander Edition panel online.")

    # ---------------------------------------------------------
    # UI LAYOUT
    # ---------------------------------------------------------
    def _build_layout(self):
        layout = QVBoxLayout()

        layout.addWidget(QLabel("<b>Trend Ingest – Commander Edition</b>"))

        # ---------------- TABS ----------------
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # === Tab 1: Dashboard ===
        dash = QWidget()
        dash_lay = QVBoxLayout()
        dash.setLayout(dash_lay)

        # --- Source selection ---
        src_box = QGroupBox("Sources to Scrape")
        src_l = QVBoxLayout()

        def add_flag(name, label):
            cb = QCheckBox(label)
            cb.setChecked(self.source_flags[name])
            cb.stateChanged.connect(lambda s, n=name: self._update_source_flag(n, s))
            src_l.addWidget(cb)

        add_flag("youtube", "YouTube Trending")
        add_flag("x", "X Trending (via Nitter)")
        add_flag("google_trends", "Google Trends")
        add_flag("reddit", "Reddit Hot (future)")
        add_flag("tiktok", "TikTok Explore (future)")
        add_flag("instagram", "Instagram Explore (future)")

        src_box.setLayout(src_l)
        dash_lay.addWidget(src_box)

        # --- Filters ---
        filter_box = QGroupBox("Filters")
        fl = QVBoxLayout()

        row_kw = QHBoxLayout()
        row_kw.addWidget(QLabel("Include (comma):"))
        self.include_input = QLineEdit()
        row_kw.addWidget(self.include_input)

        row_ex = QHBoxLayout()
        row_ex.addWidget(QLabel("Exclude (comma):"))
        self.exclude_input = QLineEdit()
        row_ex.addWidget(self.exclude_input)

        row_score = QHBoxLayout()
        row_score.addWidget(QLabel("Minimum Score:"))
        self.score_input = QLineEdit("0")
        row_score.addWidget(self.score_input)

        fl.addLayout(row_kw)
        fl.addLayout(row_ex)
        fl.addLayout(row_score)

        filter_box.setLayout(fl)
        dash_lay.addWidget(filter_box)

        # --- Automation ---
        auto_box = QGroupBox("Automation")
        al = QVBoxLayout()

        self.auto_checkbox = QCheckBox("Automatic Scraping")
        self.auto_checkbox.stateChanged.connect(self._toggle_auto_mode)
        al.addWidget(self.auto_checkbox)

        self.autopush_checkbox = QCheckBox("Auto-Push to TrendScout")
        self.autopush_checkbox.setChecked(True)
        self.autopush_checkbox.stateChanged.connect(
            lambda s: setattr(self, "auto_push", s == Qt.CheckState.Checked)
        )
        al.addWidget(self.autopush_checkbox)

        self.interval_combo = QComboBox()
        self.interval_combo.addItems(["1 hour", "3 hours", "6 hours"])
        self.interval_combo.setCurrentIndex(1)
        self.interval_combo.currentIndexChanged.connect(self._update_interval)
        al.addWidget(QLabel("Scrape every:"))
        al.addWidget(self.interval_combo)

        auto_box.setLayout(al)
        dash_lay.addWidget(auto_box)

        # --- Buttons ---
        row_btns = QHBoxLayout()
        self.btn_run = QPushButton("Run Scraper Now")
        self.btn_run.clicked.connect(self._run_scraper_now)
        row_btns.addWidget(self.btn_run)

        self.btn_push = QPushButton("Push to TrendScout")
        self.btn_push.clicked.connect(self._push_now)
        row_btns.addWidget(self.btn_push)

        dash_lay.addLayout(row_btns)
        self.tabs.addTab(dash, "Dashboard")

        # === Tab 2: Results ===
        self.results_tab = QWidget()
        rlay = QVBoxLayout()
        self.results_tab.setLayout(rlay)

        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        rlay.addWidget(self.results_text)

        self.tabs.addTab(self.results_tab, "Results")

        # === Tab 3: Raw JSON ===
        self.raw_tab = QWidget()
        raw_lay = QVBoxLayout()
        self.raw_tab.setLayout(raw_lay)

        self.raw_text = QTextEdit()
        self.raw_text.setReadOnly(True)
        raw_lay.addWidget(self.raw_text)

        self.tabs.addTab(self.raw_tab, "Raw JSON")

        # === Tab 4: Scraper Logs ===
        self.log_tab = QWidget()
        log_lay = QVBoxLayout()
        self.log_tab.setLayout(log_lay)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        log_lay.addWidget(self.log_view)

        self.tabs.addTab(self.log_tab, "Scraper Log")

        return layout

    # ---------------------------------------------------------
    # OPTION UPDATES
    # ---------------------------------------------------------
    def _update_source_flag(self, name, state):
        self.source_flags[name] = (state == Qt.CheckState.Checked)

    def _toggle_auto_mode(self, state):
        self.auto_mode = (state == Qt.CheckState.Checked)

    def _update_interval(self, index):
        self.scrape_interval_hours = [1, 3, 6][index]

    # ---------------------------------------------------------
    # TIMER CYCLE
    # ---------------------------------------------------------
    def _start_timers(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self._auto_cycle)
        self.timer.start(60_000)

    def _auto_cycle(self):
        if not self.auto_mode:
            return

        now = time.time()
        if not self.last_scrape_ts:
            self._run_scraper_now()
            return

        if (now - self.last_scrape_ts) >= self.scrape_interval_hours * 3600:
            self._run_scraper_now()

    # ---------------------------------------------------------
    # SCRAPER EXECUTION
    # ---------------------------------------------------------
    def _run_scraper_now(self):
        """Tell SessionWindow to run scraper with options."""
        try:
            print("[TREND_INGEST] Commander initiating scrape run...")

            sources = [k for k, v in self.source_flags.items() if v]

            filters = {
                "include": self.include_input.text(),
                "exclude": self.exclude_input.text(),
                "score_threshold": int(self.score_input.text() or "0")
            }

            self.bus.emit(
                "scraper.run.requested",
                session_id=self.session_id,
                sources=sources,
                filters=filters,
                keepalive=True
            )

            self.last_scrape_ts = time.time()

        except Exception as e:
            QMessageBox.critical(self, "Error Running Scraper", str(e))

    # ---------------------------------------------------------
    # SCRAPER CALLBACKS
    # ---------------------------------------------------------

    def _scrape_log(self, session_id, line, **_):
        if session_id != self.session_id:
            return
        self.log_view.append(line)

    def _scrape_failed(self, session_id, error, **_):

        d(error)

        import traceback
        print("##############################################")
        print("🔥 PANEL RECEIVED SCRAPER ERROR 🔥")
        print(error)
        print("##############################################")

        QMessageBox.critical(self, "SCRAPER ERROR", error)


        if session_id != self.session_id:
            return

        # If backend sent a formatted traceback already — use it
        if "\n" in error:
            tb = error
        else:
            # Local fallback: produce traceback from here
            tb = traceback.format_exc()

        # Display human-friendly popup with scrollable text
        dlg = QMessageBox()
        dlg.setWindowTitle("Scraper Error (with Traceback)")
        dlg.setIcon(QMessageBox.Icon.Critical)
        dlg.setText("A scraper error occurred. Full traceback below:")
        dlg.setDetailedText(tb)
        dlg.exec()

    def _scrape_finished(self, session_id, data, **_):

        try:

            if session_id != self.session_id:
                return

            self.raw_data = data
            self.raw_text.setPlainText(json.dumps(data, indent=2))

            # Build per-source breakdown
            result_out = []
            topics_all = []

            for src, items in data.items():
                result_out.append(f"=== {src.upper()} ===")
                for t in items:
                    if isinstance(t, dict):
                        topic = t.get("topic", str(t))
                        score = t.get("score", "?")
                        result_out.append(f"- {topic} ({score})")
                        topics_all.append({"topic": topic, "score": score})
                    else:
                        # fallback for unexpected string entries
                        result_out.append(f"- {t}")
                        topics_all.append({"topic": str(t), "score": 0})

                result_out.append("")

            self.results_text.setPlainText("\n".join(result_out))

            # Flatten for push
            self.topics_buffer = topics_all

            if self.auto_push:
                self._push_now()
        except Exception as e:
            emit_gui_exception_log("TrendIngest._scrape_finished", e)
            QMessageBox.critical(self, "Push Error", str(e))

    # ---------------------------------------------------------
    # PUSH TO SWARM
    # ---------------------------------------------------------
    def _push_now(self):
        if not self.topics_buffer:
            QMessageBox.warning(self, "No Data", "Nothing to push.")
            return

        print("[TREND_INGEST] Pushing topics to TrendScout...")

        try:
            pk = Packet()
            pk.set_data({
                "handler": "cmd_service_request",
                "ts": time.time(),
                "content": {
                    "service": "hive.trend_scout.push_local",
                    "payload": {
                        "topics": self.topics_buffer,
                        "source": "local_ingest",
                        "session_id": self.session_id,
                        "pushed_at": time.time(),
                        "return_handler": "trend_ingest_panel.push_ack"
                    }
                }
            })

            self.bus.emit(
                "outbound.message",
                session_id=self.session_id,
                channel="outgoing.command",
                packet=pk
            )

        except Exception as e:
            emit_gui_exception_log("TrendIngest._push_now", e)
            QMessageBox.critical(self, "Push Error", str(e))

    # ---------------------------------------------------------
    # PANEL HANDLING
    # ---------------------------------------------------------
    def get_panel_buttons(self):
        return [
            PanelButton("📊", "Trend Ingest", lambda: self.session_window.show_specialty_panel(self))
        ]

    def on_deployment_updated(self, deployment):
        # no-op
        pass

    # ---------------------------------------------------------
    # Bus Handlers (persistent)
    # ---------------------------------------------------------
    def _connect_signals(self):

        """Attach bus listeners."""
        try:
            if self._signals_connected:
                return
            self._signals_connected = True

            self.bus.on("scrape.completed", self._scrape_finished)
            self.bus.on("scrape.failed", self._scrape_failed)
            self.bus.on("scrape_log", self._scrape_log)

        except Exception as e:
            emit_gui_exception_log("LogWatcher._connect_signals", e)

    def _disconnect_signals(self):
        """Detach bus listeners and clear any buffered lines."""
        pass

    def _on_close(self):
        if self._signals_connected:
            try:
                if not self._signals_connected:
                    return
                self._signals_connected = False

                self.bus.off("scrape.completed", self._scrape_finished)
                self.bus.off("scrape.failed", self._scrape_failed)
                self.bus.off("scrape_log", self._scrape_log)

            except Exception as e:
                emit_gui_exception_log("trend_scout._disconnect_signals", e)
