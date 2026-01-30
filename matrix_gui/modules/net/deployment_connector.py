# Authored by Daniel F MacDonald and ChatGPT-5 aka The Generals
from .class_lib.processes.connection_launcher import ConnectionLauncher
from matrix_gui.core.emit_gui_exception_log import emit_gui_exception_log
from .entity.adapter.agent_connection_wrapper import AgentConnectionWrapper
from matrix_gui.config.boot.globals import get_sessions
from matrix_gui.core.dispatcher.session_bus import SessionBus
from matrix_gui.core.connector_bus import ConnectorBus

# Supported connector types for outbound/inbound agent protocols
SUPPORTED_PROTOS = {"https", "wss", "smtp"}

# Mapping of protocol type → full class path of connector implementation
CONNECTOR_MAP = {
    "https": "matrix_gui.modules.net.connector.egress.https.https.HTTPSConnector",
    "wss": "matrix_gui.modules.net.connector.ingress.wss.wss.WSSConnector",
    "smtp": "matrix_gui.modules.net.connector.egress.smtp.smtp.SMTPConnector",
    # Future connector types (examples):
    # "discord": connect_discord,
    # "telegram": connect_telegram,
    # "slack": connect_slack,
    # "sms": connect_sms,
}

def _connect_single(deployment, session_id, dep_id):
    """
    Initializes a full swarm connection group and its launch sequence.

    This function:
      - Creates a new session context in the global session manager
      - Instantiates a ConnectionLauncher for the session
      - Binds ConnectorBus events into the session's SessionBus
      - Iterates over all agents in the deployment and launches
        their associated connectors (if supported)

    @param deployment: Dict containing deployment structure, agents, and metadata
    @param session_id: Unique ID assigned to this session
    @param dep_id: Deployment ID reference (used in logs and labels)

    @return: SessionContext object with bus, launcher, and agents initialized
    """
    try:
        sessions = get_sessions()
        if not sessions:
            print("[ERROR] No global sessions instance")
            return

        connection_launcher = ConnectionLauncher()

        group = {
            "id": session_id,
            "name": deployment.get("name", dep_id),
            "proto": "deployment",
            "deployment_id": dep_id,
            "deployment": deployment,
            "connection_launcher": connection_launcher
        }

        # Register session in SessionManager
        ctx = sessions.create(group)
        ctx.channels = {}
        ctx.status = {}

        # Assign a session-bound event bus
        ctx.bus = SessionBus(session_id)
        ctx._bus_refs = []  # Track ConnectorBus bindings for later cleanup

        # Proxy connectors → bus
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

        # Launch all agent connectors (if supported)
        for agent in deployment.get("agents", []):
            adapter = AgentConnectionWrapper(agent, deployment)
            proto, host, port = adapter.proto, adapter.host, adapter.port

            connector_fn = CONNECTOR_MAP.get(proto, False)
            if connector_fn:
                args = {
                    "agent": agent,
                    "deployment": deployment,
                    "session_id": session_id
                }
                try:
                    channel_name = agent.get("universal_id")
                    ctx.channels[channel_name] = agent

                    connection_launcher.load(channel_name, connector_fn, context=args)
                    connection_launcher.launch(channel_name)

                except Exception as e:
                    emit_gui_exception_log(
                        f"[CONNECT][ERROR] Failed to launch {proto} connector for {agent.get('universal_id')}", e
                    )

        return ctx

    except Exception as e:
        emit_gui_exception_log("deployment_connector._connect_single", e)
        return {}