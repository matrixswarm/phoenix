# Authored by Daniel F MacDonald and ChatGPT-5 aka The Generals
import time, copy
from PyQt6.QtCore import QObject
from matrix_gui.core.dialog.inject_agent_dialog import InjectAgentDialog
from matrix_gui.core.emit_gui_exception_log import emit_gui_exception_log

class InjectAgentPanel(QObject):
    """Launches an InjectAgentDialog and handles Phoenix callback + toaster."""

    def __init__(self, session_id, bus, conn, deployment, parent=None):
        super().__init__(parent)
        self.session_id = session_id
        self.bus = bus
        self.conn = conn
        self.deployment = copy.deepcopy(deployment)
        self.parent = parent
        self._dlg = None
        self.clear_to_show = True

        # Listen for injection confirmation from Matrix → Phoenix
        self.bus.on(
            f"inbound.verified.inject_dialog.result.{self.session_id}",
            self._handle_result
        )

    def launch(self, uid: str = None):
        """Open the inject dialog window."""
        try:
            if not self.clear_to_show:
                return

            self.clear_to_show = False

            self._dlg = InjectAgentDialog(
                session_id=self.session_id,
                bus=self.bus,
                conn=self.conn,
                deployment=self.deployment,
                parent=self.parent
            )
            if uid:
                self._dlg.preselect_parent(uid)

            self._dlg.finished.connect(self._on_finished)
            self._dlg.show()
        except Exception as e:
            emit_gui_exception_log("InjectAgentPanel.launch", e)

    def _on_finished(self, result):
        """Dialog closed — nothing more to do; Matrix handles injection."""
        if result != self._dlg.DialogCode.Accepted:
            self._cleanup()
        self.clear_to_show = True

    def _handle_result(self, session_id, channel, source, payload, ts):
        """Phoenix inbound event: injection completed or failed."""
        try:
            content = payload.get("content", {})
            uid = content.get("target_universal_id", "unknown")
            agents = content.get("agents", [])
            result = content.get("result", {})
            success = result.get("success", False)
            err = result.get("error")

            # Build message and details
            agent_names = ", ".join(
                [a.get("name", "?") for a in agents]
            ) or "unknown"

            if success:
                msg = f"🧬 Injected {len(agents)} agent(s) ({agent_names}) under '{uid}'"
            else:
                msg = f"⚠️ Injection failed for '{uid}': {err or 'Unknown error'}"

            # Send toast to cockpit
            if self.conn:
                self.conn.send({
                    "type": "ui_toast",
                    "session_id": self.session_id,
                    "message": msg
                })

            # Log event to Swarm Feed
            if self.conn:
                event = {
                    "event_type": "inject",
                    "agent": uid,
                    "details": msg,
                    "session_id": self.session_id,
                    "deployment": self.deployment.get("label", "unknown"),
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "level": "INFO" if success else "ERROR"
                }
                self.conn.send({
                    "type": "swarm_feed",
                    "session_id": self.session_id,
                    "event": event
                })

        except Exception as e:
            emit_gui_exception_log("InjectAgentPanel._handle_result", e)
        finally:
            self._cleanup()

    def _cleanup(self):
        """Ensure dialog and panel refs cleaned up."""
        if self._dlg:
            self._dlg.deleteLater()
            self._dlg = None
