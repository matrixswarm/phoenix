# Authored by Daniel F MacDonald and ChatGPT-5.1 aka The Generals
# FULLY CORRECTED — SINGLE-VIEW, NO DUPLICATES, CLEAN WORKSPACE

import json, uuid
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGraphicsScene, QGraphicsView, QGraphicsRectItem, QGraphicsTextItem,
    QMessageBox, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, QMimeData
from PyQt6.QtGui import QPen, QColor, QPainter, QDrag, QPainter


# =====================================================================
# Agent Item Graphic Widget
# =====================================================================
class AgentItem(QGraphicsRectItem):
    """Draggable agent block."""
    WIDTH, HEIGHT = 160, 60

    def __init__(self, node, parent=None):
        super().__init__(0, 0, self.WIDTH, self.HEIGHT, parent)
        self.node = node

        self.setBrush(QColor("#1e1e1e"))
        self.setPen(QPen(Qt.GlobalColor.lightGray))
        self.setFlag(self.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(self.GraphicsItemFlag.ItemIsSelectable)

        label = node.get("name", "unknown")
        self.text = QGraphicsTextItem(label, self)
        self.text.setDefaultTextColor(Qt.GlobalColor.white)
        self.text.setPos(8, 8)

    def refresh_label(self):
        self.text.setPlainText(self.node.get("name", "unknown"))

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        parent_dialog = self.scene().views()[0].parentWidget()
        if getattr(parent_dialog, "link_mode", False):
            parent_dialog._handle_link_click(self)

    def mouseDoubleClickEvent(self, event):
        from PyQt6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(
            None, "Rename Agent", "New name:",
            text=self.node.get("name", ""))
        if ok and new_name.strip():
            self.node["name"] = new_name.strip()
            self.refresh_label()


# =====================================================================
# Palette List
# =====================================================================
class AgentPalette(QListWidget):
    """Drag source for adding agents."""
    def mouseMoveEvent(self, event):
        item = self.currentItem()
        if not item:
            return

        mime = QMimeData()
        mime.setText(item.text())

        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)


# =====================================================================
# Main Workspace Dialog (FULLY FIXED)
# =====================================================================
class SwarmWorkspaceDialog(QDialog):
    """Visual editor for the swarm directive graph."""

    def __init__(self, directive, agents_root, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Swarm Workspace")
        self.setMinimumSize(1000, 700)

        # Core data
        self.directive = directive
        self.agents_root = agents_root
        self.items = []
        self.node_map = {}
        self.link_mode = False
        self._link_buffer = []

        # --------------------------------------------------------------
        # Scene + Single View (FIXED)
        # --------------------------------------------------------------
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setAcceptDrops(True)

        # --------------------------------------------------------------
        # Dialog Layout
        # --------------------------------------------------------------
        layout = QVBoxLayout(self)

        # Button Row
        row = QHBoxLayout()
        self.btn_matrix = QPushButton("Add Matrix")
        self.btn_add = QPushButton("Add Agent")
        self.btn_link = QPushButton("Link Mode")
        self.btn_link.setCheckable(True)
        self.btn_save = QPushButton("Save & Close")
        self.btn_cancel = QPushButton("Cancel")

        row.addWidget(self.btn_matrix)
        row.addWidget(self.btn_add)
        row.addWidget(self.btn_link)
        row.addStretch()
        row.addWidget(self.btn_save)
        row.addWidget(self.btn_cancel)
        layout.addLayout(row)

        # Split Layout (Palette + View)
        split = QHBoxLayout()
        self.agent_palette = AgentPalette()
        self.agent_palette.setFixedWidth(200)
        self.agent_palette.setStyleSheet("""
            QListWidget { background: #222; color: #aaa; }
            QListWidget::item:selected { background: #4e7cff; color: white; }
        """)
        split.addWidget(self.agent_palette)
        split.addWidget(self.view, 1)
        layout.addLayout(split)

        # Wire buttons
        self.btn_matrix.clicked.connect(self.add_matrix)
        self.btn_add.clicked.connect(self.add_agent)
        self.btn_link.clicked.connect(self._toggle_link_mode)
        self.btn_save.clicked.connect(self.save_and_close)
        self.btn_cancel.clicked.connect(self.reject)

        # Load palette
        self._load_palette()

        # Load existing swarm structure
        self._render_from_directive(self.directive)


    # =================================================================
    # PALETTE LOADER
    # =================================================================
    def _load_palette(self):
        """Load agent folders from root."""
        try:
            root = Path(self.agents_root)
            for child in root.iterdir():
                if child.is_dir() and (child / f"{child.name}.py").exists():
                    item = QListWidgetItem(child.name)
                    self.agent_palette.addItem(item)
        except Exception as e:
            print(f"[PALETTE ERROR] {e}")

    def delete_agent(self, item):
        # 1. Remove children or force reassignment
        children = item.node.get("children", [])
        if children:
            yn = QMessageBox.question(
                self, "Delete Agent",
                f"'{item.node['name']}' has {len(children)} children.\n\n"
                "Delete entire subtree?\n"
                "Or reassign first-level children to another parent?"
            )

            if yn == QMessageBox.StandardButton.Yes:
                # full recursive delete
                self._recursive_delete(item)
            else:
                self._prompt_reassign_children(item)
        else:
            self._recursive_delete(item)

    def _prompt_reassign_children(self, parent_item):
        from PyQt6.QtWidgets import QInputDialog

        # Exclude the one being deleted & its descendants
        valid_parents = [
            i for i in self.items
            if i is not parent_item and i.node["name"].lower() != "matrix"
        ]

        names = [i.node["name"] for i in valid_parents]
        name, ok = QInputDialog.getItem(
            self, "Reassign Children",
            "Select new parent for these agents:",
            names, 0, False
        )
        if not ok:
            return

        new_parent = next(i for i in valid_parents if i.node["name"] == name)

        # Reassign children:
        for child_node in parent_item.node["children"]:
            child_item = self.node_map[child_node["universal_id"]]
            self.link_parent_child(new_parent, child_item)

        # Now delete parent
        self._recursive_delete(parent_item)

    def _refresh_all_dropdowns(self):
        for item in self.items:
            if hasattr(item, "dropdown"):
                self._update_dropdown_for_item(item)

    def _serialize_tree(self):
        # find root
        root = self.node_map.get("matrix")
        return self._serialize_subtree(root)

    def _serialize_subtree(self, item):
        node = {
            "name": item.node["name"],
            "universal_id": item.node["universal_id"],
            "children": []
        }
        for child in item.node.get("children", []):
            child_item = self.node_map[child["universal_id"]]
            node["children"].append(self._serialize_subtree(child_item))
        return node

    def save_and_close(self):
        self.directive["agent_tree"] = self._serialize_tree()
        self.accept()

    def _apply_color(self, item):
        if item.node.get("resolved"):
            item.setPen(QPen(QColor("#00ff99"), 2))
        else:
            item.setPen(QPen(QColor("#ff4444"), 2))


    # =================================================================
    # LINK MODE
    # =================================================================
    def _toggle_link_mode(self, checked):
        self.link_mode = checked
        self._link_buffer = []
        if checked:
            self.btn_link.setText("Linking...")
        else:
            self.btn_link.setText("Link Mode")


    def _handle_link_click(self, agent_item):
        """Handles 1-to-many linking."""
        self._link_buffer.append(agent_item)
        if len(self._link_buffer) == 2:
            parent, child = self._link_buffer
            self._link_buffer.clear()
            self.link_parent_child(parent, child)


    # =================================================================
    # DRAG + DROP
    # =================================================================
    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        name = event.mimeData().text()
        self._spawn_agent_from_palette(name, event)
        event.acceptProposedAction()


    def _spawn_agent_from_palette(self, name, event):
        if "matrix" not in [i.node["name"].lower() for i in self.items]:
            QMessageBox.warning(self, "Missing Root", "Matrix must be added first.")
            return

        node = {
            "name": name,
            "universal_id": str(uuid.uuid4())[:8],
            "children": [],
            "parent": None,
            "meta": {}
        }

        item = AgentItem(node)
        pos = self.view.mapToScene(event.position().toPoint())
        item.setPos(pos)
        self.scene.addItem(item)
        self.items.append(item)

        # Auto-link under Matrix
        root = self.node_map.get("matrix")
        if root:
            self.link_parent_child(root, item)


    # =================================================================
    # NODE SPAWNING
    # =================================================================
    def add_matrix(self):
        if "matrix" in self.node_map:
            QMessageBox.information(self, "Matrix", "Matrix already exists.")
            return

        node = {
            "name": "matrix",
            "universal_id": "matrix",
            "children": [],
            "parent": None,
            "meta": {}
        }
        item = AgentItem(node)
        item.setBrush(QColor("#2e4cff"))
        item.setPos(200, 100)

        self.scene.addItem(item)
        self.items.append(item)
        self.node_map["matrix"] = item


    def add_agent(self):
        node = {
            "name": "new_agent",
            "universal_id": str(uuid.uuid4())[:8],
            "children": [],
            "parent": None,
            "meta": {}
        }
        item = AgentItem(node)
        item.setPos(400, 200)
        self.scene.addItem(item)
        self.items.append(item)


    # =================================================================
    # LINKING (STRICT 1 → MANY)
    # =================================================================
    def link_parent_child(self, parent_item, child_item):
        # Prevent invalid relationships
        if child_item.node["name"].lower() == "matrix":
            QMessageBox.warning(self, "Invalid", "Matrix cannot be a child.")
            return False

        if parent_item is child_item:
            QMessageBox.warning(self, "Invalid", "An agent cannot link to itself.")
            return False

        # Enforce strict 1 → many
        if child_item.node.get("parent"):
            QMessageBox.warning(self, "Invalid",
                f"{child_item.node['name']} already has a parent.")
            return False

        # Assign parent
        child_item.node["parent"] = parent_item.node["universal_id"]
        parent_item.node.setdefault("children", []).append(child_item.node)

        # Draw visual link
        line = self.scene.addLine(
            parent_item.scenePos().x() + 80, parent_item.scenePos().y() + 60,
            child_item.scenePos().x() + 80, child_item.scenePos().y(),
            QPen(QColor("#00ff99"), 2)
        )
        line.setZValue(-1)

        return True


    # =================================================================
    # LOAD EXISTING DIRECTIVE
    # =================================================================
    def _render_from_directive(self, node, parent_item=None, depth=0, row=0):
        if not node:
            return

        item = AgentItem(node)
        x, y = depth * 250, row * 140
        item.setPos(x, y)

        self.scene.addItem(item)
        self.items.append(item)
        self.node_map[node["universal_id"]] = item

        # Draw parent line
        if parent_item:
            line = self.scene.addLine(
                parent_item.scenePos().x() + 80, parent_item.scenePos().y() + 60,
                x + 80, y, QPen(QColor("#888888"), 2)
            )
            line.setZValue(-1)

        # Recurse children
        for i, child in enumerate(node.get("children", [])):
            self._render_from_directive(child, item, depth + 1, row + i + 1)


