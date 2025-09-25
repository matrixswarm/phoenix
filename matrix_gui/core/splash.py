from PyQt5.QtWidgets import QSplashScreen
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtCore import Qt, QTimer

class PhoenixSplash(QSplashScreen):
    def __init__(self):
        pixmap = QPixmap("matrix_gui/theme/matrixswarm_logo.png")  # Queen’s crest
        super().__init__(pixmap)

        self.setFont(QFont("Consolas", 12))
        self.messages = [
            "Decrypting Vault…",
            "Assembling Guardians…",
            "Establishing Trust Lineage…",
            "Summoning Sentinels…",
            "All Hail the Queen…"
        ]
        self.index = 0

        # show first message
        self.showMessage(
            self.messages[self.index],
            Qt.AlignBottom | Qt.AlignCenter,
            Qt.white
        )

        # cycle messages every 1200ms
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_message)
        self.timer.start(1200)

    def next_message(self):
        self.index = (self.index + 1) % len(self.messages)
        self.showMessage(
            self.messages[self.index],
            Qt.AlignBottom | Qt.AlignCenter,
            Qt.white
        )

