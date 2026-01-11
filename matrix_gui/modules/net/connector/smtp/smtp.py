#!/usr/bin/env python3
# Commander & ChatGPT — Victory Always Edition
# EMAIL CONNECTOR — Outbound Phoenix → IMAP Swarm Ingress

import smtplib, ssl, json, base64, uuid, time
from email.message import EmailMessage
from matrix_gui.core.class_lib.packet_delivery.utility.security.packet_security import wrap_packet_securely
from matrix_gui.modules.net.connector.interfaces.connector_base import BaseConnector
from matrix_gui.config.boot.globals import get_sessions
from matrix_gui.core.emit_gui_exception_log import emit_gui_exception_log
from matrix_gui.core.class_lib.packet_delivery.packet.standard.command.packet import Packet

class SMTPConnector(BaseConnector):
    """
    EMAIL CONNECTOR (Outbound)
    --------------------------
    Sends Phoenix → Swarm packets via SMTP to the IMAP inbox
    monitored by matrix_email ingress agent.

    Transport Packet:
        {
            "payload_b64": "<base64 of Phoenix outer wrapper>",
            "meta": {
                "ts": <timestamp>,
                "uuid": "<message-id>"
            }
        }

    The payload_b64 decodes to the secured, encrypted Phoenix wrapper.
    """

    def __init__(self):
        super().__init__(None, None, None)

        self.proto = "smtp"

        self.smtp_host = None
        self.smtp_port = None
        self.smtp_user = None
        self.smtp_pass = None
        self.to_addr    = None
        self.session_id = None
        self.agent      = None
        self.deployment = None

    def __call__(self, agent, deployment, session_id, timeout=10):
        """
        Initialize connector on deployment attach.
        """
        self.ctx = get_sessions().get(session_id)
        if not self.ctx:
            print(f"[EmailConnector][{agent.get('universal_id')}] ❌ No session context.")
            return

        conn = agent.get("connection", {})
        if not conn:
            print(f"[SMTPConnector][__call__] no connection dict provided")
            return

        host = conn.get("smtp_server", False)
        port = conn.get("smtp_port", False)
        username = conn.get("smtp_username", False)
        password = conn.get("smtp_password", False)
        smtp_to = conn.get("smtp_to", False)
        encryption = conn.get("smtp_encryption", False)

        if not port or not host:
            print(f"[SMTPConnector][__call__] host and port not provided")
            return

        # SMTP config
        self.smtp_host = host
        self.smtp_port = int(port)
        self.smtp_user = username
        self.smtp_pass = password
        self.to_addr   = smtp_to
        self.encryption = encryption

        self.agent      = agent
        self.deployment = deployment
        self.session_id = session_id

        if not (self.smtp_host and self.smtp_user and self.smtp_pass and self.to_addr):
            print("[EmailConnector] ❌ Missing SMTP config in deployment.")
            return

        self.proto = "smtp"
        channel_name = f"smtp-{session_id[:6]}-{uuid.uuid4().hex[:6]}"

        self.ctx.channels[channel_name] = self
        self.ctx.status[channel_name] = "ready"
        self._set_channel_name(channel_name)
        self._set_status("connected")

        print(f"[EmailConnector] Registered → {channel_name}")

        return self

    def send(self, packet:Packet, timeout=10):
        """
        Wrap Phoenix payload, base64 encode, send via SMTP.
        """
        try:

            if not (self.smtp_host and self.smtp_user and self.smtp_pass and self.to_addr):
                print("[EmailConnector] ❌ Missing SMTP config in deployment.")
                return

            uid = self.agent.get("universal_id") if self.agent else "unknown"
            print(f"[EmailConnector][{uid}] 🎯 Attempting send → {self.smtp_host}:{self.smtp_user}")

            inner={}
            self._set_status("connecting")
            content = packet.get_packet()
            inner['matrix_packet']=content
            inner["ts"] = int(time.time())
            inner["session_id"] = self.session_id

            #encrypt & sign inner packet
            envelope = wrap_packet_securely(
                inner,
                deployment=self.deployment,
                sign=True,
                encrypt=True,
                target_uid=self.agent.get("universal_id")
            )

            packet = envelope.get_packet()
            body = json.dumps(packet, separators=(",", ":")).encode()

            # Wrap it for an email's body
            body = base64.b64encode(body).decode("utf-8")

            msg = EmailMessage()
            msg["From"] = self.smtp_user
            msg["To"]   = self.to_addr
            msg["Subject"] = f"Phoenix → Swarm Packet ({self.agent.get('universal_id')})"
            msg.set_content(body)

            print(f"Connecting to {self.smtp_host}:{self.smtp_port} with SSL encryption.")
            if self.ctx and hasattr(self.ctx, "bus"):
                self.ctx.bus.emit("channel.packet.sent", start_end=1)

            try:
                with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=timeout) as server:
                    server.starttls(context=ssl._create_unverified_context())
                    server.login(self.smtp_user, self.smtp_pass)
                    server.send_message(msg)
                print(f"[EmailConnector] 📧 Sent packet to {self.to_addr}")
            except smtplib.SMTPException as e:
                print(f"Failed to send email: {e}")
            finally:
                if self.ctx and hasattr(self.ctx, "bus"):
                    self.ctx.bus.emit("channel.packet.sent", start_end=0)

        except Exception as e:
            emit_gui_exception_log("EmailConnector.send", e)
            print(f"[EmailConnector] ❌ Send error: {e}")

    def close(self, session_id=None, channel_name=None):
        """
        Email connector has no persistent state to close.
        """
        self._set_status("disconnected")
        print(f"[EmailConnector] Session closed {session_id}/{channel_name}")
