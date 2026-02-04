from abc import ABC, abstractmethod
import time
from matrix_gui.core.class_lib.packet_delivery.packet.standard.command.packet import Packet
from matrix_gui.core.emit_gui_exception_log import emit_gui_exception_log
from matrix_gui.core.connector_bus import ConnectorBus

class BaseConnector(ABC):
    """
    Standard interface for all connectors (HTTPS, WSS, SMTP, etc).

    Persistent connectors (like WSS) run continuous loops and self-manage.
    Ephemeral connectors (like HTTPS/SMTP) perform a single mission and exit.

    Subclasses should override:
      - run_once()   → for single-shot tasks
      - run_loop()   → for persistent sockets or repeating tasks
      - send() / close()   → core communication methods
    """

    persistent = False  # default mode: single-shot
    run_on_launch = True  # compatible with ConnectionLauncher

    def __init__(self, shared=None):
        """
        Initialize shared state and default attributes.

        Args:
            shared (dict, optional): Shared context dict between threads,
                containing keys like 'session_id', 'agent', 'deployment'.
                If None, an empty dict will be created.
        """
        try:
            shared = shared or {}
            self.session_id = shared.get("session_id")
            self.agent = shared.get("agent")
            self.deployment = shared.get("deployment")
            self._shared = shared

            self._closed = False
            self._status = "disconnected"
            self._channel_name = None
            self._mission = None
            self._stop_flag = False

            # optional hooks for telemetry
            self._shared.setdefault("last_heartbeat", time.time())
        except Exception as e:
            emit_gui_exception_log("BaseConnector.__init__()", e)

    # ------------------------------------------------------------------
    # Abstracts for communication primitives
    # ------------------------------------------------------------------
    @abstractmethod
    def send(self, packet: Packet, timeout=10):
        """
        Send a payload through this connector.

        Args:
            packet (Packet): The packet to transmit.
            timeout (int): Seconds to wait for send completion.
        """
        pass

    @abstractmethod
    def close(self, session_id: str = None, channel_name: str = None):
        """
        Close down the connector cleanly (terminate sockets, threads, etc).

        Args:
            session_id (str, optional): Identifier for the session to close.
            channel_name (str, optional): Name of the communication channel.
        """
        pass

    # ------------------------------------------------------------------
    # Lifecycle management
    # ------------------------------------------------------------------
    def stop(self):
        """
        Signal the connector's thread to stop gracefully.
        Sets internal stop flags and updates status.
        """
        self._stop_flag = True
        if self._shared:
            self._shared["stop"] = True
        self._set_status("stopping")

    def stopped(self) -> bool:
        """
        Returns True if stop() was requested, False otherwise.

        Returns:
            bool: Whether a stop has been requested.
        """
        return self._stop_flag or (self._shared and self._shared.get("stop"))

    def heartbeat(self):
        """
        Update last heartbeat timestamp in shared state.
        Use this to indicate the connector is still alive.
        """
        if self._shared:
            self._shared["last_heartbeat"] = time.time()

    def reboot_now(self):
        """
        Signals to connection_launcher's auto monitor to reboot the this thread now
        """
        if self._shared:
            self._shared["reboot_now"] = True

    # ------------------------------------------------------------------
    # Unified run logic
    # ------------------------------------------------------------------
    def run(self):
        """
        Entry point executed by ConnectionLauncher threads.

        Chooses run_once() or run_loop() based on self.persistent flag,
        sets status accordingly, and ensures cleanup on exit.
        """
        try:

            if self.persistent:
                self.run_loop()
            else:
                self.run_once()

        except Exception as e:
            emit_gui_exception_log(f"{self.__class__.__name__}.run()", e)
        finally:
            # allow graceful cleanup
            try:
                self.close(self.session_id, self._channel_name)
            except Exception:
                pass

        print(f"{self.__class__.__name__}.run(): thread exiting cleanly.")

    # ------------------------------------------------------------------
    # Template methods for subclasses to override
    # ------------------------------------------------------------------
    def run_once(self):
        """
        Single-mission behavior. Override for HTTPS/SMTP connectors.

        Raises:
            NotImplementedError: If not implemented by subclass.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement run_once()")

    def run_loop(self):
        """
        Persistent socket or repeating task behavior. Override for WSS connectors.
        By default, loops calling loop_tick() until stopped.
        """
        continue_loop=True
        while not self.stopped() and continue_loop:
            try:
                continue_loop=self.loop_tick()
                if(continue_loop):
                    self.heartbeat()
                    time.sleep(1)

            except Exception as e:
                continue_loop=False
                emit_gui_exception_log(f"{self.__class__.__name__}.loop_tick()", e)
                time.sleep(1)

    def loop_tick(self):
        """
        Optional sub-loop tick method for persistent connectors.

        Raises:
            NotImplementedError: If subclass is persistent but does not implement this.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement loop_tick() if persistent")

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------
    def get_status(self) -> str:
        """
        Get the current status of the connector.

        Returns:
            str: One of 'disconnected', 'running', 'stopping', 'stopped', or 'error'.
        """
        return self._status

    def get_channel_name(self) -> str:
        """
        Get the name of the communication channel in use.

        Returns:
            str: Channel identifier, or None if unset.
        """
        return self._channel_name

    def _set_status(self, status: str):
        """
        Internally update the connector's status.

        Args:
            status (str): New status value.
        """
        self._status = status

    def _set_channel_name(self, name: str):
        """
        Internally update the connector's channel name.

        Args:
            name (str): New channel name.
        """
        self._channel_name = name

    def _emit_status(self, status, host=None, port=None):
        """
        Emit a channel.status event and update internal status.

        Args:
            status (str): New status string ('connected', 'disconnected', etc).
            host (str, optional): Hostname for context in the event.
            port (int, optional): Port number for context in the event.
        """

        ConnectorBus.get(self.session_id).emit(
            "channel.status",
            session_id=self.session_id,
            channel=self.agent.get("universal_id"),
            status=status,
            info={"host": host, "port": port} if host else {},
        )
        self._set_status(status)
