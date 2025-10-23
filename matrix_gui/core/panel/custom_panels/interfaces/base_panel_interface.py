from abc import ABCMeta, abstractmethod
from PyQt6.QtWidgets import QWidget

# Hybrid metaclass: combines Qt's QWidget metaclass and ABCMeta
class PanelABCMeta(type(QWidget), ABCMeta):
    pass

class PhoenixPanelInterface(QWidget, metaclass=PanelABCMeta):
    """
    Base class for all Phoenix custom panels.
    Enforces required interface methods.
    """
    cache_panel = True

    def __init__(self, session_id, bus, node=None, session_window=None):
        super().__init__(session_window)
        self.session_id = session_id
        self.bus = bus
        self.node = node
        self.session_window = session_window
        self.conn = getattr(session_window, "conn", None)
        self.deployment = getattr(session_window, "deployment", {})

        # enforce implementation
        missing = []
        for fn in ["_connect_signals", "_disconnect_signals", "get_panel_buttons", "on_deployment_updated"]:
            if not callable(getattr(self, fn, None)):
                missing.append(fn)
        if missing:
            raise NotImplementedError(
                f"{self.__class__.__name__} missing required methods: {', '.join(missing)}"
            )

    @abstractmethod
    def _connect_signals(self): ...
    @abstractmethod
    def _disconnect_signals(self): ...
    @abstractmethod
    def get_panel_buttons(self): ...
    @abstractmethod
    def on_deployment_updated(self, deployment): ...
