# Authored by Daniel F MacDonald and ChatGPT-5.1 aka The Generals
# Commander Edition — Railgun MatrixOS Installer
import os
import io
import zipfile
import tempfile
import requests
import paramiko
import time
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QLabel,
    QFileDialog, QComboBox, QLineEdit, QTextEdit, QCheckBox, QMessageBox
)
from matrix_gui.core.emit_gui_exception_log import emit_gui_exception_log

class RailgunInstallDialog(QDialog):
    """
    Full matrix installer:
    - Local folder bundling
    - GitHub release download
    - GitHub branch download
    - SSH select (vault)
    - Upload + run installer
    """

    def __init__(self, vault_data, parent=None):
        super().__init__(parent)
        self.vault_data = vault_data or {}
        self.setWindowTitle("⚡ Railgun — Install MatrixOS")
        self.resize(720, 560)

        self._zip_temp = None

        layout = QVBoxLayout(self)

        # =======================
        # SOURCE SELECTION
        # =======================
        src_box = QGridLayout()

        src_box.addWidget(QLabel("<b>Source:</b>"), 0, 0)

        self.src_selector = QComboBox()
        self.src_selector.addItems([
            "Use Local MatrixOS Folder",
            #"Download From GitHub (Stable Release)",
            "Download From GitHub (Dev Branch: main)",
            #"Download From GitHub (Custom Branch)"
        ])
        src_box.addWidget(self.src_selector, 0, 1)

        # Local folder picker
        self.local_path_edit = QLineEdit()
        self.local_path_edit.setPlaceholderText("Select local MatrixOS root…")
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_local_repo)

        src_box.addWidget(self.local_path_edit, 1, 0, 1, 1)
        src_box.addWidget(browse_btn, 1, 1)

        # Custom branch
        self.branch_edit = QLineEdit()
        self.branch_edit.setPlaceholderText("custom-branch-name")
        src_box.addWidget(QLabel("Custom Branch:"), 2, 0)
        src_box.addWidget(self.branch_edit, 2, 1)

        layout.addLayout(src_box)

        # =======================
        # SSH TARGET
        # =======================
        ssh_box = QHBoxLayout()
        ssh_box.addWidget(QLabel("<b>SSH Target:</b>"))
        self.ssh_selector = QComboBox()

        ssh_map = (self.vault_data.get("connection_manager") or {}).get("ssh", {})
        for sid, meta in ssh_map.items():
            label = meta.get("label", sid)
            self.ssh_selector.addItem(f"{label} ({meta.get('host')})", meta)

        ssh_box.addWidget(self.ssh_selector)
        layout.addLayout(ssh_box)

        # =======================
        # INSTALL PATH + OPTIONS
        # =======================
        path_box = QGridLayout()
        self.install_path_edit = QLineEdit("/matrix")
        path_box.addWidget(QLabel("<b>Install Path:</b>"), 0, 0)
        path_box.addWidget(self.install_path_edit, 0, 1)

        self.chk_overwrite = QCheckBox("Overwrite existing installation")
        path_box.addWidget(self.chk_overwrite, 1, 0, 1, 2)

        layout.addLayout(path_box)

        # =======================
        # ACTION BUTTON
        # =======================
        run_btn = QPushButton("⚡ Install MatrixOS")
        run_btn.setStyleSheet("background:#222; color:#0f0; font-weight:bold;")
        run_btn.clicked.connect(self._run_install)
        layout.addWidget(run_btn)

        # =======================
        # OUTPUT
        # =======================
        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        self.output_box.setStyleSheet(
            "background:#000; color:#00ff00; font-family:Consolas,monospace; font-size:12px;"
        )
        layout.addWidget(self.output_box)

    # -------------------------------------------------------------
    # BROWSE LOCAL
    # -------------------------------------------------------------
    def _browse_local_repo(self):
        folder = QFileDialog.getExistingDirectory(self, "Select MatrixOS Root Folder")
        if folder:
            self.local_path_edit.setText(folder)

    # -------------------------------------------------------------
    # ZIP LOCAL MATRIXOS FOLDER
    # -------------------------------------------------------------
    def _zip_local_repo(self, path):
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
            zf = zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED)

            root = Path(path)

            allowed_dirs = {"agents", "core", "scripts"}
            allowed_files = {
                "requirements.txt",
                "requirements.swarm.txt",
                "README.md",
                "pyproject.toml"
            }

            for item in root.iterdir():
                name = item.name

                # include only approved directories
                if item.is_dir() and name in allowed_dirs:
                    for p in item.rglob("*"):
                        arc = p.relative_to(root)
                        zf.write(p, arc)

                # include allowed files
                elif item.is_file() and name in allowed_files:
                    zf.write(item, item.name)

            zf.close()
            return tmp.name

        except Exception as e:
            emit_gui_exception_log("RailgunInstall._zip_local_repo", e)
            return None

    # -------------------------------------------------------------
    # DOWNLOAD GITHUB RELEASE OR BRANCH
    # -------------------------------------------------------------
    def _download_github(self):
        try:
            import zipfile
            import shutil

            mode = self.src_selector.currentText()

            if "Stable Release" in mode:
                url = "https://github.com/matrixswarm/matrixos/archive/refs/tags/latest.zip"
            elif "Dev Branch" in mode:
                url = "https://github.com/matrixswarm/matrixos/archive/refs/heads/main.zip"
            else:
                branch = self.branch_edit.text().strip()
                if not branch:
                    QMessageBox.warning(self, "Missing Branch", "Enter a branch name.")
                    return None
                url = f"https://github.com/matrixswarm/matrixos/archive/refs/heads/{branch}.zip"

            # 1) Download ZIP
            tmp_zip = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            tmp_zip.write(r.content)
            tmp_zip.close()

            # 2) Extract into temp dir
            extract_dir = Path(tempfile.mkdtemp(prefix="matrixos_zip_"))
            with zipfile.ZipFile(tmp_zip.name, "r") as z:
                z.extractall(extract_dir)

            # 3) Detect top-level folder
            subdirs = [p for p in extract_dir.iterdir() if p.is_dir()]
            if len(subdirs) != 1:
                QMessageBox.critical(None, "GitHub ZIP Error",
                                     "Could not determine top-level directory in GitHub ZIP.")
                return None

            top = subdirs[0]

            # 4) Build clean manifest structure
            clean_dir = Path(tempfile.mkdtemp(prefix="matrixos_clean_"))

            needed_dirs = ["agents", "core", "scripts"]
            needed_files = ["requirements.txt", "requirements.swarm.txt", "pyproject.toml", "README.md"]

            for d in needed_dirs:
                src = top / d
                if src.exists():
                    shutil.copytree(src, clean_dir / d)

            for f in needed_files:
                src = top / f
                if src.exists():
                    shutil.copy(src, clean_dir / f)

            # 5) Zip the cleaned manifest
            out_zip = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
            with zipfile.ZipFile(out_zip.name, "w", zipfile.ZIP_DEFLATED) as z:
                for item in clean_dir.rglob("*"):
                    arc = item.relative_to(clean_dir)
                    z.write(item, arc)

            return out_zip.name

        except Exception as e:
            emit_gui_exception_log("RailgunInstall._download_github", e)
            return None

    # -------------------------------------------------------------
    # RUN INSTALL
    # -------------------------------------------------------------
    def _run_install(self):
        try:
            # resolve source zip
            mode = self.src_selector.currentText()
            if "Local" in mode:
                if not self.local_path_edit.text().strip():
                    QMessageBox.warning(self, "Missing Path", "Select a local MatrixOS folder.")
                    return
                src_zip = self._zip_local_repo(self.local_path_edit.text().strip())

            else:
                src_zip = self._download_github()

            if not src_zip:
                QMessageBox.critical(self, "No Source", "Failed to prepare MatrixOS source.")
                return

            self._zip_temp = src_zip
            self.output_box.append("[Railgun] Source bundle ready.")

            # SSH meta from vault
            ssh_cfg = self.ssh_selector.currentData()
            if not ssh_cfg:
                QMessageBox.critical(self, "SSH Missing", "No SSH target in vault.")
                return

            host = ssh_cfg.get("host")
            user = ssh_cfg.get("username")
            port = int(ssh_cfg.get("port", 22))
            privkey_pem = ssh_cfg.get("private_key")

            # path settings
            install_path = self.install_path_edit.text().strip()
            overwrite = self.chk_overwrite.isChecked()

            self.output_box.append(f"[Railgun] Target: {host}")
            self.output_box.append(f"[Railgun] Install Path: {install_path}")
            if overwrite:
                self.output_box.append("[Railgun] Overwrite enabled.")

            # Start SSH session
            key = paramiko.RSAKey.from_private_key(io.StringIO(privkey_pem))
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(host, port=port, username=user, pkey=key)
            sftp = client.open_sftp()

            # Upload zip
            remote_zip = f"/tmp/matrixos_{os.path.basename(src_zip)}"
            sftp.put(src_zip, remote_zip)
            sftp.close()
            self.output_box.append("[Railgun] Uploaded source bundle.")

            # Upload installer script
            installer = self._generate_installer_script(install_path, overwrite, remote_zip)
            remote_installer = "/tmp/install_matrixos.sh"

            sftp = client.open_sftp()
            with sftp.open(remote_installer, "w") as f:
                f.write(installer)
            sftp.chmod(remote_installer, 0o755)
            sftp.close()
            self.output_box.append("[Railgun] Installer uploaded.")

            # Execute install
            cmd = f"bash {remote_installer}"
            self.output_box.append(f"[Railgun] Running installer…\n")

            transport = client.get_transport()
            channel = transport.open_session()
            channel.get_pty(term="xterm")
            channel.set_combine_stderr(True)
            channel.exec_command(cmd)

            buf = ""
            while True:
                if channel.recv_ready():
                    chunk = channel.recv(4096).decode(errors="ignore")
                    buf += chunk

                    # split on newline to make it feel alive
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        self.output_box.append(line)
                        self.output_box.ensureCursorVisible()
                        self.output_box.repaint()

                if channel.exit_status_ready():
                    # flush any remaining partial line
                    if buf.strip():
                        self.output_box.append(buf.strip())
                    break

                time.sleep(0.05)



            exit_code = channel.recv_exit_status()
            self.output_box.append(f"\n[Railgun] Install finished (exit={exit_code})")

            client.close()

        except Exception as e:
            emit_gui_exception_log("RailgunInstall.run_install", e)
            QMessageBox.critical(self, "Railgun Error", str(e))

    # -------------------------------------------------------------
    # INSTALL SCRIPT (OS-neutral)
    # -------------------------------------------------------------
    def _generate_installer_script(self, install_path, overwrite, remote_zip):
        script = f"""#!/bin/bash
        set -e

        echo "[Installer] Starting MatrixOS installation…"

        if [ ! -d "{install_path}" ]; then
            mkdir -p {install_path}
        fi
        
        echo "[Installer] Preparing directories…"
        
        {"echo '[Installer] Removing old install…' && rm -rf " + install_path + "/*" if overwrite else ""}
        mkdir -p {install_path}/boot_directives
        mkdir -p {install_path}/boot_directives/keys
        chown -R root:root {install_path}/boot_directives
        chmod 700 {install_path}/boot_directives/keys

        echo "[Installer] Unpacking source bundle…"
        unzip -o {remote_zip} -d {install_path}

        # Flatten GitHub-style directory wrapper (matrixos-main/, matrixos-branchname/, etc.)
        top_dir=$(find {install_path} -maxdepth 1 -type d -name "matrixos-*")
        if [ -n "$top_dir" ]; then
            echo "[Installer] Flattening GitHub directory structure…"
            mv "$top_dir"/* {install_path}/
            rmdir "$top_dir"
        fi

        echo "[Installer] Checking Python…"
        if ! command -v python3 >/dev/null 2>&1; then
            if [ -f /etc/redhat-release ]; then
                yum install -y python3 python3-pip
            else
                apt update && apt install -y python3 python3-pip python3-venv
            fi
        fi

        echo "[Installer] Creating virtual environment…"
        python3 -m venv {install_path}/venv
        source {install_path}/venv/bin/activate

        echo "[Installer] Installing requirements…"
        pip install --upgrade pip
        pip install -r {install_path}/requirements.txt || true

        # matrixd symlink
        echo "[Installer] Linking matrixd globally…"
        ln -sf {install_path}/scripts/matrixd /usr/local/bin/matrixd
        chmod +x /usr/local/bin/matrixd

        echo "[Installer] MatrixOS install complete."
        """
        return script
