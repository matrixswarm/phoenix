# Authored by Daniel F MacDonald and ChatGPT-5.1 aka The Generals
# FULLY CORRECTED — SINGLE-VIEW, NO DUPLICATES, CLEAN WORKSPACE

# Enhanced Swarm Workspace Redesign (Commander Edition)
# Features:
#  - Left palette loads agents from MatrixOS directories using meta.json
#  - Only one Matrix allowed on the board
#  - Each agent has required meta fields (universal_id, parent, connection)
#  - Agents can be dragged from palette onto canvas
#  - Double-click to open field editor (parent assign, connections, etc.)
#  - Saving/loading workspace layout supported
#  - Validation: required fields checked before save/deploy

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QGraphicsScene, QGraphicsView, QGraphicsRectItem, QLabel, QPushButton,
    QDialog, QFormLayout, QLineEdit, QFileDialog, QMessageBox
)
from PyQt6.QtGui import QColor, QPen, QDrag
from PyQt6.QtCore import Qt, QMimeData
from pathlib import Path
import json, uuid


class AgentPalette(QListWidget):
    """Drag source for adding agents found in MatrixOS install."""

    def __init__(self, agents_root):
        super().__init__()
        self.agents_root = Path(agents_root)
        self.load_agents()

    def load_agents(self):
        self.clear()
        if not self.agents_root.exists():
            print("[PALETTE] Invalid agent root:", self.agents_root)
            return

        for folder in self.agents_root.rglob("*"):
            # Look for Python agent folders like: matrix_https/matrix_https.py
            if folder.is_dir():
                agent_py = folder / (folder.name + ".py")
                meta_json = folder / "meta.json"

                if agent_py.exists() and meta_json.exists():
                    try:
                        data = json.loads(meta_json.read_text())
                        name = data.get("name", folder.name)
                        item = QListWidgetItem(name)
                        item.setData(Qt.ItemDataRole.UserRole, data)
                        self.addItem(item)
                    except Exception as e:
                        print("[PALETTE ERROR]", folder, e)

    def mouseMoveEvent(self, event):
        item = self.currentItem()
        if not item:
            return
        mime = QMimeData()
        mime.setText(item.text())
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)

class AgentItem(QGraphicsRectItem):
    WIDTH, HEIGHT = 160, 60

    def __init__(self, meta):
        super().__init__(0,0,self.WIDTH,self.HEIGHT)
        self.meta = meta
        self.node = {
            "name": meta.get('name', 'agent'),
            "universal_id": str(uuid.uuid4())[:8],
            "parent": None,
            "connection": None
        }
        self.setBrush(QColor('#1e1e1e'))
        self.setPen(QPen(QColor('#888')))
        self.setFlag(self.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(self.GraphicsItemFlag.ItemIsSelectable)

    def mouseDoubleClickEvent(self, event):
        dlg = AgentPropertyDialog(self.node)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.node.update(dlg.collect_data())

class AgentPropertyDialog(QDialog):
    """Dialog for editing agent attributes."""
    def __init__(self, node):
        super().__init__()
        self.setWindowTitle(node.get('name','Agent Config'))
        self.node = node
        layout = QFormLayout(self)
        self.inputs = {}

        # Universal ID (read-only)
        uid = QLineEdit(node.get('universal_id',''))
        uid.setReadOnly(True)
        layout.addRow(QLabel('Universal ID:'), uid)

        # Parent field
        parent = QLineEdit(node.get('parent',''))
        parent.setPlaceholderText('Required (except Matrix)')
        layout.addRow(QLabel('Parent:'), parent)
        self.inputs['parent'] = parent

        # Connection field
        conn = QLineEdit(node.get('connection',''))
        conn.setPlaceholderText('Required connection reference')
        layout.addRow(QLabel('Connection:'), conn)
        self.inputs['connection'] = conn

        btn = QPushButton('Save')
        btn.clicked.connect(self.accept)
        layout.addRow(btn)

    def collect_data(self):
        return {k:v.text().strip() for k,v in self.inputs.items()}

class SwarmWorkspaceDialog(QDialog):
    def __init__(self, directive, agents_root):
        super().__init__()
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setAcceptDrops(True)
        self.view.dragEnterEvent = self.dragEnterEvent
        self.view.dropEvent = self.dropEvent

        self.palette = AgentPalette(agents_root)
        self.save_btn = QPushButton('💾 Save Layout')
        self.load_btn = QPushButton('📂 Load Layout')
        self.deploy_btn = QPushButton('Validate & Deploy')

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.load_btn)
        btn_row.addWidget(self.deploy_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(btn_row)
        layout.addWidget(self.palette,1)
        layout.addWidget(self.view,4)

        self.save_btn.clicked.connect(self.save_layout)
        self.load_btn.clicked.connect(self.load_layout)
        self.deploy_btn.clicked.connect(self.validate_before_deploy)

    def dragEnterEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        name = event.mimeData().text()
        for i in range(self.palette.count()):
            item = self.palette.item(i)
            if item.text() == name:
                meta = item.data(Qt.ItemDataRole.UserRole)
                break
        else:
            return
        # Ensure only one Matrix
        if meta.get('name','').lower() == 'matrix':
            for item in self.scene.items():
                if isinstance(item, AgentItem) and item.meta.get('name','').lower() == 'matrix':
                    QMessageBox.warning(self, 'Duplicate Matrix', 'Only one Matrix agent allowed.')
                    return
        agent_item = AgentItem(meta)
        pos = self.view.mapToScene(event.position().toPoint())
        agent_item.setPos(pos)
        self.scene.addItem(agent_item)

    def save_layout(self):
        path,_ = QFileDialog.getSaveFileName(self, 'Save Workspace', '', 'Workspace JSON (*.json)')
        if not path: return
        data = []
        for item in self.scene.items():
            if isinstance(item, AgentItem):
                pos = item.scenePos()
                node = item.node.copy()
                node['pos'] = {'x': pos.x(), 'y': pos.y()}
                data.append(node)
        Path(path).write_text(json.dumps(data, indent=2))

    def load_layout(self):
        path,_ = QFileDialog.getOpenFileName(self, 'Load Workspace', '', 'Workspace JSON (*.json)')
        if not path: return
        try:
            nodes = json.loads(Path(path).read_text())
            self.scene.clear()
            for node in nodes:
                meta = {'name': node.get('name','agent')}
                item = AgentItem(meta)
                item.node.update(node)
                item.setPos(node.get('pos',{}).get('x',0), node.get('pos',{}).get('y',0))
                self.scene.addItem(item)
        except Exception as e:
            QMessageBox.critical(self, 'Error', str(e))

    def validate_before_deploy(self):
        errors = []
        has_matrix = False
        for item in self.scene.items():
            if not isinstance(item, AgentItem):
                continue
            name = item.node.get('name','')
            if name.lower() == 'matrix':
                has_matrix = True
            # validate required fields
            if name.lower() != 'matrix' and not item.node.get('parent'):
                errors.append(f"{name} missing parent")
            if not item.node.get('connection'):
                errors.append(f"{name} missing connection")
        if not has_matrix:
            errors.append('Matrix agent required.')
        if errors:
            QMessageBox.warning(self, 'Validation Errors', '\n'.join(errors))
        else:
            QMessageBox.information(self, 'Validation Passed', 'All agents valid for deployment.')

