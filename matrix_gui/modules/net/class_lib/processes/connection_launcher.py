# Authored by Daniel F MacDonald and ChatGPT-5 aka The Generals
import importlib
import threading

import time
import uuid
from matrix_gui.core.emit_gui_exception_log import emit_gui_exception_log
class ConnectionLauncher:
    """
    ConnectionLauncher — Swarm Thread Orchestrator
    ------------------------------------------
    • Dynamically loads classes
    • Executes them as managed threads
    • Supports ephemeral and persistent workers
    • Centralized logging via BootAgent.log
    """

    def __init__(self):
        """
        Initialize the ConnectionLauncher with empty registries and lock.

        Attributes:
            _threads (dict): Maps thread_id → threading.Thread instance.
            _registry (dict): Maps universal_id → metadata dict for each connector.
            _shared_state (dict): Maps universal_id → shared context dict.
            _lock (threading.Lock): Ensures thread-safe registry updates.
        """
        self._threads = {}        # thread_id -> Thread
        self._registry = {}       # thread_id -> metadata
        self._shared_state = {}   # thread_id -> shared dict
        self._lock = threading.Lock()

        print("ConnectionLauncher initialized")

    # --------------------------------------------------
    def load(self, universal_id, class_path, context=None, check_interval=30):
        """
        Register a connector class under a universal identifier.

        Args:
            universal_id (str): Unique key to refer to this connector.
            class_path (str): Dotted path to the connector class.
            context (dict, optional): Initial context passed into connector instances.
            check_interval (int, optional): Heartbeat check interval in seconds.

        Returns:
            ConnectionLauncher: Self for fluent chaining.
        """
        context = context or {}

        with self._lock:
            self._registry[universal_id] = {
                "universal_id": universal_id,
                "class_path": class_path,
                "context": context,
                "persist": True,  # persistent by definition
                "check_interval": check_interval,
                "thread_id": None,
            }

            self._shared_state[universal_id] = {
                "universal_id": universal_id,
                "thread_id": None,
                "class_path": class_path,
                "context": context,
                "started_at": None,
                "last_heartbeat": None,
                "stop": False,
                "reboot_now": False #a way for the thread to signal to reboot itself
            }

        #print(f"[ConnectionLauncher][LOAD] Registered {class_path} as {universal_id}")
        return self

    def launch(self, universal_id, packet:dict=None, fire_catapult=False):
        """
        Instantiate and start the connector as a daemon thread.

        Args:
            universal_id (str): Identifier under which the class was loaded.
            packet (dict, optional): Initial packet data to inject into context.
            fire_catapult (bool, optional): Force immediate launch even if run_on_launch=False.

        Returns:
            threading.Thread | None: The thread object if launched, else None.
        """
        try:
            with self._lock:
                meta = self._registry.get(universal_id)
                if not meta:
                    print(f"[LAUNCH][ERROR] No such universal_id {universal_id}")
                    return None

                class_path = meta["class_path"]
                context = meta["context"]
                thread_id = uuid.uuid4().hex

                shared = self._shared_state[universal_id]
                shared["thread_id"] = thread_id
                shared["started_at"] = time.time()
                shared["last_heartbeat"] = time.time()
                shared["reboot_now"] = False
                shared["stop"] = False

            cls = self._load_class(class_path)
            persist = getattr(cls, "persistent", False)
            run_on_launch = getattr(cls, "run_on_launch", False)

            with self._lock:
                self._registry[universal_id]["persist"] = persist

            t=None
            if fire_catapult or run_on_launch:
                # Update the shared dict (never replace it)
                shared.update({
                    "session_id": context.get("session_id"),
                    "agent": context.get("agent"),
                    "deployment": context.get("deployment"),
                    "context": context,
                    "packet": packet,
                })

                instance = cls(shared=shared)

                t = threading.Thread(
                    target=instance.run,
                    name=f"thread:{class_path}",
                    daemon=True,
                )
                if persist:
                    with self._lock:
                        meta["thread_id"] = thread_id
                        self._threads[thread_id] = t

                t.start()

                print(f"[ConnectionLauncher][LAUNCH] Started {universal_id} as thread {thread_id}")

            return t

        except Exception as e:
            emit_gui_exception_log("ConnectionLauncher.launch()", e)

    # --------------------------------------------------
    def kill_thread(self, universal_id: str):
        """
        Terminate and clean up a managed thread.

        Args:
            universal_id (str): registry key to locate the thread to kill.
        """
        with self._lock:

            thread_id = self._registry.get(universal_id,{}).get("thread_id", False)
            if not thread_id:
                print(f"[NUKER] No active thread_id to nuke using {universal_id}.")
                return

            t = self._threads.get(thread_id, False)
            if not t or not isinstance(t, threading.Thread):
                print(f"[NUKER] No active thread {thread_id} to nuke.")
                return

            print(f"[NUKER] Nuking thread {thread_id}")
            try:
                if t.is_alive():
                    # Try to stop gracefully if possible
                    shared = self._shared_state.get(universal_id)
                    if shared:
                        shared["stop"] = True
                    # force cleanup
                    t.join(timeout=1)
            except Exception as e:
                print(f"[NUKER][WARN] Exception during kill: {e}")
            finally:
                self._threads.pop(thread_id, None)

   # --------------------------------------------------
    def start_auto_monitor(self, check_interval: int = 10):
        """
        Starts an internal background monitor thread that keeps
        all persistent threads alive. Auto-relaunches any that
        die or stop heartbeating.
        """
        if hasattr(self, "_monitor_thread") and self._monitor_thread.is_alive():
            return  # already running

        def _monitor_loop():
            print("[ConnectionLauncher][MONITOR] Auto-monitor active.")
            while True:
                try:
                    now = time.time()
                    restarts = []

                    with self._lock:
                        for uid, meta in self._registry.items():
                            tid = meta["thread_id"]
                            t = self._threads.get(tid)
                            shared = self._shared_state.get(uid)
                            alive = t.is_alive() if t else False

                            # restart conditions:
                            if not alive and bool(meta['persist']) and not bool(shared["stop"]):
                                restarts.append(uid)
                            elif bool(meta['persist']) and bool(shared["reboot_now"]): #thread wants to get rebooted if true
                                restarts.append(uid)
                            elif bool(meta['persist']) and not bool(shared["stop"]):
                                hb = shared.get("last_heartbeat", 0)
                                if now - hb > meta["check_interval"] * 2:
                                    print("heatbeat failure")
                                    restarts.append(uid)

                    for uid in restarts:
                        print(f"[MONITOR] Restarting {uid}")
                        self.kill_thread(uid)
                        self.launch(uid)

                    time.sleep(10)

                except Exception as e:
                    emit_gui_exception_log("ConnectionLauncher.auto_monitor()", e)
                    time.sleep(check_interval)

        self._monitor_thread = threading.Thread(target=_monitor_loop, name="thread_launcher_monitor", daemon=True)
        self._monitor_thread.start()

    # --------------------------------------------------
    def stop_uid(self, universal_id):
        with self._lock:
            meta = self._registry.get(universal_id)
            if not meta:
                print(f"[STOP] No such universal_id {universal_id}")
                return False

            # retrieve the thread_id
            tid = meta.get("thread_id")
            if not tid:
                print(f"[STOP] No thread for {universal_id}")
                return False

            # mark the shared stop flag
            shared = self._shared_state.get(universal_id)
            if shared:
                shared["stop"] = True

            print(f"[STOP] Signal sent to {universal_id} → thread {tid}")
            return True

    # --------------------------------------------------
    def _load_class(self, dotted_path: str):
        """
        Dynamically import and return a class by its dotted module path.

        Args:
            dotted_path (str): Module and class name, e.g. 'module.sub.ClassName'.

        Returns:
            type: The class object referenced by dotted_path.

        Raises:
            Exception: Propagates any error during import or attribute lookup.
        """
        try:

            module_path, class_name = dotted_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)

            return cls

        except Exception as e:
            emit_gui_exception_log("ConnectionLauncher._load_class()", e)
            raise

    # --------------------------------------------------
    def destroy_all(self, force=False):
        """
        Destroy all active connections and threads managed by the launcher.

        Args:
            force (bool, optional): If True, forcibly clears registries even if
                threads fail to exit gracefully.

        Behavior:
            1. Signals all threads to stop via shared state.
            2. Attempts graceful join on each thread.
            3. Force-cleans thread registry and state maps.
            4. Stops the monitor loop if running.
        """
        try:
            print("[ConnectionLauncher][DESTROY] Commencing full shutdown sequence...")
            with self._lock:
                # signal stop
                for tid, shared in list(self._shared_state.items()):
                    if shared:
                        shared["stop"] = True

                threads = list(self._threads.items())

            # attempt graceful join
            for tid, t in threads:
                if t.is_alive():
                    print(f"[DESTROY] Waiting for thread {tid} to stop...")
                    t.join(timeout=2)

            # final cleanup
            with self._lock:
                self._threads.clear()
                self._registry.clear()
                self._shared_state.clear()

            # stop monitor loop if any
            if hasattr(self, "_monitor_thread") and self._monitor_thread.is_alive():
                print("[DESTROY] Stopping monitor thread...")
                self._monitor_thread = None  # daemon thread will exit on its own

            print("[ConnectionLauncher][DESTROY] ✅ All connections destroyed.")
        except Exception as e:
            if not force:
                emit_gui_exception_log("ConnectionLauncher.destroy_all()", e)
            else:
                # fallback: hard purge everything
                self._threads.clear()
                self._registry.clear()
                self._shared_state.clear()
                self._monitor_thread = None
                print("[ConnectionLauncher][DESTROY][FORCE] ⚠️ Forced purge completed.")


