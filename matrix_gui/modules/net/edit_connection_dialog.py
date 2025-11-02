# Authored by Daniel F MacDonald and ChatGPT-5 aka The Generals
from PyQt6.QtWidgets import QDialog, QFormLayout, QLineEdit, QRadioButton, QButtonGroup, QComboBox, QCheckBox, QDialogButtonBox, QMessageBox, QWidget
import uuid
import ipaddress
from matrix_gui.core.emit_gui_exception_log import emit_gui_exception_log

def edit_connection_dialog(parent, default_proto="https", data=None, conn_id=None):
    dlg = QDialog(parent)
    dlg.setWindowTitle("Edit Connection")
    dlg.setMinimumWidth(520)

    layout = QFormLayout(dlg)
    fields = {}

    type_selector = QComboBox()
    type_selector.addItems(["https", "wss", "discord", "telegram", "openai", "email", "slack"])
    layout.addRow("Connection Type", type_selector)

    pre_proto = (data or {}).get("proto", default_proto)
    idx = type_selector.findText(pre_proto)
    if idx >= 0:
        type_selector.setCurrentIndex(idx)

    field_container = QWidget()
    field_layout = QFormLayout(field_container)
    layout.addRow(field_container)

    def clear_fields():
        while field_layout.count():
            item = field_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        fields.clear()

    def add_field(name, default=""):
        box = QLineEdit()
        if data:
            val = data.get(name, default)
            if name == "allowlist_ips" and isinstance(val, list):
                val = ", ".join(val)
            box.setText(str(val))
        else:
            box.setText(str(default))
        if name == "serial":
            box.setReadOnly(True)
        field_layout.addRow(name.replace("_", " ").title(), box)
        fields[name] = box

    def update_fields_for_type():
        clear_fields()
        p = type_selector.currentText()
        add_field("label")

        if p == "email":
            # Radio row
            mode = (data or {}).get("type", "outgoing")
            type_group = QButtonGroup(dlg)
            radio_out = QRadioButton("Outgoing (SMTP)")
            radio_in = QRadioButton("Incoming (IMAP/POP3)")
            type_group.addButton(radio_out)
            type_group.addButton(radio_in)
            if mode == "incoming":
                radio_in.setChecked(True)
            else:
                radio_out.setChecked(True)

            radio_row = QWidget()
            radio_row_layout = QFormLayout(radio_row)
            radio_row_layout.addRow(radio_out, radio_in)
            field_layout.addRow(radio_row)
            fields["email_type"] = type_group

            # Dedicated email subcontainer
            email_field_container = QWidget()
            email_field_layout = QFormLayout(email_field_container)
            field_layout.addRow(email_field_container)

            # Helper widgets (we will create and store them explicitly so toggling reuses objects)
            smtp_server = QLineEdit()
            smtp_port = QLineEdit()
            smtp_encryption = QComboBox()
            smtp_encryption.addItems(["SSL", "STARTTLS", "None", "Auto"])
            smtp_username = QLineEdit()
            smtp_password = QLineEdit()
            smtp_password.setEchoMode(QLineEdit.EchoMode.Password)

            incoming_protocol = QComboBox()
            incoming_protocol.addItems(["IMAP", "POP3"])
            incoming_server = QLineEdit()
            incoming_port = QLineEdit()
            incoming_encryption = QComboBox()
            incoming_encryption.addItems(["SSL", "STARTTLS", "None", "Auto"])
            incoming_username = QLineEdit()
            incoming_password = QLineEdit()
            incoming_password.setEchoMode(QLineEdit.EchoMode.Password)
            leave_copy_cb = QCheckBox()

            # prefill from data if present
            if data:
                smtp_server.setText(str(data.get("smtp_server", "")))
                smtp_port.setText(str(data.get("smtp_port", "")))
                smtp_encryption.setCurrentText(str(data.get("smtp_encryption", "Auto")))
                smtp_username.setText(str(data.get("smtp_username", "")))
                smtp_password.setText(str(data.get("smtp_password", "")))

                incoming_protocol.setCurrentText(str(data.get("protocol", "IMAP")))
                incoming_server.setText(str(data.get("incoming_server", "")))
                incoming_port.setText(str(data.get("incoming_port", "")))
                incoming_encryption.setCurrentText(str(data.get("incoming_encryption", "Auto")))
                incoming_username.setText(str(data.get("incoming_username", "")))
                incoming_password.setText(str(data.get("incoming_password", "")))
                leave_copy_cb.setChecked(bool(data.get("leave_copy", False)))

            # functions to set sensible default ports when encryption selection changes
            def set_smtp_defaults(enc: str):
                enc = enc.upper()
                if not smtp_port.text().strip():
                    if enc == "SSL":
                        smtp_port.setText("465")
                    elif enc == "STARTTLS":
                        smtp_port.setText("587")
                    else:
                        smtp_port.setText("25")

            def set_incoming_defaults(enc: str, proto: str):
                enc = enc.upper()
                proto = proto.upper()
                if not incoming_port.text().strip():
                    if proto == "IMAP":
                        if enc == "SSL":
                            incoming_port.setText("993")
                        elif enc == "STARTTLS":
                            incoming_port.setText("143")
                        else:
                            incoming_port.setText("143")
                    else:  # POP3
                        if enc == "SSL":
                            incoming_port.setText("995")
                        elif enc == "STARTTLS":
                            incoming_port.setText("110")
                        else:
                            incoming_port.setText("110")

            # render function that clears email sublayout and re-adds the right widgets
            def render_email_fields():
                # clear only the email sublayout
                while email_field_layout.count():
                    item = email_field_layout.takeAt(0)
                    w = item.widget()
                    if w:
                        w.setParent(None)
                # add shared/default row: default channel
                channel_box = QComboBox()
                channel_box.addItems(["alerts"])
                prev_default = (data or {}).get("default_channel")
                if prev_default:
                    idxc = channel_box.findText(prev_default)
                    if idxc >= 0:
                        channel_box.setCurrentIndex(idxc)
                email_field_layout.addRow("Default Channel Role", channel_box)
                fields["default_channel"] = channel_box

                # serial row
                serial_val = str((data or {}).get("serial") or uuid.uuid4().hex[:8])
                serial_box = QLineEdit()
                serial_box.setText(serial_val)
                serial_box.setReadOnly(True)
                email_field_layout.addRow("Serial", serial_box)
                fields["serial"] = serial_box

                # Now the mode-specific fields
                if radio_out.isChecked():
                    email_field_layout.addRow("Smtp Server", smtp_server)
                    email_field_layout.addRow("Smtp Port", smtp_port)
                    email_field_layout.addRow("Smtp Encryption", smtp_encryption)
                    email_field_layout.addRow("Smtp Username", smtp_username)
                    email_field_layout.addRow("Smtp Password", smtp_password)

                    # wire encryption default behavior
                    smtp_encryption.currentTextChanged.connect(lambda t: set_smtp_defaults(t))
                    # initial defaults
                    set_smtp_defaults(smtp_encryption.currentText())

                    # populate fields dict
                    fields["smtp_server"] = smtp_server
                    fields["smtp_port"] = smtp_port
                    fields["smtp_encryption"] = smtp_encryption
                    fields["smtp_username"] = smtp_username
                    fields["smtp_password"] = smtp_password

                else:
                    # incoming mode
                    email_field_layout.addRow("Protocol", incoming_protocol)
                    email_field_layout.addRow("Incoming Server", incoming_server)
                    email_field_layout.addRow("Incoming Port", incoming_port)
                    email_field_layout.addRow("Incoming Encryption", incoming_encryption)
                    email_field_layout.addRow("Incoming Username", incoming_username)
                    email_field_layout.addRow("Incoming Password", incoming_password)
                    email_field_layout.addRow("Leave Copy", leave_copy_cb)

                    # wire default population
                    incoming_encryption.currentTextChanged.connect(lambda t: set_incoming_defaults(t, incoming_protocol.currentText()))
                    incoming_protocol.currentTextChanged.connect(lambda p: set_incoming_defaults(incoming_encryption.currentText(), p))
                    set_incoming_defaults(incoming_encryption.currentText(), incoming_protocol.currentText())

                    fields["protocol"] = incoming_protocol
                    fields["incoming_server"] = incoming_server
                    fields["incoming_port"] = incoming_port
                    fields["incoming_encryption"] = incoming_encryption
                    fields["incoming_username"] = incoming_username
                    fields["incoming_password"] = incoming_password
                    fields["leave_copy"] = leave_copy_cb

            # connect toggles and render initial
            radio_out.toggled.connect(render_email_fields)
            radio_in.toggled.connect(render_email_fields)
            render_email_fields()

        elif p in ("https", "wss"):
            add_field("host")
            add_field("port")
            add_field("purpose")
            add_field("note")
            add_field("allowlist_ips")
        elif p == "discord":
            add_field("channel_id")
            add_field("bot_token")
            add_field("note")
        elif p == "telegram":
            add_field("chat_id")
            add_field("bot_token")
            add_field("note")
        elif p == "openai":
            add_field("api_key")
            add_field("note")
        elif p == "slack":
            add_field("webhook_url")
            add_field("note")

        # channel/default role
        channel_roles = {
            "https": ["outgoing.command"],
            "wss": ["payload.reception"],
            "discord": ["alerts"],
            "telegram": ["alerts"],
            "openai": ["oracle"],
            "email": ["alerts"],
            "slack": ["alerts"]
        }

        # only add if not email (email handled inside its container)
        if p != "email":
            channel_box = QComboBox()
            channel_box.addItems(channel_roles.get(p, ["outgoing.command"]))
            prev_default = (data or {}).get("default_channel")
            if prev_default:
                idx = channel_box.findText(prev_default)
                if idx >= 0:
                    channel_box.setCurrentIndex(idx)
            field_layout.addRow("Default Channel Role", channel_box)
            fields["default_channel"] = channel_box

            serial = str((data or {}).get("serial") or uuid.uuid4().hex[:8])
            add_field("serial", default=serial)

    def validate_and_return():
        p = type_selector.currentText()
        result = {"proto": p}
        required_fields = ["label"]

        if p == "email":
            # determine email subtype
            btn = fields.get("email_type")
            if btn and btn.checkedButton():
                etype = "outgoing" if btn.checkedButton().text().startswith("Outgoing") else "incoming"
            else:
                etype = (data or {}).get("type", "outgoing")
            result["type"] = etype
            if etype == "outgoing":
                required_fields += ["smtp_server", "smtp_port", "smtp_username", "smtp_password"]
            else:
                required_fields += ["incoming_server", "incoming_port", "incoming_username", "incoming_password"]
        elif p in ("https", "wss"):
            required_fields += ["host", "port"]
        elif p == "discord":
            required_fields += ["channel_id"]
        elif p == "telegram":
            required_fields += ["chat_id"]
        elif p == "slack":
            required_fields += ["webhook_url"]

        for key in required_fields:
            widget = fields.get(key)
            if not widget:
                QMessageBox.warning(dlg, "Missing Field", f"'{key.replace('_', ' ').title()}' is required.")
                return None, None
            # QCheckBox doesn't have text()
            if isinstance(widget, QCheckBox):
                val_ok = True
            else:
                if isinstance(widget, QComboBox):
                    txt = widget.currentText()
                else:
                    txt = widget.text()
                if not str(txt).strip():
                    QMessageBox.warning(dlg, "Missing Field", f"'{key.replace('_', ' ').title()}' is required.")
                    return None, None

        for k, widget in fields.items():

            if isinstance(widget, QButtonGroup):
                # skip radio group, already handled via 'etype'
                continue
            elif isinstance(widget, QComboBox):
                result[k] = widget.currentText()
            elif isinstance(widget, QCheckBox):
                result[k] = widget.isChecked()
            else:
                val = widget.text().strip()
                if val:
                    if k in ("port", "smtp_port", "incoming_port", "channel_id", "chat_id"):
                        try:
                            result[k] = int(val)
                        except ValueError:
                            QMessageBox.warning(dlg, "Invalid Input", f"{k} must be numeric.")
                            return None, None
                    elif k == "allowlist_ips":
                        ips = [x.strip() for x in val.split(",") if x.strip()]
                        for ip in ips:
                            try:
                                ipaddress.ip_address(ip)
                            except ValueError:
                                QMessageBox.warning(dlg, "Invalid IP", f"'{ip}' is not a valid IP address.")
                                return None, None
                        result[k] = ips
                    else:
                        result[k] = val

        new_id = conn_id or f"conn_{result['proto']}_{result.get('label','unnamed').lower().replace(' ', '_')}"
        return new_id, result

    def on_accept():
        out = validate_and_return()
        if not out or out == (None, None):
            return
        new_id, result = out
        dlg._return_id = new_id
        dlg._return_data = result
        dlg.accept()


    try:

        type_selector.currentTextChanged.connect(update_fields_for_type)


        update_fields_for_type()

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addRow(btns)
        btns.accepted.connect(on_accept)
        btns.rejected.connect(dlg.reject)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None, None

        return dlg._return_id, dlg._return_data

    except Exception as e:
        emit_gui_exception_log("edit_connection_dialog", e)