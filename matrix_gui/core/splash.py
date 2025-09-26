from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtGui import QPixmap, QFont, QPainter
from PyQt5.QtCore import Qt, QTimer, QRect
import sys

class PhoenixSplash(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.SplashScreen | Qt.FramelessWindowHint)
        self.logo = QPixmap("matrix_gui/theme/matrixswarm_logo.png")  # 786x747 or your latest PNG
        self.setFixedSize(self.logo.width(), self.logo.height())
        self.setStyleSheet("background: black;")
        self.font = QFont("Consolas", 10)
        self.text = "Establishing Trust Lineage..."
        self.messages = [
            "Decrypting Vault…",
            "Assembling Guardians…",
            "Establishing Trust Lineage…",
            "All Hail the Queen!",
        ]
        self.index = 0

        # Cycle message
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_message)
        self.timer.start(1200)

    def next_message(self):
        self.index = (self.index + 1) % len(self.messages)
        self.text = self.messages[self.index]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        # Draw logo, fully centered
        painter.drawPixmap(0, 0, self.logo)

        # Draw dynamic text: center in "white space" (adjust Y for your logo)
        painter.setFont(self.font)
        painter.setPen(Qt.white)
        # --- Adjust Y for perfect alignment below logo/crown ---
        text_y = self.height() - 30  # Try 90, 110, 120 px from bottom (experiment!)
        rect = QRect(0, text_y, self.width(), 60)
        painter.drawText(rect, Qt.AlignHCenter | Qt.AlignTop, self.text)

# --- To use in your main ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    splash = PhoenixSplash()
    splash.show()
    QTimer.singleShot(7000, splash.close)  # Demo auto-close
    sys.exit(app.exec_())
