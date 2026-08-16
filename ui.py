"""
USD Assembler - Main Window + Actions
"""
import os
import sys
import shutil
from pathlib import Path

try:
    from PyQt6.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
        QListWidget, QListWidgetItem, QPushButton, QMessageBox, QDialog, QFrame
    )
    from PyQt6.QtCore import Qt, QSize
    from PyQt6.QtGui import QPixmap, QIcon
    USING_PYQT6 = True
except ImportError:
    from PySide6.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
        QListWidget, QListWidgetItem, QPushButton, QMessageBox, QDialog, QFrame
    )
    from PySide6.QtCore import Qt, QSize
    from PySide6.QtGui import QPixmap, QIcon
    USING_PYQT6 = False

from scanner import ProjectManager, AssetScanner, ASSEMBLY_TASKS, assembly_filename
from widgets import DropdownSelector, AddAssemblyDialog, LinkAssetDialog
from usda_io import write_sublayer_usda

_USER_ROLE = Qt.ItemDataRole.UserRole if USING_PYQT6 else Qt.UserRole
_NO_SELECT = Qt.ItemFlag.ItemIsSelectable if USING_PYQT6 else Qt.ItemIsSelectable
_GREEN_DOT = '<span style="color: #3ddc84;">&#9679;</span>'

LABEL_W = 70
DROP_W  = 160

_BTN = """
    QPushButton {
        background-color:transparent; color:#888888;
        border:none; border-bottom:2px solid transparent;
        padding:0px 20px; font-size:12px; font-weight:normal;
    }
    QPushButton:checked        { color:#e0e0e0; border-bottom:2px solid #867a68; font-weight:bold; }
    QPushButton:hover:!checked { color:#bbbbbb; border-bottom:2px solid #555555; }
    QPushButton:disabled       { color:#555555; }
"""
_SMALL_BTN = """
    QPushButton {
        background-color:#4a4a4a; color:#cccccc;
        border:1px solid #2a2a2a; padding:6px; font-size:11px;
    }
    QPushButton:hover    { background-color:#555555; }
    QPushButton:pressed  { background-color:#3a3a3a; }
    QPushButton:disabled { background-color:#353535; color:#555555; border:1px solid #252525; }
"""
_PUBLISH_BTN = """
    QPushButton {
        background-color:#867a68; color:#fff;
        border:1px solid #867a68; padding:6px;
        font-size:11px; font-weight:bold;
    }
    QPushButton:hover    { background-color:#a2947d; border:1px solid #a2947d; }
    QPushButton:pressed  { background-color:#7b7061; border:1px solid #7b7061; }
    QPushButton:disabled { background-color:#4a4040; color:#666060; border:1px solid #3a3030; }
"""
_LIST = """
    QListWidget {
        border:1px solid #2a2a2a; background-color:#282828;
        outline:none;
        font-size:11px; color:#cccccc;
    }
    QListWidget::item                { padding:0px; border-bottom:1px solid #333333; }
    QListWidget::item:selected       { background-color:#867a68; color:#fff; }
    QListWidget::item:selected:hover { background-color:#867a68; color:#fff; }
    QListWidget::item:hover          { background-color:#404040; }
"""
_LABEL_STYLE = "font-weight:bold; font-size:11px; color:#aaaaaa;"


class USDAssembler(QMainWindow):

    def __init__(self):
        super().__init__()
        self.project_path          = None
        self.scanner               = None
        self.current_mode          = "asset"
        self.current_category      = None
        self.current_sequence      = None
        self.current_asset         = None
        self.current_shot          = None
        self.current_previz        = None
        self.current_task          = None
        self.current_assembly      = None
        self.linked_files          = []
        self.shot_linked_assets    = []
        self.assemblies            = []

        self.setWindowTitle("USD Assembler 1.0")
        self.setGeometry(100, 100, 980, 700)
        self.setMinimumSize(880, 600)
        self._setup_ui()
        self._initialize_project()

    # ── State helpers ─────────────────────────────────────────────────────────

    @property
    def _mode(self):
        return self.current_mode

    @property
    def _entity(self):
        if self._mode == 'asset':  return self.current_asset
        if self._mode == 'shot':   return self.current_shot
        return self.current_previz

    def _set_entity(self, name):
        if self._mode == 'asset':  self.current_asset  = name
        elif self._mode == 'shot': self.current_shot   = name
        else:                      self.current_previz = name

    def _clear_entity(self):
        self.current_asset = self.current_shot = self.current_previz = None

    def _norm_project_path(self):
        p = os.environ.get('PIPELINE_PROJECT_PATH', str(self.project_path))
        p = p.replace('\\', '/')
        if p.startswith('/mnt/') and len(p.split('/')) > 3:
            drive = p.split('/')[2].upper()
            p = f"{drive}:/" + "/".join(p.split('/')[3:])
        return p

    # ── UI helpers ────────────────────────────────────────────────────────────

    def _lbl(self, text):
        w = QLabel(text)
        w.setStyleSheet(_LABEL_STYLE)
        w.setFixedWidth(LABEL_W)
        return w

    def _selector_row(self, label_text, selector, extra=None):
        row = QHBoxLayout()
        row.setSpacing(20)
        row.addWidget(self._lbl(label_text))
        row.addWidget(selector)
        if extra:
            row.addWidget(extra)
        row.addStretch()
        return row

    def _selector_widget(self, label_text, selector):
        w   = QWidget()
        lay = self._selector_row(label_text, selector)
        lay.setContentsMargins(0, 0, 0, 0)
        w.setLayout(lay)
        return w

    def _mode_btn(self, label, slot):
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setFixedHeight(36)
        btn.setStyleSheet(_BTN)
        btn.clicked.connect(slot)
        return btn

    def _no_select_item(self, text=""):
        item = QListWidgetItem(text)
        item.setFlags(item.flags() & ~_NO_SELECT)
        return item

    def _rich_item(self, display_text, file_info=None, selectable=True):
        html = f"<nobr>{display_text}</nobr>"
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 24))
        if file_info:
            item.setData(_USER_ROLE, file_info)
        if not selectable:
            item.setFlags(item.flags() & ~_NO_SELECT)
        lbl = QLabel()
        lbl.setTextFormat(Qt.TextFormat.RichText if USING_PYQT6 else Qt.RichText)
        lbl.setText(html)
        lbl.setContentsMargins(4, 0, 4, 0)
        lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.NoTextInteraction if USING_PYQT6 else Qt.NoTextInteraction
        )
        lbl.setStyleSheet(
            "font-size:11px; color:#cccccc; background:transparent; border:none; padding:0px;"
        )
        return item, lbl

    def _file_item(self, left_html, right_html, file_info=None, selectable=True):
        """Two-column item: meta left (grey), name right (white bold)."""
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 24))
        if file_info:
            item.setData(_USER_ROLE, file_info)
        if not selectable:
            item.setFlags(item.flags() & ~_NO_SELECT)
        w   = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(4, 0, 4, 0)
        lay.setSpacing(0)
        lbl_left = QLabel()
        lbl_left.setTextFormat(Qt.TextFormat.RichText if USING_PYQT6 else Qt.RichText)
        lbl_left.setText(f"<nobr>{left_html}</nobr>")
        lbl_left.setTextInteractionFlags(
            Qt.TextInteractionFlag.NoTextInteraction if USING_PYQT6 else Qt.NoTextInteraction)
        lbl_left.setStyleSheet(
            "font-size:11px; background:transparent; border:none; padding:0;")
        lbl_right = QLabel()
        lbl_right.setTextFormat(Qt.TextFormat.RichText if USING_PYQT6 else Qt.RichText)
        lbl_right.setText(f"<nobr>{right_html}</nobr>")
        lbl_right.setTextInteractionFlags(
            Qt.TextInteractionFlag.NoTextInteraction if USING_PYQT6 else Qt.NoTextInteraction)
        lbl_right.setStyleSheet(
            "font-size:11px; background:transparent; border:none; padding:0;")
        lay.addWidget(lbl_left)
        lay.addStretch()
        lay.addWidget(lbl_right)
        w.setStyleSheet("background:transparent; border:none;")
        return item, w

    # ── Setup UI ──────────────────────────────────────────────────────────────

    def _setup_ui(self):
        self.setStyleSheet("QMainWindow { background-color:#3a3a3a; }")
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(50)
        hdr.setStyleSheet("QWidget { background-color:#2a2a2a; border-bottom:1px solid #1a1a1a; }")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(15, 0, 15, 0)
        t = QLabel("USD Assembler")
        t.setStyleSheet("font-size:16px; font-weight:bold; color:#cccccc;")
        hl.addWidget(t); hl.addStretch()
        root.addWidget(hdr)

        # Content (layout built below after mode band)

        # ── Mode band ──────────────────────────────────────────────────────────
        mode_band = QWidget()
        mode_band.setFixedHeight(36)
        mode_band.setStyleSheet("""
            QWidget {
                background-color:#252525;
                border-bottom:1px solid #1a1a1a;
            }
        """)
        mode_lay = QHBoxLayout(mode_band)
        mode_lay.setContentsMargins(8, 0, 8, 0)
        mode_lay.setSpacing(0)
        self.asset_btn  = self._mode_btn("Asset",  self._on_asset_mode)
        self.shot_btn   = self._mode_btn("Shot",   self._on_shot_mode)
        self.previz_btn = self._mode_btn("Previz", self._on_previz_mode)
        self.asset_btn.setChecked(True)
        for b in (self.asset_btn, self.shot_btn, self.previz_btn):
            mode_lay.addWidget(b)
        mode_lay.addStretch()

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus if USING_PYQT6 else Qt.NoFocus)
        self.refresh_btn.setFixedHeight(22)
        self.refresh_btn.clicked.connect(self._on_refresh)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color:transparent; color:#666666;
                border:1px solid #444444; outline:none;
                padding:0px 10px; font-size:11px; font-weight:bold;
            }
            QPushButton:hover { color:#aaaaaa; border-color:#666666; }
            QPushButton:pressed { color:#cccccc; border-color:#888888; }
        """)
        mode_lay.addWidget(self.refresh_btn)
        root.addWidget(mode_band)
        inner = QWidget()
        inner.setStyleSheet("background-color:#3a3a3a;")
        il = QVBoxLayout(inner)
        il.setContentsMargins(15, 12, 15, 10)
        il.setSpacing(12)
        cl = il

        # ── Top area: selectors (left) + linked assets panel (right, shot only) ─
        top_outer = QWidget()
        to_lay    = QHBoxLayout(top_outer)
        to_lay.setContentsMargins(0, 0, 0, 0)
        to_lay.setSpacing(20)

        # Left column: dropdowns
        top = QWidget()
        tl  = QVBoxLayout(top)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(4)

        # Category (asset only)
        self.category_selector = DropdownSelector("")
        self.category_selector.set_callback(self._on_category_selected)
        self.category_selector.setFixedWidth(DROP_W)
        self.category_widget = self._selector_widget("Category:", self.category_selector)
        tl.addWidget(self.category_widget)

        # Sequence (shot mode only)
        self.sequence_selector = DropdownSelector("")
        self.sequence_selector.set_callback(self._on_sequence_selected)
        self.sequence_selector.setFixedWidth(DROP_W)
        self.sequence_widget = self._selector_widget("Sequence:", self.sequence_selector)
        self.sequence_widget.hide()
        tl.addWidget(self.sequence_widget)

        # Entity (Asset / Shot / Previz)
        self.entity_label    = self._lbl("Asset:")
        self.entity_selector = DropdownSelector("")
        self.entity_selector.set_callback(self._on_entity_selected)
        self.entity_selector.setFixedWidth(DROP_W)
        entity_row = QHBoxLayout()
        entity_row.setSpacing(20)
        entity_row.addWidget(self.entity_label)
        entity_row.addWidget(self.entity_selector)
        entity_row.addStretch()
        tl.addLayout(entity_row)

        # Task
        self.task_label    = self._lbl("Task:")
        self.task_selector = DropdownSelector("")
        self.task_selector.set_callback(self._on_task_selected)
        self.task_selector.setFixedWidth(DROP_W)
        task_row = QHBoxLayout()
        task_row.setSpacing(20)
        task_row.addWidget(self.task_label)
        task_row.addWidget(self.task_selector)
        task_row.addStretch()
        tl.addLayout(task_row)

        # Assembly + Add button
        self.assembly_selector = DropdownSelector("")
        self.assembly_selector.set_callback(self._on_assembly_selected)
        self.assembly_selector.setFixedWidth(DROP_W)
        self.add_assembly_btn = QPushButton("Add Assembly")
        self.add_assembly_btn.clicked.connect(self._add_new_assembly)
        self.add_assembly_btn.setFixedHeight(22)
        self.add_assembly_btn.setStyleSheet(
            _SMALL_BTN.replace("padding:6px;", "padding:2px 10px;")
        )
        tl.addLayout(self._selector_row("Assembly:", self.assembly_selector, self.add_assembly_btn))
        tl.addStretch()
        to_lay.addWidget(top)

        cl.addWidget(top_outer)
        cl.addSpacing(8)

        # Lists
        lists = QWidget()
        ll    = QHBoxLayout(lists)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(15)

        fp = QWidget()
        fl = QVBoxLayout(fp)
        fl.setContentsMargins(0, 0, 0, 0); fl.setSpacing(8)
        fh = QLabel("Available Files")
        fh.setStyleSheet(_LABEL_STYLE + " padding:2px 0;")
        fl.addWidget(fh)
        self.files_list = QListWidget()
        self.files_list.setSelectionMode(
            QListWidget.SelectionMode.MultiSelection if USING_PYQT6 else QListWidget.MultiSelection
        )
        self.files_list.setStyleSheet(_LIST)
        fl.addWidget(self.files_list)
        self.link_btn = QPushButton("Link \u2192")
        self.link_btn.clicked.connect(self._link_selected_files)
        self.link_btn.setStyleSheet(_SMALL_BTN)
        fl.addWidget(self.link_btn)
        ll.addWidget(fp)

        ap = QWidget()
        al = QVBoxLayout(ap)
        al.setContentsMargins(0, 0, 0, 0); al.setSpacing(8)
        self.assembly_header = QLabel("Assembly: None")
        self.assembly_header.setStyleSheet(_LABEL_STYLE + " padding:2px 0;")
        al.addWidget(self.assembly_header)
        self.assembly_list = QListWidget()
        self.assembly_list.setSelectionMode(
            QListWidget.SelectionMode.MultiSelection if USING_PYQT6 else QListWidget.MultiSelection
        )
        self.assembly_list.setStyleSheet(_LIST)
        al.addWidget(self.assembly_list)
        btns = QHBoxLayout()
        self.unlink_btn = QPushButton("\u2190 Unlink")
        self.unlink_btn.clicked.connect(self._unlink_selected_files)
        self.unlink_btn.setStyleSheet(_SMALL_BTN)
        btns.addWidget(self.unlink_btn)
        self.publish_btn = QPushButton("Publish")
        self.publish_btn.clicked.connect(self._publish_assembly)
        self.publish_btn.setStyleSheet(_PUBLISH_BTN)
        btns.addWidget(self.publish_btn)
        al.addLayout(btns)
        ll.addWidget(ap)

        # Thin vertical separator
        self.panel_separator = QFrame()
        self.panel_separator.setFrameShape(QFrame.Shape.VLine if USING_PYQT6 else QFrame.VLine)
        self.panel_separator.setStyleSheet("QFrame { color:#2a2a2a; background:#2a2a2a; max-width:1px; }")
        self.panel_separator.hide()
        ll.addWidget(self.panel_separator)

        # Linked Assets panel — right of Assembly, shot/previz only
        self.asset_panel = QWidget()
        apl = QVBoxLayout(self.asset_panel)
        apl.setContentsMargins(0, 0, 0, 0)
        apl.setSpacing(8)

        ap_hdr = QHBoxLayout()
        self.assets_panel_header = QLabel("Linked Assets")
        self.assets_panel_header.setStyleSheet(_LABEL_STYLE + " padding:2px 0;")
        ap_hdr.addWidget(self.assets_panel_header)
        ap_hdr.addStretch()
        self.add_asset_btn = QPushButton("+ Asset")
        self.add_asset_btn.clicked.connect(self._add_asset_dialog)
        self.add_asset_btn.setFixedHeight(20)
        self.add_asset_btn.setStyleSheet(
            _SMALL_BTN.replace("padding:6px;", "padding:1px 8px;").replace("font-size:11px;", "font-size:10px;")
        )
        ap_hdr.addWidget(self.add_asset_btn)
        apl.addLayout(ap_hdr)

        self.assets_panel_list = QListWidget()
        self.assets_panel_list.setStyleSheet(_LIST)
        apl.addWidget(self.assets_panel_list)

        self.publish_assets_btn = QPushButton("Publish Assets")
        self.publish_assets_btn.clicked.connect(self._publish_shot_assets_panel)
        self.publish_assets_btn.setStyleSheet(
            _PUBLISH_BTN.replace("padding:6px;", "padding:2px 8px;")
                        .replace("font-size:11px;", "font-size:10px;")
        )
        self.publish_assets_btn.setFixedHeight(20)
        apl.addWidget(self.publish_assets_btn)

        self.asset_panel.hide()
        ll.addWidget(self.asset_panel)

        cl.addWidget(lists, 1)
        root.addWidget(inner, 1)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(
            "color:#888; font-size:10px; padding:8px 15px; "
            "border-top:1px solid #2a2a2a; background-color:#3a3a3a;"
        )
        root.addWidget(self.status_label)

    # ── Project init ──────────────────────────────────────────────────────────

    def _initialize_project(self):
        self.project_path = ProjectManager.find_project_path()
        if not self.project_path:
            self.status_label.setText("Project not found")
            return
        self.scanner = AssetScanner(self.project_path)
        self._load_categories()
        self._load_assemblies()
        self.status_label.setText(f"Project: {self.project_path.name}")
        self._load_custom_logo()

    def _load_custom_logo(self):
        def res(rel):
            try:    base = sys._MEIPASS
            except: base = os.path.abspath(".")
            return os.path.join(base, rel)
        for p in [res("icone/assembler.ico"), res("assembler.ico"),
                  "icone/assembler.ico", "assembler.ico"]:
            if p and Path(p).exists():
                try:
                    if str(p).endswith('.ico'):
                        icon = QIcon(str(p))
                    else:
                        px = QPixmap(str(p))
                        if px.isNull(): continue
                        icon = QIcon(); icon.addPixmap(px)
                    if not icon.isNull():
                        self.setWindowIcon(icon); return
                except Exception:
                    continue

    # ── Mode switches ─────────────────────────────────────────────────────────

    def _on_refresh(self):
        """Reload all lists for the current mode without losing the current entity."""
        mode   = self.current_mode
        entity = self._entity
        seq    = self.current_sequence
        # Re-init the mode (reloads entity list, sequences, etc.)
        {'asset': self._on_asset_mode, 'shot': self._on_shot_mode, 'previz': self._on_previz_mode}[mode]()
        # Force re-check so the button stays checked
        {'asset': self.asset_btn, 'shot': self.shot_btn, 'previz': self.previz_btn}[mode].setChecked(True)

    def _on_asset_mode(self):
        if not self.asset_btn.isChecked():
            self.asset_btn.setChecked(True); return
        self.shot_btn.setChecked(False); self.previz_btn.setChecked(False)
        self.current_mode = 'asset'
        self.sequence_widget.hide()
        self.category_widget.show()
        self.asset_panel.hide()
        self.panel_separator.hide()
        self.add_assembly_btn.show()
        self.assembly_selector.setEnabled(True)
        self.task_selector.setEnabled(True)
        self.entity_label.setText("Asset:")
        self._clear_entity()
        self.current_category = self.current_sequence = self.current_task = self.current_assembly = None
        self.linked_files = []
        self.files_list.clear()
        self.assembly_list.clear()
        self.assembly_header.setText("Assembly: None")
        self.status_label.setText("Asset mode")
        self._load_categories()

    def _on_shot_mode(self):
        if not self.shot_btn.isChecked():
            self.shot_btn.setChecked(True); return
        self.asset_btn.setChecked(False); self.previz_btn.setChecked(False)
        self.current_mode = 'shot'
        self.category_widget.hide()
        self.sequence_widget.show()
        self.asset_panel.show()
        self.panel_separator.show()
        self.add_assembly_btn.show()
        self.assembly_selector.setEnabled(True)
        self.task_selector.setEnabled(True)
        self.entity_label.setText("Shot:")
        self._clear_entity()
        self.current_sequence = self.current_task = self.current_assembly = None
        self.linked_files = []
        self.shot_linked_assets = []
        self.files_list.clear()
        self.assembly_list.clear()
        self.assembly_header.setText("Assembly: None")
        self.assets_panel_list.clear()
        self.status_label.setText("Shot mode")
        self._load_sequences()

    def _on_previz_mode(self):
        if not self.previz_btn.isChecked():
            self.previz_btn.setChecked(True); return
        self.asset_btn.setChecked(False); self.shot_btn.setChecked(False)
        self.current_mode = 'previz'
        self.category_widget.hide()
        self.sequence_widget.hide()
        self.asset_panel.hide()
        self.panel_separator.hide()
        self.add_assembly_btn.show()
        self.assembly_selector.setEnabled(True)
        self.task_selector.setEnabled(True)
        self.entity_label.setText("Previz:")
        self._clear_entity()
        self.current_sequence = self.current_task = self.current_assembly = None
        self.linked_files = []
        self.files_list.clear()
        self.assembly_list.clear()
        self.assembly_header.setText("Assembly: None")
        self.status_label.setText("Previz mode")
        self._load_entities()

    # ── Entity / Category / Sequence ──────────────────────────────────────────

    def _load_sequences(self):
        if not self.scanner: return
        seqs = self.scanner.get_sequences()
        self.sequence_selector.clear()
        self.sequence_selector.addItems(seqs)
        if seqs:
            self.sequence_selector.select_item(0)

    def _on_sequence_selected(self, text, index):
        self.entity_selector.clear()
        self.task_selector.clear()
        self.assembly_selector.clear()
        self.files_list.clear()
        self._set_entity(None)
        if index < 0 or not text:
            self.current_sequence = None
            return
        self.current_sequence = text
        self._load_entities()

    def _load_categories(self):
        self.category_selector.clear()
        self.category_selector.addItems(["character", "environment", "fx", "props"])
        if self.category_selector.count() > 0:
            self.category_selector.select_item(0)
            self.current_category = self.category_selector.items[0]

    def _on_category_selected(self, text, index):
        self.entity_selector.clear()
        self.task_selector.clear()
        self.assembly_selector.clear()
        self.files_list.clear()
        self.current_asset = None
        if index < 0:
            self.current_category = None
            self.assembly_header.setText("Assembly: None")
            return
        self.current_category = text
        self._load_entities()
        self.status_label.setText(f"Category: {text}")

    def _load_entities(self):
        if not self.scanner: return
        if self._mode == 'asset':
            items = self.scanner.get_assets(self.current_category)
        elif self._mode == 'shot':
            items = self.scanner.get_shots(self.current_sequence)
        else:
            items = self.scanner.get_previz()
        self.entity_selector.clear()
        self.entity_selector.addItems(items)
        if items:
            self.entity_selector.select_item(0)
        self.status_label.setText(f"Found {len(items)} items")

    def _on_entity_selected(self, text, index):
        self.task_selector.clear()
        self.assembly_selector.clear()
        self.files_list.clear()
        if index < 0 or not text:
            self._set_entity(None)
            self.assembly_header.setText("Assembly: None")
            return
        self._set_entity(text)
        self.assembly_header.setText(f"Assembly: {text}")
        self._load_tasks(text)
        self._load_assemblies()
        if self._mode == 'shot':
            self._refresh_asset_panel()
        self.status_label.setText(f"Selected: {text}")

    # ── Tasks ─────────────────────────────────────────────────────────────────

    def _load_tasks(self, entity_name):
        if not self.scanner:
            return
        tasks = self.scanner.get_tasks(self._mode, entity_name)
        self.task_selector.clear()
        self.task_selector.addItem("all", enabled=True)
        names   = list(tasks.keys())
        enabled = [tasks[n] for n in names]
        self.task_selector.addItems(names, enabled)
        # Auto-select "all"
        self.task_selector.select_item(0)

    def _on_task_selected(self, text, index):
        self.files_list.clear()
        self.linked_files = []
        self.update_assembly_display()
        if index < 0 or not text:
            self.current_task = None
            self.link_btn.setEnabled(True)
            self.unlink_btn.setEnabled(True)
            self.publish_btn.setEnabled(True)
            return
        self.current_task = text
        entity = self._entity
        if text == "all":
            self.link_btn.setEnabled(False)
            self.publish_btn.setEnabled(False)
            self._load_all_files(entity)
            self._show_all_assemblies()
            self.status_label.setText(f"All tasks: {entity}")
        else:
            self.link_btn.setEnabled(True)
            self.unlink_btn.setEnabled(True)
            self.publish_btn.setEnabled(True)
            self._load_files(entity, text)
            if self.current_assembly:
                self._load_existing_assembly()
            self._update_assembly_info()

    # ── File lists ────────────────────────────────────────────────────────────

    def _load_files(self, entity_name, task_name):
        if not self.scanner:
            return
        files = self.scanner.get_usd_files(self._mode, entity_name, task_name)
        if not files:
            self.files_list.addItem(self._no_select_item("No USD files found"))
            return
        for fi in files:
            meta = fi['metadata']
            date = meta.get('exportDate', ''); date = date.split()[0] if date and ' ' in date else date
            name = meta.get('groupName', fi['output_name'])
            left, right = self._fmt_row(name, meta.get('user','?'), fi['file'].suffix[1:], date)
            item, w = self._file_item(left, right, fi, selectable=True)
            self.files_list.addItem(item)
            self.files_list.setItemWidget(item, w)

    def _load_all_files(self, entity_name):
        if not self.scanner:
            return
        tasks = self.scanner.get_tasks(self._mode, entity_name)
        all_files = []
        for task_name, has_usd in tasks.items():
            if has_usd:
                for fi in self.scanner.get_usd_files(self._mode, entity_name, task_name):
                    fi['task_name'] = task_name
                    all_files.append(fi)
        if not all_files:
            self.files_list.addItem(self._no_select_item("No USD files found"))
            return
        # Grouper par task
        by_task = {}
        for fi in all_files:
            by_task.setdefault(fi['task_name'], []).append(fi)
        for task in sorted(by_task):
            # Header de section
            hdr_item, hdr_lbl = self._rich_item(self._fmt_task_header(task), selectable=False)
            self.files_list.addItem(hdr_item)
            self.files_list.setItemWidget(hdr_item, hdr_lbl)
            for fi in by_task[task]:
                meta = fi['metadata']
                date = meta.get('exportDate', ''); date = date.split()[0] if date and ' ' in date else date
                name = meta.get('groupName', fi['output_name'])
                left, right = self._fmt_row(name, meta.get('user','?'), fi['file'].suffix[1:], date, indent='  ')
                item, w = self._file_item(left, right, fi, selectable=True)
                self.files_list.addItem(item)
                self.files_list.setItemWidget(item, w)

    def _refresh_asset_panel(self):
        """Reload linked assets panel from [entity].usda or [entity]_[assembly].usda."""
        self.assets_panel_list.clear()
        self.shot_linked_assets = []
        if not self.scanner or not self._entity: return
        assembly = self.current_assembly or 'main'
        for fi in self.scanner.get_linked_assets(self._entity, assembly):
            name = fi.get('asset_name', '')
            if name:
                self.shot_linked_assets.append({'asset_name': name, 'published': True})
        self._rebuild_asset_panel()

    def _rebuild_asset_panel(self):
        self.assets_panel_list.clear()
        for info in self.shot_linked_assets:
            asset_name = info['asset_name'] if isinstance(info, dict) else info
            published  = info.get('published', False) if isinstance(info, dict) else False
            dot        = f"{_GREEN_DOT} " if published else ""

            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 22))
            self.assets_panel_list.addItem(item)

            w = QWidget()
            w.setStyleSheet("background:transparent; border:none;")
            lay = QHBoxLayout(w)
            lay.setContentsMargins(6, 0, 4, 0)
            lay.setSpacing(4)

            lbl = QLabel()
            lbl.setTextFormat(Qt.TextFormat.RichText if USING_PYQT6 else Qt.RichText)
            lbl.setText(f"{dot}{asset_name}")
            lbl.setStyleSheet("font-size:11px; color:#e0e0e0; background:transparent; border:none;")
            lay.addWidget(lbl)
            lay.addStretch()

            btn = QPushButton("\u2212")
            btn.setFixedSize(16, 16)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus if USING_PYQT6 else Qt.NoFocus)
            btn.setStyleSheet(
                "QPushButton{background:#555;color:#ccc;border:none;font-size:12px;font-weight:bold;}"
                "QPushButton:hover{background:#888;}"
            )
            btn.clicked.connect(lambda _checked, n=asset_name: self._remove_asset(n))
            lay.addWidget(btn)

            self.assets_panel_list.setItemWidget(item, w)

    def _add_asset_dialog(self):
        if not self._entity:
            QMessageBox.warning(self, "Warning", "Select a shot first"); return
        if not self.scanner: return
        all_assets = self.scanner.get_assets()
        already_names = [
            i['asset_name'] if isinstance(i, dict) else i
            for i in self.shot_linked_assets
        ]
        dlg = LinkAssetDialog(all_assets, already_linked=already_names, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            for name in dlg.get_selected():
                if name not in already_names:
                    self.shot_linked_assets.append({'asset_name': name, 'published': False})
            self._rebuild_asset_panel()

    def _remove_asset(self, name):
        self.shot_linked_assets = [
            i for i in self.shot_linked_assets
            if (i['asset_name'] if isinstance(i, dict) else i) != name
        ]
        self._rebuild_asset_panel()

    def _publish_shot_assets_panel(self):
        entity = self._entity
        if not entity:
            QMessageBox.warning(self, "Warning", "Select a shot first"); return
        try:
            proj  = self._norm_project_path()
            assembly = self.current_assembly or 'main'
            if assembly == 'main':
                usda = self.project_path / "shots" / entity / f"{entity}.usda"
            else:
                usda = self.project_path / "shots" / entity / f"{entity}_{assembly}.usda"
            paths = [f"./pub/assembly/{assembly}Assembly/{entity}_{assembly}Assembly.usda"]
            for info in self.shot_linked_assets:
                name = info['asset_name'] if isinstance(info, dict) else info
                paths.append(
                    f"{proj}/assets/{name}/pub/assembly/mainAssembly/asset_{name}_mainAssembly.usda"
                )
            write_sublayer_usda(usda, paths)
            for info in self.shot_linked_assets:
                if isinstance(info, dict):
                    info['published'] = True
            self._rebuild_asset_panel()
            n = len(self.shot_linked_assets)
            self.status_label.setText(f"Published {n} assets to {usda.name}")
            QMessageBox.information(self, "Success", f"Published {n} asset(s) to:\n{usda}")
        except Exception as e:
            self.status_label.setText(f"Error: {e}")
            QMessageBox.critical(self, "Error", f"Failed:\n{e}")

    # ── Assemblies ────────────────────────────────────────────────────────────

    def _load_assemblies(self):
        self.assembly_selector.clear()
        self.assembly_selector.addItem("Select assembly...")
        entity = self._entity
        if self.scanner and entity:
            self.assemblies = self.scanner.get_available_assemblies(self._mode, entity)
            if "main" not in self.assemblies:
                self.assemblies.insert(0, "main")
        else:
            self.assemblies = []
        if self.assemblies:
            self.assembly_selector.addItems(self.assemblies)
            if "main" in self.assemblies:
                self.assembly_selector.select_item(self.assemblies.index("main") + 1)

    def _on_assembly_selected(self, text, index):
        if index <= 0 or text == "Select assembly...":
            self.current_assembly = None
            return
        self.current_assembly = text
        self._update_assembly_info()
        self._load_existing_assembly()
        if self.current_task == "all":
            self._show_all_assemblies()
        if self._mode in ('shot', 'previz') and self._entity:
            self.assets_panel_header.setText(f"Linked Assets: {self._entity}")
            self._refresh_asset_panel()

    def _load_existing_assembly(self):
        if not self.scanner or not self.current_task or not self.current_assembly:
            return
        if self.current_task == "all" or not self._entity:
            return
        files = self.scanner.get_existing_assembly(
            self._mode, self._entity, self.current_task, self.current_assembly
        )
        self.linked_files = files
        self.update_assembly_display()
        if files:
            self.status_label.setText(f"Loaded: {len(files)} files")

    def _update_assembly_info(self):
        if not self.current_task or not self.current_assembly or not self._entity:
            return
        folder = f"{self.current_assembly}{self.current_task.title()}"
        exists = self.scanner.check_assembly_folder(
            self._mode, self._entity, self.current_task, self.current_assembly
        )
        self.status_label.setText(f"Target: {folder}" + ("" if exists else " (new)"))


    # ── Row formatter (aligned columns everywhere) ─────────────────────────────

    @staticmethod
    def _fmt_row(name, user, ext, date, dot='', indent=''):
        """Returns (left_html, right_html) for two-column layout."""
        u = f"{user:<12}"
        e = f"{ext:<4}"
        d = f"{date}" if date else ""
        left  = f'<span style="color:#e0e0e0;font-weight:bold;">{dot}{indent}{name}</span>'
        right = f'<span style="color:#777777;">{u}&nbsp;&nbsp;{e}&nbsp;&nbsp;{d}</span>'
        return left, right

    @staticmethod
    def _fmt_asset_row(name, dot='', indent=''):
        left  = f'<span style="color:#e0e0e0;font-weight:bold;">{dot}{indent}{name}</span>'
        right = f'<span style="color:#777777;">{"asset":<12}&nbsp;&nbsp;&nbsp;{"usda":<6}</span>'
        return left, right

    @staticmethod
    def _fmt_task_header(task_name):
        return f'<span style="color:#867a68;font-weight:bold;">{task_name.upper()}</span>'

    # ── Assembly display ──────────────────────────────────────────────────────

    def update_assembly_display(self):
        self.assembly_list.clear()
        for fi in self.linked_files:
            dot = f"{_GREEN_DOT} " if fi.get('published', True) else ""
            if fi.get('is_asset', False):
                left, right = self._fmt_asset_row(fi.get('asset_name','unknown'), dot=dot)
            else:
                meta = fi['metadata']
                date = meta.get('exportDate', ''); date = date.split()[0] if date and ' ' in date else date
                left, right = self._fmt_row(meta.get('groupName', fi['output_name']),
                                            meta.get('user','?'), fi['file'].suffix[1:], date, dot=dot)
            item, w = self._file_item(left, right, fi)
            self.assembly_list.addItem(item)
            self.assembly_list.setItemWidget(item, w)

    def _show_all_assemblies(self):
        self.assembly_list.clear()
        self.link_btn.setEnabled(False)
        self.unlink_btn.setEnabled(False)
        self.publish_btn.setEnabled(False)

        if not self.current_assembly or not self.scanner or not self._entity:
            self.assembly_list.addItem(self._no_select_item("Select an assembly to view its contents"))
            return

        all_files = self.scanner.get_all_existing_assemblies(self._mode, self._entity)
        filtered  = [fi for fi in all_files if fi.get('assembly_name') == self.current_assembly]
        if not filtered:
            self.assembly_list.addItem(
                self._no_select_item(f"No files in '{self.current_assembly}' assembly")
            )
            return

        by_task = {}
        for fi in filtered:
            by_task.setdefault(fi.get('source_task', 'unknown'), []).append(fi)

        for task in sorted(by_task):
            hdr_item, hdr_lbl = self._rich_item(self._fmt_task_header(task), selectable=False)
            self.assembly_list.addItem(hdr_item)
            self.assembly_list.setItemWidget(hdr_item, hdr_lbl)
            for fi in by_task[task]:
                dot = f"{_GREEN_DOT} " if fi.get('published', True) else ""
                if fi.get('is_asset', False):
                    left, right = self._fmt_asset_row(fi.get('asset_name','unknown'), dot=dot, indent='  ')
                else:
                    meta = fi['metadata']
                    date = meta.get('exportDate', ''); date = date.split()[0] if date and ' ' in date else date
                    left, right = self._fmt_row(meta.get('groupName', fi['output_name']),
                                                meta.get('user','?'), fi['file'].suffix[1:], date,
                                                dot=dot, indent='  ')
                item, w = self._file_item(left, right, fi, selectable=False)
                self.assembly_list.addItem(item)
                self.assembly_list.setItemWidget(item, w)

    # ── Link / Unlink ─────────────────────────────────────────────────────────

    def _link_selected_files(self):
        selected = self.files_list.selectedItems()
        if not selected:
            self.status_label.setText("No files selected")
            return
        count = 0
        for item in selected:
            fi = item.data(_USER_ROLE)
            if not fi:
                continue
            if fi.get('is_asset'):
                dup = any(
                    e.get('is_asset') and e.get('asset_name') == fi.get('asset_name')
                    for e in self.linked_files
                )
            else:
                dup = any(
                    not e.get('is_asset') and e.get('output_name') == fi.get('output_name')
                    for e in self.linked_files
                )
            if dup:
                key = fi.get('asset_name') if fi.get('is_asset') else fi.get('output_name')
                QMessageBox.information(self, "Info", f"'{key}' is already linked")
                continue
            fi['published'] = False
            self.linked_files.append(fi)
            count += 1
        self.update_assembly_display()
        self.files_list.clearSelection()
        self.status_label.setText(f"Linked {count} file(s)")

    def _unlink_selected_files(self):
        selected = self.assembly_list.selectedItems()
        if not selected:
            self.status_label.setText("No files selected")
            return
        count = 0
        for item in selected:
            fi = item.data(_USER_ROLE)
            if fi in self.linked_files:
                self.linked_files.remove(fi)
                count += 1
        self.update_assembly_display()
        self.status_label.setText(f"Unlinked {count} file(s)")

    # ── Publish ───────────────────────────────────────────────────────────────

    def _publish_assembly(self):
        entity = self._entity
        if not entity:
            QMessageBox.warning(self, "Warning", "Select an entity first"); return
        if not self.current_assembly or not self.current_task:
            QMessageBox.warning(self, "Warning", "Select task and assembly"); return
        if not self.linked_files:
            r = QMessageBox.question(
                self, "Empty Assembly", "No files linked. Publish empty assembly?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if r == QMessageBox.StandardButton.No: return
        try:
            folder = f"{self.current_assembly}{self.current_task.title()}"
            if self._mode == 'asset':
                base   = self.project_path / "assets" / entity / "pub" / "assembly" / folder
                prefix = "asset"
            else:
                base   = self.project_path / "shots" / entity / "pub" / "assembly" / folder
                prefix = "shot"
            base.mkdir(parents=True, exist_ok=True)
            version   = self._next_version(base)
            usda_path = base / version / "usda"
            usda_path.mkdir(parents=True, exist_ok=True)
            content_paths = self._build_sublayer_paths(self.linked_files)
            task_cap = self.current_task.title()
            fname    = assembly_filename(self._mode, entity, self.current_assembly, task_cap)
            versioned = usda_path / fname
            write_sublayer_usda(versioned, content_paths)
            latest = base / "latest" / "usda"
            latest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(versioned, latest / fname)
            n = len(self.linked_files)
            for fi in self.linked_files:
                fi['published'] = True
            self.update_assembly_display()
            self.status_label.setText(f"Published {version}: {n} files")
            QMessageBox.information(self, "Success", f"Published {version}\n{n} files\n{versioned}")
        except Exception as e:
            self.status_label.setText(f"Error: {e}")
            QMessageBox.critical(self, "Error", f"Failed:\n{e}")


    def _build_sublayer_paths(self, linked_files):
        """Return the list of sublayer paths for the given linked files."""
        if not linked_files:
            return []
        return [str(fi['file']).replace('\\', '/') for fi in linked_files]

    # ── Assembly structure creation ───────────────────────────────────────────

    def _add_new_assembly(self):
        entity = self._entity
        if not entity:
            QMessageBox.warning(self, "Warning", "Select an entity first"); return
        dialog = AddAssemblyDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name = dialog.get_assembly_name()
        if not name:
            return
        existing = self.scanner.get_available_assemblies(self._mode, entity)
        if name in existing:
            QMessageBox.warning(self, "Warning", f"'{name}' already exists"); return
        try:
            self._create_assembly_structure(self._mode, entity, name)
            self._load_assemblies()
            if name in self.assemblies:
                self.assembly_selector.select_item(self.assemblies.index(name) + 1)
            self.status_label.setText(f"Created assembly: {name}")
            QMessageBox.information(self, "Success", f"Assembly '{name}' created")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed:\n{e}")

    def _create_assembly_structure(self, entity_type, entity_name, assembly_name):
        tasks = ASSEMBLY_TASKS[entity_type]
        if entity_type == 'asset':
            base = self.project_path / "assets" / entity_name / "pub" / "assembly"
        else:
            base = self.project_path / "shots" / entity_name / "pub" / "assembly"
        base.mkdir(parents=True, exist_ok=True)

        # Task folders — keep versioned layout (latest/usda/)
        for task in tasks:
            d = base / f"{assembly_name}{task}" / "latest" / "usda"
            d.mkdir(parents=True, exist_ok=True)
            fname = assembly_filename(entity_type, entity_name, assembly_name, task)
            write_sublayer_usda(d / fname, [])

        # [assembly]Assembly folder — flat, no versioning
        main_dir = base / f"{assembly_name}Assembly"
        main_dir.mkdir(parents=True, exist_ok=True)
        sublayer_paths = [
            f"../{assembly_name}{task}/latest/usda/{assembly_filename(entity_type, entity_name, assembly_name, task)}"
            for task in tasks
        ]
        main_fname = (f"asset_{entity_name}_{assembly_name}Assembly.usda"
                      if entity_type == 'asset'
                      else f"{entity_name}_{assembly_name}Assembly.usda")
        write_sublayer_usda(main_dir / main_fname, sublayer_paths)

        # For shot/previz: create root [entity]_[assembly].usda referencing the assembly
        if entity_type != 'asset':
            root_usda = self.project_path / "shots" / entity_name / f"{entity_name}_{assembly_name}.usda"
            write_sublayer_usda(
                root_usda,
                [f"./pub/assembly/{assembly_name}Assembly/{main_fname}"]
            )

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _next_version(self, path):
        if not path.exists():
            return "v001"
        versions = [
            int(d.name[1:]) for d in path.iterdir()
            if d.is_dir() and d.name.startswith('v') and d.name[1:].isdigit()
        ]
        return f"v{(max(versions) + 1):03d}" if versions else "v001"

    def _norm_project_path(self):
        p = os.environ.get('PIPELINE_PROJECT_PATH', str(self.project_path))
        p = p.replace('\\', '/')
        if p.startswith('/mnt/') and len(p.split('/')) > 3:
            drive = p.split('/')[2].upper()
            p = f"{drive}:/" + "/".join(p.split('/')[3:])
        return p