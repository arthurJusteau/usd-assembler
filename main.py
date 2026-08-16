#!/usr/bin/env python3
"""
USD Assembler - Main Entry Point
"""

import sys

try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QPalette, QColor
    USING_PYQT6 = True
except ImportError:
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QPalette, QColor
        USING_PYQT6 = False
    except ImportError:
        print("Error: Neither PyQt6 nor PySide6 found. Please install one:")
        print("pip install PyQt6")
        sys.exit(1)

from ui import USDAssembler


def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Minimal theme - white background
    palette = QPalette()
    if USING_PYQT6:
        palette.setColor(QPalette.ColorRole.Window, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
        palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 245, 245))
        palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(0, 0, 0))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(200, 200, 200))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
    else:
        palette.setColor(QPalette.Window, QColor(255, 255, 255))
        palette.setColor(QPalette.WindowText, QColor(0, 0, 0))
        palette.setColor(QPalette.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.AlternateBase, QColor(245, 245, 245))
        palette.setColor(QPalette.Button, QColor(240, 240, 240))
        palette.setColor(QPalette.ButtonText, QColor(0, 0, 0))
        palette.setColor(QPalette.Highlight, QColor(200, 200, 200))
        palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
    
    app.setPalette(palette)
    
    window = USDAssembler()
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())