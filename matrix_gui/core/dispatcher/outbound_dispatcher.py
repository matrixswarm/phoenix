from matrix_gui.core.emit_gui_exception_log import emit_gui_exception_log
from matrix_gui.config.boot.globals import get_sessions
from matrix_gui.core.class_lib.packet_delivery.packet.standard.command.packet import Packet
from matrix_gui.core.class_lib.packet_delivery.utility.security.packet_security import wrap_packet_securely
class OutboundDispatcher:
    """
    Dispatches outbound messages from the GUI to the MatrixSwarm.

    This class listens for 'outbound.message' events, signs the
    payloads using a private key retrieved from the vault, and routes
    the messages to the correct channel (HTTPS or WSS).
    """
    def __init__(self, bus, session_id):
        """
        Initializes the dispatcher and sets up the event listener.

        Args:
            bus: The event bus instance for listening to messages.
        """
        self._session_id = session_id
        self._outbound_connector=None
        self._resolved_channel=None
        bus.on("outbound.message", self._handle_outbound)

    def _get_ctx(self):

        r=None
        try:
            r = get_sessions().get(self._session_id)
        except Exception as e:
            pass
        return r

    def get_outbound_connector(self):
        """
        Returns the current outbound connector (object + proto name).
        """
        try:
            ctx = self._get_ctx()
            if not ctx or not self._resolved_channel:
                return None

            connector = ctx.channels.get(self._resolved_channel)
            if not connector:
                return None

            # each connector (HTTPSConnector / SMTPConnector) defines .proto
            proto = getattr(connector, "proto", None)
            return {"connector": connector, "proto": proto}
        except Exception as e:
            emit_gui_exception_log("OutboundDispatcher.get_outbound_connector", e)
            return None

    def set_outbound_connector(self, agent:dict):

        ctx = self._get_ctx()

        if ctx is None:
            return

        ch = agent.get("connection", {})

        proto=None
        if ch.get("channel") == "outgoing.command":
            proto = ch.get("proto")

        resolved_channel = None
        for ch, connector in ctx.channels.items():
            if getattr(connector, "proto", "").lower() == proto:
                resolved_channel = ch
                break

        if not resolved_channel:
            print(f"[DISPATCHER] ❌ No active connector for proto '{proto}' in session {self._session_id}")
            return

        self._resolved_channel=resolved_channel

    #called on the bus; responsible for sending the packet to a given universe
    def _handle_outbound(self, session_id, channel, packet:Packet,
                                                     security_sig=True,
                                                     security_encryption=True,
                                                     security_target_universal_id="matrix"):
        try:

            ctx= self._get_ctx()
            if ctx is None:
                print("[OutboundDispatcher][_handle_outbound] ctx set None, aborting sending packet.")
                return

            dep = ctx.group.get("deployment", {}) if ctx else {}
            if not dep:
                print("[OutboundDispatcher][_handle_outbound] no deployment set, aborting sending packet.")
                return

            if not self._resolved_channel:
                print("[OutboundDispatcher][_handle_outbound] a resolved channel has not bee set, aborting sending packet.")
                return

            #Matrix Signing & Encryption - Inner Packet
            original_data = packet.get_packet()
            packet = wrap_packet_securely(
                original_data,
                deployment=dep,
                sign=security_sig,
                encrypt=security_encryption,
                target_uid=security_target_universal_id
            )
            conn = ctx.channels[self._resolved_channel]
            conn.send(packet)  # Send the packet

        except Exception as e:
            emit_gui_exception_log("OutboundDispatcher._handle_outbound", e)