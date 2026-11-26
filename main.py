"""Entry point aplikasi BPIC17 Event Log Analyzer.

GUI : python main.py
CLI : python main.py --cli "BPI Challenge 2017.xes.gz" [--out folder_hasil]
"""

import argparse
import os
import sys
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="pm4py")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def force_light_theme(app):
    """Selalu pakai tema terang agar tampilan konsisten walau Windows memakai dark mode."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPalette

    try:  # Qt >= 6.8: abaikan color scheme sistem operasi
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    except AttributeError:
        pass
    app.setStyle("Fusion")
    p = QPalette()
    white, text = QColor("#ffffff"), QColor("#1f1f1f")
    p.setColor(QPalette.Window, QColor("#f0f0f0"))
    p.setColor(QPalette.WindowText, text)
    p.setColor(QPalette.Base, white)
    p.setColor(QPalette.AlternateBase, QColor("#f5f7f7"))
    p.setColor(QPalette.Text, text)
    p.setColor(QPalette.Button, QColor("#e8e8e8"))
    p.setColor(QPalette.ButtonText, text)
    p.setColor(QPalette.ToolTipBase, white)
    p.setColor(QPalette.ToolTipText, text)
    p.setColor(QPalette.PlaceholderText, QColor("#888888"))
    p.setColor(QPalette.Highlight, QColor("#2f80c4"))
    p.setColor(QPalette.HighlightedText, white)
    p.setColor(QPalette.Link, QColor("#0b5e8a"))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, QColor("#9a9a9a"))
    app.setPalette(p)


def main():
    parser = argparse.ArgumentParser(description="BPIC17 Event Log Analyzer (PM4Py)")
    parser.add_argument("--cli", metavar="XES", help="jalankan semua analisis tanpa GUI pada file XES ini")
    parser.add_argument("--out", metavar="FOLDER", help="folder untuk menyimpan CSV (mode CLI)")
    args = parser.parse_args()

    if args.cli:
        from analyzer.cli import run_cli
        run_cli(args.cli, args.out)
        return

    from PySide6.QtWidgets import QApplication

    from gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("BPIC17 Event Log Analyzer")
    force_light_theme(app)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
