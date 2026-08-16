"""
Custom widgets for USD Assembler
"""

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
        QPushButton, QListWidget, QListWidgetItem, QFrame, QDialog
    )
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QAction
    USING_PYQT6 = True
except ImportError:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
        QPushButton, QListWidget, QListWidgetItem, QFrame, QDialog
    )
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QAction
    USING_PYQT6 = False

_ITEM_H   = 20   # pixels per dropdown row
_MAX_VIS  = 15   # rows before scroll kicks in
_SCROLL_W = 8    # scrollbar width

_POPUP_LIST_STYLE = """
    QListWidget {
        border: none;
        background-color: #4a4a4a;
        color: #cccccc;
        font-size: 11px;
        outline: none;
    }
    QListWidget::item {
        padding: 1px 8px;
        min-height: 18px;
    }
    QListWidget::item:selected,
    QListWidget::item:hover {
        background-color: #ff6600;
        color: #ffffff;
    }
    QListWidget::item:disabled {
        color: #666666;
        background-color: #3a3a3a;
    }
    QScrollBar:vertical {
        background: #3a3a3a;
        width: 6px;
        margin: 0;
        border: none;
    }
    QScrollBar::handle:vertical {
        background: #666666;
        border-radius: 3px;
        min-height: 20px;
    }
    QScrollBar::handle:vertical:hover {
        background: #888888;
    }
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {
        background: none;
        border: none;
        height: 0;
    }
"""

_DISPLAY_STYLE = """
    QLineEdit {
        border: 1px solid #2a2a2a;
        padding: 2px 6px;
        background-color: #4a4a4a;
        color: #cccccc;
        font-size: 11px;
    }
    QLineEdit:hover {
        background-color: #555555;
        border: 1px solid #666666;
    }
    QLineEdit:focus {
        border: 1px solid #ff6600;
    }
    QLineEdit:disabled {
        background-color: #353535;
        color: #666666;
        border: 1px solid #2a2a2a;
    }
"""


class DropdownSelector(QWidget):
    """Dropdown with a scrollable floating list (max 15 visible items)."""

    def __init__(self, placeholder="-- Select --", parent=None):
        super().__init__(parent)
        self.items         = []   # list of (text, enabled)
        self.current_index = -1
        self.placeholder   = placeholder
        self.callback      = None
        self._popup        = None
        self._setup_ui()

    # ── Public API ────────────────────────────────────────────────────────────

    def set_callback(self, fn):
        self.callback = fn

    def clear(self):
        self.items         = []
        self.current_index = -1
        self.display.setText(self.placeholder)

    def addItem(self, text, enabled=True):
        self.items.append((text, enabled))

    def addItems(self, texts, enabled_list=None):
        for i, text in enumerate(texts):
            en = enabled_list[i] if enabled_list and i < len(enabled_list) else True
            self.addItem(text, en)

    def select_item(self, index):
        if 0 <= index < len(self.items):
            text, enabled = self.items[index]
            if enabled:
                self.current_index = index
                self.display.setText(text)
                if self.callback:
                    self.callback(text, index)

    def currentText(self):
        return self.display.text() if self.current_index >= 0 else ""

    def currentIndex(self):
        return self.current_index

    def count(self):
        return len(self.items)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _setup_ui(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.display = QLineEdit()
        self.display.setReadOnly(True)
        self.display.setText(self.placeholder)
        self.display.mousePressEvent = lambda _e: self._show_popup()
        self.display.setStyleSheet(_DISPLAY_STYLE)
        lay.addWidget(self.display, 1)

    def _show_popup(self):
        if not self.items or not self.isEnabled():
            return

        # Close any existing popup first
        if self._popup and self._popup.isVisible():
            self._popup.close()
            self._popup = None
            return

        w = max(self.width(), 120)
        n = len(self.items)
        visible = min(n, _MAX_VIS)
        h = visible * _ITEM_H + 2   # +2 for top/bottom border

        popup_flags = Qt.WindowType.Popup if USING_PYQT6 else Qt.Popup
        popup = QFrame(None, popup_flags)
        popup.setStyleSheet("QFrame { background-color:#4a4a4a; border:1px solid #1a1a1a; }")
        popup.setFixedSize(w, h)
        pl = QVBoxLayout(popup)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(0)

        lw = QListWidget()
        lw.setStyleSheet(_POPUP_LIST_STYLE)
        lw.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff if USING_PYQT6 else Qt.ScrollBarAlwaysOff
        )
        if n > _MAX_VIS:
            lw.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAsNeeded if USING_PYQT6 else Qt.ScrollBarAsNeeded
            )
        else:
            lw.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff if USING_PYQT6 else Qt.ScrollBarAlwaysOff
            )
        lw.setFixedWidth(w)
        lw.setFixedHeight(h)

        _disabled_flag  = Qt.ItemFlag.ItemIsEnabled    if USING_PYQT6 else Qt.ItemIsEnabled
        _selectable_flag= Qt.ItemFlag.ItemIsSelectable if USING_PYQT6 else Qt.ItemIsSelectable

        for text, enabled in self.items:
            item = QListWidgetItem(text)
            if not enabled:
                item.setFlags(item.flags() & ~_disabled_flag & ~_selectable_flag)
            lw.addItem(item)

        pl.addWidget(lw)

        global_pos = self.mapToGlobal(self.rect().bottomLeft())
        popup.move(global_pos)
        popup.show()
        lw.setFocus()

        _enabled_flag = Qt.ItemFlag.ItemIsEnabled if USING_PYQT6 else Qt.ItemIsEnabled

        def on_click(item):
            if item.flags() & _enabled_flag:
                idx = lw.row(item)
                self.current_index = idx
                self.display.setText(item.text())
                popup.close()
                if self.callback:
                    self.callback(item.text(), idx)

        lw.itemClicked.connect(on_click)
        self._popup = popup

    # Keep old show_menu name as alias for compatibility
    def show_menu(self):
        self._show_popup()


# ─────────────────────────────────────────────────────────────────────────────


class AddAssemblyDialog(QDialog):
    """Dialog to name a new assembly."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Assembly")
        self.setModal(True)
        self.setFixedSize(350, 150)
        self._setup_ui()

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(20, 20, 20, 20)
        self.setStyleSheet("QDialog { background-color:#3a3a3a; }")

        lbl = QLabel("Assembly Name:")
        lbl.setStyleSheet("font-weight:bold; color:#cccccc; font-size:11px;")
        lay.addWidget(lbl)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., hero, prop, background...")
        self.name_input.setStyleSheet("""
            QLineEdit {
                border:1px solid #2a2a2a; padding:2px 6px;
                background-color:#4a4a4a; color:#cccccc; font-size:11px;
            }
            QLineEdit:focus { border:1px solid #ff6600; }
        """)
        lay.addWidget(self.name_input)

        row = QHBoxLayout()
        row.addStretch()

        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        cancel.setStyleSheet(self._btn(False))
        row.addWidget(cancel)

        ok = QPushButton("Add")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        ok.setStyleSheet(self._btn(True))
        row.addWidget(ok)

        lay.addLayout(row)
        self.name_input.setFocus()

    def get_assembly_name(self):
        return self.name_input.text().strip()

    @staticmethod
    def _btn(accent):
        if accent:
            return ("QPushButton{background:#ff6600;color:#fff;border:1px solid #ff6600;"
                    "padding:6px 16px;font-size:11px;font-weight:bold;}"
                    "QPushButton:hover{background:#ff7722;}"
                    "QPushButton:pressed{background:#ee5500;}")
        return ("QPushButton{background:#4a4a4a;color:#ccc;border:1px solid #2a2a2a;"
                "padding:6px 16px;font-size:11px;}"
                "QPushButton:hover{background:#555;}"
                "QPushButton:pressed{background:#3a3a3a;}")


# ─────────────────────────────────────────────────────────────────────────────


class LinkAssetDialog(QDialog):
    """Scrollable list to pick assets to link to a shot."""

    _DLG_STYLE = """
        QDialog { background-color:#3a3a3a; }
        QListWidget {
            border:1px solid #2a2a2a; background-color:#282828;
            outline:none; font-size:11px; color:#cccccc;
        }
        QListWidget::item { padding:4px 6px; border-bottom:1px solid #333; }
        QListWidget::item:selected       { background-color:#867a68; color:#fff; }
        QListWidget::item:selected:hover { background-color:#867a68; color:#fff; }
        QListWidget::item:hover          { background-color:#404040; }
        QLabel { color:#aaaaaa; font-size:11px; font-weight:bold; }
    """

    def __init__(self, assets, already_linked=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Link Asset")
        self.setModal(True)
        self.setFixedSize(300, 420)
        self.setStyleSheet(self._DLG_STYLE)
        self._selected = []
        self._already  = set(already_linked or [])
        self._build(assets)

    def _build(self, assets):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        lay.addWidget(QLabel("Select assets to link:"))

        self.list_w = QListWidget()
        mode = (QListWidget.SelectionMode.MultiSelection if USING_PYQT6
                else QListWidget.MultiSelection)
        self.list_w.setSelectionMode(mode)

        # Show ALL assets — let caller decide what to show
        for a in assets:
            item = QListWidgetItem(a)
            if a in self._already:
                # Show already-linked assets as greyed / not selectable
                _en  = Qt.ItemFlag.ItemIsEnabled    if USING_PYQT6 else Qt.ItemIsEnabled
                _sel = Qt.ItemFlag.ItemIsSelectable if USING_PYQT6 else Qt.ItemIsSelectable
                item.setFlags(item.flags() & ~_en & ~_sel)
                item.setText(f"{a}  ✓")
            self.list_w.addItem(item)

        lay.addWidget(self.list_w)

        row = QHBoxLayout()
        row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        cancel.setStyleSheet(self._btn_style(False))
        row.addWidget(cancel)
        ok = QPushButton("Link")
        ok.setDefault(True)
        ok.clicked.connect(self._on_ok)
        ok.setStyleSheet(self._btn_style(True))
        row.addWidget(ok)
        lay.addLayout(row)

    def _on_ok(self):
        self._selected = [i.text() for i in self.list_w.selectedItems()]
        self.accept()

    def get_selected(self):
        return self._selected

    @staticmethod
    def _btn_style(accent):
        if accent:
            return ("QPushButton{background:#867a68;color:#fff;border:1px solid #867a68;"
                    "padding:4px 14px;font-size:11px;font-weight:bold;}"
                    "QPushButton:hover{background:#a2947d;}")
        return ("QPushButton{background:#4a4a4a;color:#ccc;border:1px solid #2a2a2a;"
                "padding:4px 14px;font-size:11px;}"
                "QPushButton:hover{background:#555;}")