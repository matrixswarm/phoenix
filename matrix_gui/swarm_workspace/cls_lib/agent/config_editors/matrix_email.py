# Commander & ChatGPT – Victory Always Edition
# MATRIX EMAIL Config Editor (Minimalist)
# Focused on: poll_interval, msg_retrieval_limit, process_packets

from PyQt6.QtWidgets import (
    QWidget, QLabel, QFormLayout, QSpinBox, QCheckBox
)
from .base_editor import BaseEditor
from .mixin.service_roles_mixin import ServiceRolesMixin


class MatrixEmail(BaseEditor, ServiceRolesMixin):

    def _build_form(self):
        cfg = self.config

        # ---------------------------------------------
        # GENERAL SETTINGS
        # ---------------------------------------------
        general_box = QWidget()
        gl = QFormLayout(general_box)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.setSpacing(4)

        # Poll interval (seconds)
        self.poll_interval = QSpinBox()
        self.poll_interval.setRange(5, 3600)
        self.poll_interval.setValue(int(cfg.get("poll_interval", 20)))
        gl.addRow("Poll Interval (sec):", self.poll_interval)

        # Message retrieval limit
        self.msg_limit = QSpinBox()
        self.msg_limit.setRange(1, 500)
        self.msg_limit.setValue(int(cfg.get("msg_retrieval_limit", 10)))
        gl.addRow("Message Retrieval Limit:", self.msg_limit)

        # Process packets toggle
        self.proc_packets = QCheckBox("Process Incoming Packets")
        self.proc_packets.setChecked(bool(cfg.get("process_packets", True)))
        gl.addRow(self.proc_packets)

        # Add section to layout
        self.layout.addRow(QLabel("📧 Matrix Email Settings"))
        self.layout.addRow(general_box)

        # ---------------------------------------------
        # SERVICE MANAGER ROLES
        # ---------------------------------------------
        self.layout.addRow(QLabel("🔗 Service Manager Roles"))
        self._build_roles_section(cfg, default_role="matrix_email.status@cmd_list_status")

    # ---------------------------------------------
    # SAVE CONFIG
    # ---------------------------------------------
    def _save(self):
        roles = self._collect_roles()

        self.node.config.update({
            "poll_interval": int(self.poll_interval.value()),
            "msg_retrieval_limit": int(self.msg_limit.value()),
            "process_packets": self.proc_packets.isChecked(),
            "service-manager": [{"role": roles}],
        })

        self.node.mark_dirty()
        self.accept()
