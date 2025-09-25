from PyQt5.QtWidgets import QSplashScreen
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtCore import Qt, QTimer

class PhoenixSplash(QSplashScreen):
    def __init__(self):
        pixmap = QPixmap("matrix_gui/theme/matrixswarm_logo.png")  # your crest
        super().__init__(pixmap)
        self.setFont(QFont("Consolas", 12))
        self.showMessage(
            "All Hail the Queen...",
            Qt.AlignBottom | Qt.AlignCenter,
            Qt.white
        )

def show_with_splash(app, main_cls, delay=3000):
    splash = PhoenixSplash()
    splash.show()
    QTimer.singleShot(delay, lambda: _launch(app, splash, main_cls))

def _launch(app, splash, main_cls):
    splash.close()
    cockpit = main_cls()
    cockpit.show()
