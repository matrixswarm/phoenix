# Authored by Daniel F MacDonald and ChatGPT-5 aka The Generals
import os
import io
import json
import hashlib
import uuid
import base64
import paramiko
import ntpath
import posixpath
from datetime import datetime
from copy import deepcopy
from PyQt6 import QtWidgets

from PyQt6.QtWidgets import (
    QMessageBox, QDialog
)
from pathlib import Path
from PyQt6.QtWidgets import QInputDialog
from matrix_gui.modules.vault.crypto.deploy_tools import generate_swarm_encrypted_directive
from matrix_gui.modules.directive.encryption_staging_dialog import EncryptionStagingDialog
from matrix_gui.modules.directive.ui.deployment_dialog import DeploymentDialog
from matrix_gui.modules.directive.deploy_options_dialog import DeployOptionsDialog
from matrix_gui.core.event_bus import EventBus
from matrix_gui.core.emit_gui_exception_log import emit_gui_exception_log
from .agent_root_validator import AgentRootValidator
from matrix_gui.modules.vault.crypto.cert_utils import embed_agent_sources
from matrix_gui.modules.vault.crypto.deploy_tools import write_encrypted_bundle_to_file
from matrix_gui.modules.vault.services.vault_core_singleton import VaultCoreSingleton

class Deploy():

    def deploy_directive(self, parent_dialog, directive_staging, deployment_staging, workspace_id):
        try:

            vcs = VaultCoreSingleton.get()

            # step 2. Generate deployment ID and label
            deployment_id = f"{uuid.uuid4().hex[:16]}"

            label, ok = QInputDialog.getText(None, "Deployment Label", "Provide a friendly deployment label:")
            if not ok or not label.strip():
                return


            # FOR RAILGUN SUPPORT
            ssh_map = None
            reg = vcs.get_store("registry")

            # Get all SSH registry objects
            ssh_namespace = reg.get_namespace("ssh") or {}

            ssh_map = deepcopy(ssh_namespace)

            # step 6. Options Dialog (Clown Car, Hashbang)
            opts_dialog = DeployOptionsDialog(ssh_map, label, parent=parent_dialog)
            if opts_dialog.exec() != QDialog.DialogCode.Accepted:
                QMessageBox.information(None, "Cancelled", "Deployment process cancelled by operator.")
                return
            opts = opts_dialog.get_options()

            # --- step 7. Agent source embedding (Clown Car) ---
            """
            Handles the "Clown Car" step in the deployment process by verifying and managing the agent source directory
            used in the directive staging process. Supports caching and verifying agent paths, loading or validating from 
            the vault, and ensuring necessary files are available for deployment.
    
            Steps:
            1. **Check 'Clown Car' Option:**
               - Determines if the "Clown Car" mode is enabled based on the `opts["clown_car"]` flag.
               - Affects how the directive is processed and staged.
    
            2. **Verify Agent Path:**
               - If the "Clown Car" mode is enabled, attempts to load the last cached agent path from the vault.
               - Verifies if the cached path exists and contains all required sources for the directive.
    
            3. **Cache Validation:**
               - If the cached path is invalid or missing necessary files, opens a verification dialog (`AgentRootCheckDialog`) 
                 for the user to select and verify the correct agent source directory.
               - Caches the newly verified path in `self.vault_data` for future deployments.
    
            4. **Generate Encrypted Directive:**
               - Calls `generate_swarm_encrypted_directive` to bundle the directive data along with encryption, 
                 integrating the verified agent path if applicable.
    
    
            Functions/Methods:
                AgentRootSelector.resolve_agents_root(agent_path): Resolves the root directory of the agent sources.
                AgentRootSelector.verify_all_sources(directive_staging, agents_root): Verifies all required agent sources 
                    exist for the directive staging at the specified root.
                generate_swarm_encrypted_directive(directive_staging, clown_car, hashbang, base_path): Generates an encrypted 
                    directive based on the provided staging data and configuration.
    
            Classes/Dialogs:
                AgentRootCheckDialog: Handles user interaction for verifying and selecting the agent root directory, 
                if no valid cached path exists.
    
            """
            clown_car = bool(opts.get("clown_car", False))
            hashbang = clown_car

            if clown_car:
                cached_path = vcs.data.get("last_agent_path")
                validator = AgentRootValidator(directive_staging, cached_path)
                verified_path = validator.run()

                if not verified_path:
                    # User tapped out — abort deployment
                    print("[CLOWN-CAR][ABORT] User cancelled agent validation.")
                    return

                agent_path = verified_path
            else:
                agent_path = None

            try:

                bundle, aes_key, directive_hash = generate_swarm_encrypted_directive(directive_staging['agents'], clown_car=clown_car, hashbang=hashbang, base_path=agent_path)

            except Exception as e:

                print(f"[CLOWN-CAR][ABORT] Missing agent sources detected. Deployment halted. {e}")
                QMessageBox.critical(None, f"Deployment Aborted {e}",
                                     "One or more agent sources could not be located.\n"
                                     "Check console output for details.")
                return


            swarm_key_mem = base64.b64encode(aes_key).decode()

            # step 8. Preview the newly minted directive (only once)
            staging_dialog = EncryptionStagingDialog(json.dumps(directive_staging['agents'], indent=2))
            if staging_dialog.exec() != QDialog.DialogCode.Accepted:
                QMessageBox.information(None, "Cancelled", "Directive encryption cancelled by operator.")
                return

            # step 9. Choose save location (default under /deploy/)
            cwd = Path.cwd()  # This is your working directory (repo root if you launch Phoenix there)
            deploy_dir = cwd / "boot_directives"
            deploy_dir.mkdir(parents=True, exist_ok=True)

            keys_dir = deploy_dir / "keys"
            keys_dir.mkdir(parents=True, exist_ok=True)

            universe = f"{label.strip()}"

            universe_temp = opts.get("universe", False)
            railgun_enabled = bool(opts.get("railgun_enabled", False))
            if universe_temp and railgun_enabled:
                universe = universe_temp.strip()

            out_path = deploy_dir / f"{universe}.enc.json"
            key_path = keys_dir / f"{universe}.key"

            # Directive path
            write_encrypted_bundle_to_file(bundle, out_path)

            # Swarm key path
            if not bool(opts.get("railgun_enabled", False)):
                # Only save to disk if Railgun is NOT used
                print(f"[DEPLOY] Writing swarm key to {key_path}")
                with open(key_path, "w", encoding="utf-8") as f:
                    f.write(base64.b64encode(aes_key).decode())
                os.chmod(key_path, 0o600)
            else:
                print("[DEPLOY] Railgun active — swarm key held in memory only.")

            # step 10. Update deployment record in the vault with encryption details
            with open(out_path, "rb") as f:
                encrypted_hash = hashlib.sha256(f.read()).hexdigest()

            deployment_record = {
                "label": label,
                "workspace_id": workspace_id,
                "deployed_at": datetime.now().isoformat(),
                "swarm_key": swarm_key_mem,
                "encrypted_path": str(out_path),
                "encrypted_hash": encrypted_hash,
                "agents": deployment_staging.deployment["agents"],
                "certs": deployment_staging.deployment["certs"],
            }

            # Persist in vault (single write; CRUD is trivial now)
            vcs = VaultCoreSingleton.get()
            deployments = vcs.data.setdefault("deployments", {})
            deployments[deployment_id] = deployment_record
            vcs.patch("deployments", deployments)
            #self.refresh_lists()

            # === Optional Rail-Gun Fire ===
            if bool(opts.get("railgun_enabled", False)):
                ssh_cfg = opts.get("railgun_target", None)
                if ssh_cfg:
                    # pass the key directly
                    self._railgun_upload_and_boot(parent_dialog, ssh_cfg, out_path, swarm_key_mem, opts)
            else:
                # step 11. Show final deploy command to operator
                deploy_cmd = f"""
                🚀 Your directive has been encrypted and saved.
    
                Directive: {out_path}
                Swarm Key: /matrix/boot_directives/keys/{universe}.key
    
                ⚠️ Secure your swarm key:
                    chmod 600 /matrix/boot_directives/keys/{universe}.key
    
                To deploy from command line, use:
    
                    matrixd boot --universe {universe}
    
                Matrix will automatically resolve the encrypted directive and swarm key.
                """
                DeploymentDialog(deploy_cmd).exec()

        except Exception as e:
            print(f"Failed directive creation: {e}")
            QMessageBox.critical(None, "Error", f"Deployment error alert:\n{e}")

        # -------------------------------------------------


    def _railgun_upload_and_boot(self, parent_dialog, ssh_meta, local_bundle, swarm_key_b64, opts):
        """Upload directive, inject swarm key via env var, stream live deploy output."""
        try:

            host = ssh_meta.get("host")
            user = ssh_meta.get("username")
            port = int(ssh_meta.get("port", 22))
            privkey_pem = ssh_meta.get("private_key")

            try:

                # === Railgun Live Deploy Popup ===
                dlg = QtWidgets.QDialog(parent_dialog)
                dlg.setWindowTitle(f"Railgun Deploy: {host}")
                dlg.resize(800, 500)

                layout = QtWidgets.QVBoxLayout(dlg)
                output_box = QtWidgets.QTextEdit()
                output_box.setReadOnly(True)
                output_box.setStyleSheet(
                    "background:#000; color:#00ff00; font-family: Consolas, monospace; font-size:12px;"
                )
                layout.addWidget(output_box)

                dlg.show()
                QtWidgets.QApplication.processEvents()
                output_box.append("[RAILGUN] 🔴 LIVE DEPLOY STREAM 🔴")
            except Exception as e:
                QMessageBox.critical(None, "Railgun Deploy Popup", str(e))
                print(f"[RAILGUN][ERROR] Railgun Deploy Popup Error: {e}")

            key = paramiko.RSAKey.from_private_key(io.StringIO(privkey_pem))
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(host, port=port, username=user, pkey=key)
            sftp = client.open_sftp()

            remote_root = "/matrix/boot_directives"
            if not self._remote_exists(sftp, remote_root):
                sftp.mkdir(remote_root)

            remote_bundle = posixpath.join(remote_root, ntpath.basename(local_bundle))
            sftp.put(local_bundle, remote_bundle)
            sftp.close()

            universe = opts.get("universe")
            boot_flags = []
            if opts.get("reboot"): boot_flags.append("--reboot")
            if opts.get("verbose"): boot_flags.append("--verbose")
            if opts.get("debug"): boot_flags.append("--debug")
            if opts.get("rug_pull"): boot_flags.append("--rug-pull")
            if opts.get("clean"): boot_flags.append("--clean")
            if opts.get("reboot_new"): boot_flags.append("--reboot-new")
            if opts.get("reboot_id"): boot_flags.append(f"--reboot-id {opts['reboot_id']}")
            boot_flags_str = " ".join(boot_flags)

            # Safe inline export – invisible to ps
            swarm_key = swarm_key_b64.strip()
            cmd = (
                f"cd /matrix && "
                f"export SITE_ROOT=/matrix && "
                f"export SWARM_KEY='{swarm_key}' && "
                f"[ -d /matrix/venv ] && source /matrix/venv/bin/activate || echo '[RAILGUN] No venv detected' && "
                f"(matrixd boot --universe {universe} --directive {remote_bundle} {boot_flags_str}) "
                f"2>&1 | tee /matrix/railgun_deploy.log"
            )

            print(f"[RAILGUN] Executing remote deploy on {host}...")

            # Create a live PTY channel for real-time output
            transport = client.get_transport()
            channel = transport.open_session()
            channel.get_pty()
            channel.exec_command(cmd)

            QtWidgets.QApplication.processEvents()
            while True:
                if channel.recv_ready():

                    chunk = channel.recv(4096).decode(errors="ignore")
                    try:
                        output_box.append(chunk)
                    except Exception as e:
                        pass

                    QtWidgets.QApplication.processEvents()
                if channel.recv_stderr_ready():

                    try:
                        err = channel.recv_stderr(4096).decode(errors="ignore")
                        output_box.append(f"<span style='color:red'>{err}</span>")
                    except Exception as e:
                        pass

                    QtWidgets.QApplication.processEvents()
                if channel.exit_status_ready():
                    break

            exit_code = channel.recv_exit_status()
            output_box.append(f"\n[RAILGUN] Deploy finished (exit={exit_code})")
            QtWidgets.QApplication.processEvents()

        except Exception as e:
            QMessageBox.critical(None, "Railgun Failed", str(e))
            print(f"[RAILGUN][ERROR] {e}")
        finally:
            try:
                client.close()
                dlg.exec()  # keep window open until closed
            except Exception as e:
                pass


    def _remote_exists(self, sftp, path):
        try:
            sftp.stat(path)
            return True
        except FileNotFoundError:
            return False

