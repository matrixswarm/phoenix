import threading, logging
from matrix_gui.core.emit_gui_exception_log import emit_gui_exception_log
from .connector.https.https import HTTPSConnector
from .connector.wss.wss import WSSConnector
from .connector.smtp.smtp import SMTPConnector
from .entity.adapter.agent_connection_wrapper import AgentConnectionWrapper
from matrix_gui.config.boot.globals import get_sessions
from matrix_gui.core.dispatcher.session_bus import SessionBus
from matrix_gui.core.connector_bus import ConnectorBus

# later: from discord_connector import connect_discord, etc.

log = logging.getLogger("deployment_connector")

SUPPORTED_PROTOS = {"https", "wss", "smtp"}

# Map proto → connector function
CONNECTOR_MAP = {
    "https": HTTPSConnector(),
    "wss": WSSConnector(),
    "smtp": SMTPConnector(),
    # future: "discord": connect_discord,
    # future: "telegram": connect_telegram,
    # future: "slack": connect_slack,
    # future: "sms": connect_sms,
}


def _connect_single(deployment, session_id, dep_id):

    try:
        sessions = get_sessions()
        if not sessions:
            print("[ERROR] No global sessions instance")
            return

        group = {
            "id": session_id,
            "name": deployment.get("name", dep_id),
            "proto": "deployment",
            "deployment_id": dep_id,
            "deployment": deployment
        }

        # Register in SessionManager
        ctx = sessions.create(group)
        ctx.channels = {}
        ctx.status = {}
        print(f"[DEBUG] Deployment {dep_id} using session {session_id}")

        # Enhance ctx with a bus
        ctx.bus = SessionBus(session_id)
        ctx._bus_refs = []  # Track all bus bindings for cleanup

        # Wire ConnectorBus → SessionBus (record them for later removal)
        def inbound_proxy(**kw):
            ctx.bus.emit("inbound.message", **kw)

        def status_proxy(**kw):
            ctx.bus.emit("channel.status", **kw)

        ConnectorBus.get(session_id).on("inbound.raw", inbound_proxy)
        ConnectorBus.get(session_id).on("channel.status", status_proxy)
        ctx._bus_refs.extend([
            ("inbound.raw", inbound_proxy),
            ("channel.status", status_proxy)
        ])

        print(f"[BRIDGE] ConnectorBus wired into SessionBus for {session_id}")

        # Launch connectors for each agent
        for agent in deployment.get("agents", []):

            adapter = AgentConnectionWrapper(agent, deployment)

            proto, host, port = adapter.proto, adapter.host, adapter.port

            #this insures the agent is a real connection
            connector_fn = CONNECTOR_MAP.get(proto, False)
            if connector_fn:
                # Some connectors (SMTP, matrix_email, discord) do not use host/port.
                args = (agent, deployment, session_id)
                try:
                    threading.Thread(
                        target=connector_fn,
                        args=args,
                        daemon=True
                    ).start()
                    print(f"[CONNECT] Launched {proto} connector for {agent.get('universal_id')}")
                except Exception as e:
                    print(f"[CONNECT][ERROR] Failed to launch {proto} connector for {agent.get('universal_id')}: {e}")

        return ctx

    except Exception as e:
        emit_gui_exception_log("deployment_connector._connect_single", e)
        return {}

#
def destroy_session(session_id):
    ctx = get_sessions().get(session_id)
    if not ctx:
        print(f"[DESTROY] ❌ No session {session_id} found")
        return

    # --- 1. Disconnect bus bridges ---
    if hasattr(ctx, "_bus_refs"):
        for event_name, handler in ctx._bus_refs:
            try:
                ConnectorBus.get(session_id).off(event_name, handler)
                print(f"[DESTROY] Disconnected {event_name} from {session_id}")
            except Exception as e:
                print(f"[DESTROY] Error unbinding {event_name}: {e}")

    # --- 2. Close connectors ---
    for channel, conn in list(ctx.channels.items()):
        if hasattr(conn, "close"):
            try:
                conn.close(session_id=session_id, channel_name=channel)
                print(f"[DESTROY] Closed connector {channel}")
            except Exception as e:
                print(f"[DESTROY] Error closing {channel}: {e}")
        ctx.channels.pop(channel, None)
        ctx.status[channel] = "disconnected"

    # --- 3. Clear the session bus ---
    if hasattr(ctx, "bus"):
        ctx.bus.clear()
        print(f"[DESTROY] closing down buses.")
