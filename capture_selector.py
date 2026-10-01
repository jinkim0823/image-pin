# SPDX-License-Identifier: GPL-3.0-only
"""Select a region from a frozen screenshot and keep its desktop coordinates."""
from PyQt5.QtCore import Qt, QPointF, QRect, QRectF, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QWidget


class CaptureSelector(QWidget):
    selected = pyqtSignal(object, object, float)
    cancelled = pyqtSignal()

    def __init__(self, snapshot, desktop):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint |
                         Qt.WindowStaysOnTopHint | Qt.X11BypassWindowManagerHint |
                         Qt.NoDropShadowWindowHint)
        self.snapshot = snapshot
        self.desktop = QRect(desktop)
        self.start = None
        self.end = None
        self.done = False
        self.setWindowTitle('Image Pin — Capture')
        self.setGeometry(desktop)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

    def selection(self):
        if self.start is None:
            return QRectF()
        return QRectF(self.start, self.end).normalized().intersected(QRectF(self.desktop))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(QRectF(self.rect()), self.snapshot, QRectF(self.snapshot.rect()))
        selected = self.selection().translated(-self.desktop.x(), -self.desktop.y())
        shade = QColor(0, 0, 0, 80)
        if selected.isEmpty():
            # The frozen snapshot matches the live desktop, so mapping the
            # selector is invisible. Dim only once a drag begins.
            return
        # Keep the selected pixels clear. The selector itself is never captured.
        width, height = self.width(), self.height()
        for rect in (
            QRectF(0, 0, width, selected.top()),
            QRectF(0, selected.bottom(), width, height - selected.bottom()),
            QRectF(0, selected.top(), selected.left(), selected.height()),
            QRectF(selected.right(), selected.top(), width - selected.right(), selected.height()),
        ):
            painter.fillRect(rect, shade)
        painter.setPen(QPen(QColor(255, 255, 255, 220), 1))
        painter.drawRect(selected.adjusted(.5, .5, -.5, -.5))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start = self.end = QPointF(event.globalPos())
            self.update()
        elif event.button() == Qt.RightButton:
            self.cancel()

    def mouseMoveEvent(self, event):
        if self.start is not None:
            self.end = QPointF(event.globalPos())
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or self.start is None or self.done:
            return
        self.end = QPointF(event.globalPos())
        selected = self.selection()
        if selected.width() < 2 or selected.height() < 2:
            self.cancel()
            return
        # Screenshot pixels and Qt desktop coordinates can differ on HiDPI.
        # Map both edges, not only width/height, to avoid accumulated rounding.
        local = selected.translated(-self.desktop.x(), -self.desktop.y())
        sx = self.snapshot.width() / self.desktop.width()
        sy = self.snapshot.height() / self.desktop.height()
        left, top = round(local.left() * sx), round(local.top() * sy)
        right, bottom = round(local.right() * sx), round(local.bottom() * sy)
        source = QRect(left, top, right - left, bottom - top)
        image = self.snapshot.copy(source)
        image.setDevicePixelRatio(1.)
        initial_scale = min(selected.width() / image.width(), selected.height() / image.height())
        self.done = True
        self.hide()
        self.snapshot = QPixmap()
        self.selected.emit(image, selected.topLeft(), initial_scale)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.cancel()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self.cancel()
        event.accept()

    def cancel(self):
        if not self.done:
            self.done = True
            self.hide()
            self.snapshot = QPixmap()
            self.cancelled.emit()
