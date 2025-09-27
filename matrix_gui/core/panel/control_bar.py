import os
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QToolButton
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QIcon
from matrix_gui.core.emit_gui_exception_log import emit_gui_exception_log
from PyQt5.QtWidgets import QToolBar

class PanelButton:
    def __init__(self, icon, text, handler):
        self.icon = icon
        self.text = text
        self.handler = handler


class ControlBar(QWidget):
    def __init__(self, session_window):
        super().__init__(session_window)

        try:
            self.session_window = session_window

            # horizontal layout instead of QToolBar
            self.layout = QHBoxLayout(self)
            self.layout.setContentsMargins(4, 2, 4, 2)
            self.layout.setSpacing(8)
            self.setLayout(self.layout)

            font = QFont("Segoe UI Emoji", 9)
            self.setFont(font)

            self.icon_size = QSize(32, 32)

            # Build default buttons
            self.default_buttons = []
            self._build_default_buttons()

            # mount at top of window
            session_window.addToolBar(Qt.TopToolBarArea, self._as_toolbar_proxy())
        except Exception as e:
            emit_gui_exception_log("session_window._update_log_status_bar", e)


    # ---- Helpers -------------------------------------------------
    def _make_button(self, icon, text, handler):

        try:
            btn = QToolButton()
            btn.setFont(self.font())
            btn.setIconSize(self.icon_size)
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

            if icon and (icon.endswith(".png") or icon.endswith(".svg")) and os.path.exists(icon):
                btn.setIcon(QIcon(icon))
            elif icon:
                # fallback: emoji as text prefix
                btn.setText(f"{icon} {text}")

            if text and not btn.text():
                btn.setText(text)

            if handler:
                btn.clicked.connect(handler)

            return btn
        except Exception as e:
            emit_gui_exception_log("session_window._update_log_status_bar", e)


    def add_button(self, icon, text, handler, add_to_bar=True):

        try:
            print(f"[DEBUG] ControlBar.add_button called with icon={icon}, text={text}")
            btn = self._make_button(icon, text, handler)
            if add_to_bar:
                self.layout.addWidget(btn)
            return btn
        except Exception as e:
            emit_gui_exception_log("session_window._update_log_status_bar", e)

    def clear_buttons(self):
        while self.layout.count():

            try:
                item = self.layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.setParent(None)
            except Exception as e:
                emit_gui_exception_log("session_window._update_log_status_bar", e)


    def reset_to_default(self):
        try:
            self.clear_buttons()
            for btn in self.default_buttons:
                self.layout.addWidget(btn)
        except Exception as e:
            emit_gui_exception_log("session_window._update_log_status_bar", e)


    def _make_toggle_button(self, icon, text, check_fn, toggle_fn):
        try:
            btn = QToolButton()
            btn.setFont(self.font())
            btn.setIconSize(self.icon_size)
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            btn.setCheckable(True)
            btn.setChecked(check_fn())
            btn.setText(f"{icon} {text}")
            btn.toggled.connect(toggle_fn)
            return btn
        except Exception as e:
            emit_gui_exception_log("session_window._update_log_status_bar", e)

    # ---- Build default/global buttons ----------------------------
    def _build_default_buttons(self):

        try:
            self.default_buttons = []
            self.default_buttons.append(
                self._make_button("☠️", "Delete Agent", self.session_window._launch_delete_agent_modal))
            self.default_buttons.append(
                self._make_button("♻️", "Replace Source", self.session_window._launch_replace_agent_source))

            self.default_buttons.append(
                self._make_toggle_button(
                    "🧵", "Threads",
                    lambda: self.session_window.detail_panel.inspector_group.isVisible(),
                    self.session_window.toggle_threads_panel
                )
            )
            self.default_buttons.append(
                self._make_toggle_button(
                    "⚙️", "Config",
                    lambda: self.session_window.detail_panel.config_group.isVisible(),
                    self.session_window.toggle_config_panel
                )
            )
            self.default_buttons.append(
                self._make_toggle_button(
                    "⏸️", "Pause Logs",
                    lambda: self.session_window.log_paused,
                    self.session_window._toggle_log_pause
                )
            )

            self.reset_to_default()

        except Exception as e:
            emit_gui_exception_log("session_window._update_log_status_bar", e)


    # ---- Adapter so SessionWindow can still use addToolBar() -----
    def _as_toolbar_proxy(self):
        try:

            proxy = QToolBar("ControlBarProxy")
            proxy.addWidget(self)
            return proxy
        except Exception as e:
            emit_gui_exception_log("session_window._update_log_status_bar", e)