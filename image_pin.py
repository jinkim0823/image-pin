#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Image Pin: reference images floating on one click-through overlay surface."""
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import tomllib
from i18n import tr, set_language

PROJECT = Path(__file__).resolve().parent
RUNTIME = Path(os.environ.get('XDG_RUNTIME_DIR', f'/tmp/image-pin-{os.getuid()}'))
SOCKET = RUNTIME / 'image-pin.sock'
# XWayland only learns the pointer position while it is over an X11 window, so
# under Wayland QCursor.pos() can be stale when a pin is opened from a launcher.
POINTER_TRACKED = os.environ.get('XDG_SESSION_TYPE') != 'wayland' and 'WAYLAND_DISPLAY' not in os.environ


def send(command, path=None, language="system"):
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(2)
        client.connect(str(SOCKET))
        client.sendall((json.dumps({'command': command, 'path': path, 'language': language}) + '\n').encode())
        reply = client.recv(1024)
        if reply != b'OK\n':
            raise RuntimeError(reply.decode(errors='replace'))


def launch(command, path=None, language="system"):
    try:
        send(command, path, language)
        return
    except OSError:
        pass
    RUNTIME.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Serialize starts without holding the lock in the resident process.
    import fcntl
    with (RUNTIME / 'image-pin-start.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            send(command, path, language)
            return
        except OSError:
            pass
        log_dir = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'image-pin'
        log_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        env = os.environ.copy()
        # GNOME Wayland permits above hints and explicit positioning via XWayland.
        env['QT_QPA_PLATFORM'] = 'xcb'
        with (log_dir / 'helper.log').open('ab') as log:
            process = subprocess.Popen([sys.executable, str(PROJECT / 'image_pin.py'), 'daemon'],
                                       env=env, stdout=log, stderr=log,
                                       stdin=subprocess.DEVNULL, start_new_session=True)
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError(f'Image Pin exited; see {log_dir / "helper.log"}')
            try:
                send(command, path, language)
                return
            except OSError:
                time.sleep(0.05)
        raise RuntimeError('Image Pin startup timed out')


def gui_types():
    from PyQt5.QtCore import Qt, QPointF, QRect, QRectF, QTimer, QProcess
    from PyQt5.QtGui import QImage, QPixmap, QPainter, QCursor, QColor, QKeySequence
    from PyQt5.QtWidgets import QApplication, QWidget, QMenu, QFileDialog, QMessageBox, QWidgetAction, QSlider, QLabel, QHBoxLayout
    from PyQt5.QtNetwork import QLocalServer
    import tempfile

    class Pin:
        """Logical image, not a native window. All pins share one stable surface."""
        def __init__(self, image, manager, origin=None, initial_scale=1.):
            self.manager = manager
            self.image = image
            self.anchor = None
            self.locked = False
            self.opacity = 1.
            self.min_scale = min(1., initial_scale, 64 / max(image.width(), image.height()))
            self.max_scale = max(1., min(5., 8192 / max(image.width(), image.height()),
                                       math.sqrt(16_000_000 / (image.width() * image.height()))))
            if origin is not None:
                # Area captures stay exactly over the region they came from.
                self.scale = initial_scale
                self.center = QPointF(origin) + QPointF(image.width(), image.height()) * self.scale / 2
                return
            screen = QApplication.screenAt(QCursor.pos()) if POINTER_TRACKED else None
            available = (screen or QApplication.primaryScreen()).availableGeometry()
            self.scale = min(initial_scale, available.width() * .7 / image.width(),
                             available.height() * .7 / image.height())
            width, height = image.width() * self.scale, image.height() * self.scale
            if POINTER_TRACKED:
                point = QPointF(QCursor.pos()) + QPointF(20, 20)
            else:
                # Cascade from the screen center so successive pins stay visible.
                offset = (len(manager.pins) % 5 - 2) * 24
                point = QPointF(available.center()) - QPointF(width, height) / 2 + QPointF(offset, offset)
            x = max(available.left(), min(point.x(), available.right() + 1 - width))
            y = max(available.top(), min(point.y(), available.bottom() + 1 - height))
            self.center = QPointF(x + width / 2, y + height / 2)

        def rect(self):
            width, height = self.image.width() * self.scale, self.image.height() * self.scale
            return QRectF(self.center.x() - width / 2, self.center.y() - height / 2, width, height)

        def begin_drag(self, point):
            if not self.locked:
                self.anchor = QPointF(point) - self.center

        def drag(self, point):
            if self.anchor is not None:
                old = self.rect()
                self.center = QPointF(point) - self.anchor
                self.manager.changed(old, self.rect())

        def end_drag(self):
            self.anchor = None

        def wheelEvent(self, event):
            modifiers = event.modifiers()
            adjusted = modifiers & (Qt.AltModifier | Qt.ShiftModifier)
            angle = event.angleDelta()
            pixel = event.pixelDelta()
            # Qt/X11 can translate modifier+vertical-wheel into horizontal
            # deltas. Treat those as steps only for our modified gestures.
            delta = (angle.y() or (angle.x() if adjusted else 0)) / 120
            if not delta:
                delta = (pixel.y() or (pixel.x() if adjusted else 0)) / 40
            if not delta:
                event.ignore()
                return
            if event.modifiers() & Qt.AltModifier:
                self.set_opacity(self.opacity + delta * .05)
                event.accept()
                return
            if self.locked:
                event.accept()
                return
            old = self.rect()
            old_scale = self.scale
            pointer = QPointF(event.globalPos())
            sensitivity = .035 if event.modifiers() & Qt.ShiftModifier else math.log(1.1)
            self.scale = max(self.min_scale, min(self.max_scale,
                             self.scale * math.exp(max(-10., min(10., delta * sensitivity)))))
            # Preserve the exact source-image point beneath the cursor. All
            # coordinates stay floating point; the native surface never moves.
            self.center = pointer + (self.center - pointer) * (self.scale / old_scale)
            if self.anchor is not None:
                self.anchor = pointer - self.center
            self.manager.changed(old, self.rect())
            event.accept()

        def set_opacity(self, value):
            self.opacity = max(.1, min(1., float(value)))
            self.manager.changed(self.rect(), self.rect())

        def toggle_lock(self, checked):
            self.locked = checked
            self.end_drag()
            self.manager.surface.update_cursor(self)

        def reset_size(self):
            if not self.locked:
                old = self.rect()
                self.scale = 1.
                self.manager.changed(old, self.rect())

        def save(self):
            path, _ = QFileDialog.getSaveFileName(self.manager.surface, tr('Save Image…'),
                                                 str(Path.home() / 'Pictures/pin.png'), 'PNG (*.png)')
            if path and not self.image.save(path, 'PNG'):
                self.manager.error(tr('Could not save the image.'))

        def menu(self, point):
            menu = QMenu(self.manager.surface)
            info = menu.addAction(f'{self.scale * 100:.0f}% · {self.image.width()} × {self.image.height()}')
            info.setEnabled(False)
            menu.addSeparator()
            menu.addAction(tr('Copy'), lambda: QApplication.clipboard().setPixmap(self.image))
            menu.addAction(tr('Save Image…'), self.save)
            menu.addAction(tr('Original Size'), self.reset_size)
            lock = menu.addAction(tr('Lock Position and Size'))
            lock.setCheckable(True)
            lock.setChecked(self.locked)
            lock.triggered.connect(self.toggle_lock)
            menu.addSeparator()
            row = QWidget(menu)
            layout = QHBoxLayout(row)
            label = QLabel(f'{tr("Opacity")} {self.opacity * 100:.0f}%', row)
            slider = QSlider(Qt.Horizontal, row)
            slider.setRange(10, 100)
            slider.setValue(round(self.opacity * 100))
            slider.valueChanged.connect(lambda value: (self.set_opacity(value / 100),
                                                       label.setText(f'{tr("Opacity")} {value}%')))
            layout.addWidget(label)
            layout.addWidget(slider)
            action = QWidgetAction(menu)
            action.setDefaultWidget(row)
            menu.addAction(action)
            menu.addSeparator()
            hint = menu.addAction(tr('Scroll to zoom · Shift: fine zoom · Alt: opacity'))
            hint.setEnabled(False)
            menu.addSeparator()
            menu.addAction(tr('Close'), self.close)
            menu.addAction(tr('Close All Pins'), self.manager.close_all)
            menu.exec_(point)

        def close(self):
            if self in self.manager.pins:
                old = self.rect()
                self.manager.pins.remove(self)
                surface = self.manager.surface
                if surface.active is self:
                    surface.active = None
                self.manager.changed(old, None)
                if not self.manager.pins:
                    surface.release_focus()
                    surface.hide()

    class Surface(QWidget):
        def __init__(self, manager):
            # The overlay is not managed by the window manager: it must not
            # acquire fullscreen tiling, resize constraints or automatic moves.
            super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
                             Qt.X11BypassWindowManagerHint | Qt.NoDropShadowWindowHint)
            self.manager = manager
            self.active = None
            self.setWindowTitle('Image Pin')
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setMouseTracking(True)
            self.setFocusPolicy(Qt.StrongFocus)
            self.input_shape = None
            self.input_rectangles = None
            self.previous_focus = None
            if QApplication.platformName() == 'xcb':
                from x11_input import InputShape
                self.input_shape = InputShape()
            self.fit_desktop()
            # Before mapping, the transparent surface must never grab the
            # entire desktop. Set empty input shape before any pin is shown.
            if self.input_shape:
                self.input_shape.set(self.winId(), [])
            for screen in QApplication.screens():
                screen.geometryChanged.connect(self.fit_desktop)
            QApplication.instance().screenAdded.connect(self.add_screen)
            QApplication.instance().screenRemoved.connect(self.fit_desktop)

        def add_screen(self, screen):
            screen.geometryChanged.connect(self.fit_desktop)
            self.fit_desktop()

        def fit_desktop(self, *args):
            bounds = QRect()
            for screen in QApplication.screens():
                bounds = bounds.united(screen.geometry())
            self.input_rectangles = None
            self.setGeometry(bounds)
            if self.manager.pins:
                self.manager.changed()

        def sync_input(self):
            if not self.input_shape:
                return
            origin = self.geometry().topLeft()
            ratio = self.devicePixelRatioF()
            rectangles = []
            for pin in self.manager.pins:
                rect = pin.rect().translated(-origin.x(), -origin.y()).intersected(QRectF(self.rect()))
                if rect.isEmpty():
                    continue
                x, y = math.floor(rect.x() * ratio), math.floor(rect.y() * ratio)
                right, bottom = math.ceil(rect.right() * ratio), math.ceil(rect.bottom() * ratio)
                rectangles.append((x, y, right - x, bottom - y))
            if rectangles != self.input_rectangles:
                self.input_shape.set(self.winId(), rectangles)
                self.input_rectangles = rectangles

        def paintEvent(self, event):
            painter = QPainter(self)
            painter.setCompositionMode(QPainter.CompositionMode_Source)
            painter.fillRect(event.rect(), Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            origin = self.geometry().topLeft()
            for pin in self.manager.pins:
                target = pin.rect().translated(-origin.x(), -origin.y())
                if target.intersects(QRectF(event.rect())):
                    painter.setOpacity(pin.opacity)
                    painter.drawPixmap(target, pin.image, QRectF(pin.image.rect()))
                    # A pin captured in place is otherwise indistinguishable
                    # from the desktop. Draw a subtle frame just outside it.
                    painter.setOpacity(1.)
                    painter.setPen(QColor(128, 128, 128, 200))
                    painter.drawRect(target.adjusted(-.5, -.5, .5, .5))

        def release_focus(self):
            # Return keyboard focus to the window used before a pin was clicked.
            if self.input_shape and self.previous_focus is not None:
                if self.input_shape.current_focus() == int(self.winId()):
                    self.input_shape.restore_focus(self.previous_focus)
                self.previous_focus = None

        def hit(self, point):
            return next((pin for pin in reversed(self.manager.pins) if pin.rect().contains(QPointF(point))), None)

        def update_cursor(self, pin=None):
            if pin is None or pin.locked:
                self.setCursor(Qt.ArrowCursor)
            else:
                self.setCursor(Qt.ClosedHandCursor if pin.anchor is not None else Qt.OpenHandCursor)

        def mousePressEvent(self, event):
            pin = self.hit(event.globalPos())
            if not pin:
                event.ignore()
                return
            self.active = pin
            self.manager.pins.remove(pin)
            self.manager.pins.append(pin)
            self.setFocus()
            if self.input_shape:
                focused = self.input_shape.current_focus()
                if focused != int(self.winId()):
                    self.previous_focus = focused
                self.input_shape.focus(self.winId())
            if event.button() == Qt.LeftButton:
                pin.begin_drag(event.globalPos())
            self.update_cursor(pin)
            self.manager.changed(pin.rect(), pin.rect())
            event.accept()

        def mouseMoveEvent(self, event):
            if self.active and self.active.anchor is not None:
                self.active.drag(event.globalPos())
                pin = self.active
            else:
                pin = self.hit(event.globalPos())
            self.update_cursor(pin)

        def mouseReleaseEvent(self, event):
            if self.active:
                self.active.end_drag()
            self.update_cursor(self.hit(event.globalPos()))

        def wheelEvent(self, event):
            pin = self.active if self.active and self.active.anchor is not None else self.hit(event.globalPos())
            if pin:
                self.active = pin
                pin.wheelEvent(event)
            else:
                event.ignore()

        def mouseDoubleClickEvent(self, event):
            pin = self.hit(event.globalPos())
            if pin and event.button() == Qt.LeftButton:
                pin.end_drag()
                pin.reset_size()
                self.update_cursor(pin)

        def contextMenuEvent(self, event):
            pin = self.hit(event.globalPos())
            if pin:
                self.active = pin
                pin.menu(event.globalPos())

        def keyPressEvent(self, event):
            if not self.active:
                event.ignore()
                return
            if event.key() == Qt.Key_Escape:
                self.active.close()
                self.release_focus()
            elif event.matches(QKeySequence.Copy):
                QApplication.clipboard().setPixmap(self.active.image)
            else:
                super().keyPressEvent(event)

    class Manager:
        def __init__(self, serve=True):
            self.pins = []
            self.capture_process = None
            self.capture_selector = None
            self.connections = set()
            self.server = QLocalServer()
            self.daemon_lock = None
            if serve:
                import fcntl
                RUNTIME.mkdir(mode=0o700, parents=True, exist_ok=True)
                self.daemon_lock = (RUNTIME / 'image-pin-daemon.lock').open('w')
                try:
                    fcntl.flock(self.daemon_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as error:
                    self.daemon_lock.close()
                    raise RuntimeError('Image Pin is already running') from error
            self.surface = Surface(self)
            if serve:
                # Starts are serialized by launch(); an absent listener is stale.
                QLocalServer.removeServer(str(SOCKET))
                if not self.server.listen(str(SOCKET)):
                    raise RuntimeError(self.server.errorString())
                os.chmod(SOCKET, 0o600)
                self.server.newConnection.connect(self.accept)

        def accept(self):
            while self.server.hasPendingConnections():
                connection = self.server.nextPendingConnection()
                self.connections.add(connection)
                connection.readyRead.connect(lambda c=connection: self.read(c))
                connection.disconnected.connect(lambda c=connection: self.drop(c))
                if connection.bytesAvailable():
                    self.read(connection)

        def drop(self, connection):
            self.connections.discard(connection)
            connection.deleteLater()

        def read(self, connection):
            if not connection.canReadLine():
                return
            try:
                request = json.loads(bytes(connection.readLine()))
                command = request['command']
                set_language(request.get('language', 'system'))
                if command not in {'capture', 'clipboard', 'file', 'close-all', 'reveal', 'shutdown', 'status'}:
                    raise ValueError('Unknown command')
                connection.write(b'OK\n')
                connection.flush()
                connection.disconnectFromServer()
                QTimer.singleShot(0, lambda: self.dispatch(command, request.get('path')))
            except (ValueError, KeyError, TypeError) as error:
                connection.write(str(error).encode())
                connection.disconnectFromServer()

        def dispatch(self, command, path=None):
            try:
                if command == 'capture':
                    self.capture()
                elif command == 'clipboard':
                    image = QApplication.clipboard().pixmap()
                    if image.isNull():
                        urls = QApplication.clipboard().mimeData().urls()
                        if urls and urls[0].isLocalFile():
                            image = QPixmap(urls[0].toLocalFile())
                    self.pin(image)
                elif command == 'file':
                    if not path:
                        path, _ = QFileDialog.getOpenFileName(None, tr('Choose an Image'), str(Path.home()), 'Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif);;All files (*)')
                    if path:
                        self.pin(QPixmap(path))
                elif command == 'close-all':
                    self.close_all()
                elif command == 'reveal':
                    self.reveal()
                elif command == 'shutdown':
                    if self.capture_process:
                        self.capture_process.kill()
                    if self.capture_selector:
                        self.capture_selector.cancel()
                    self.close_all()
                    QApplication.quit()
            except Exception as error:
                self.error(str(error))

        def pin(self, image, origin=None, initial_scale=1.):
            if image.isNull():
                self.error(tr('No image found. Copy an image or choose an image file.'))
                return
            pin = Pin(image, self, origin, initial_scale)
            self.pins.append(pin)
            self.surface.active = pin
            self.changed()
            self.surface.show()
            self.surface.raise_()
            return pin

        def changed(self, old=None, new=None):
            self.surface.sync_input()
            if old is None and new is None:
                self.surface.update()
            else:
                damage = QRectF()
                for rect in (old, new):
                    if rect is not None:
                        damage = damage.united(rect)
                origin = self.surface.geometry().topLeft()
                local = damage.translated(-origin.x(), -origin.y()).toAlignedRect().adjusted(-2, -2, 2, 2)
                self.surface.update(local)

        def reveal(self):
            screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
            available = screen.availableGeometry()
            for index, pin in enumerate(self.pins):
                old = pin.rect()
                pin.scale = min(pin.scale, available.width() * .7 / pin.image.width(),
                                available.height() * .7 / pin.image.height())
                offset = (index % 5 - 2) * 24
                pin.center = QPointF(available.center()) + QPointF(offset, offset)
                self.changed(old, pin.rect())
            if self.pins:
                self.surface.show()
                self.surface.raise_()

        def close_all(self):
            for pin in list(self.pins):
                pin.close()

        def error(self, message):
            # A desktop notification never blocks pins or incoming requests.
            notify = shutil.which('notify-send')
            if notify:
                # Detached, so the resident helper never accumulates zombies.
                started = QProcess.startDetached(notify, ['--app-name=Image Pin', '--icon=dialog-warning',
                                                          'Image Pin', message])
                if started[0] if isinstance(started, tuple) else started:
                    return
            box = QMessageBox(QMessageBox.Warning, 'Image Pin', message)
            box.setAttribute(Qt.WA_DeleteOnClose)
            box.setModal(False)
            box.show()
            self.message_box = box

        def capture(self):
            if self.capture_process or self.capture_selector:
                return
            self.capture_dir = tempfile.TemporaryDirectory(prefix='image-pin-', dir=RUNTIME)
            destination = str(Path(self.capture_dir.name) / 'capture.png')
            process = QProcess()
            self.capture_process = process
            timer = QTimer(process)
            timer.setSingleShot(True)
            timer.timeout.connect(process.kill)
            process.finished.connect(lambda code, status: self.capture_done(process, destination, code))
            process.errorOccurred.connect(lambda error: self.capture_failed(process, error))
            # Freeze once, then select ourselves so the capture retains its
            # normalized top-left instead of using the cursor at drag release.
            process.start('gnome-screenshot', ['--file', destination])
            timer.start(120000)

        def capture_failed(self, process, error):
            if error == QProcess.FailedToStart:
                self.error(tr('Could not start GNOME Screenshot. Install gnome-screenshot and try again.'))
                self.cleanup_capture(process)

        def capture_done(self, process, destination, code):
            if self.capture_process is not process:
                return
            if Path(destination).exists():
                # Loading through QImage avoids Qt's automatic file-backed
                # pixmap cache retaining the full desktop snapshot afterward.
                image = QPixmap.fromImage(QImage(destination))
                self.cleanup_capture(process)
                if image.isNull():
                    self.error(tr('Capture failed: {detail}', detail=tr('No image found. Copy an image or choose an image file.')))
                    return
                self.select_capture(image)
                return
            elif code != 0:
                detail = bytes(process.readAllStandardError()).decode(errors='replace').strip()
                # A cancelled screenshot backend need not show an error.
                if detail and 'cancel' not in detail.lower():
                    self.error(tr('Capture failed: {detail}', detail=detail[-500:]))
            self.cleanup_capture(process)

        def select_capture(self, image):
            from capture_selector import CaptureSelector
            selector = CaptureSelector(image, self.surface.geometry())
            self.capture_selector = selector
            selector.selected.connect(self.capture_selected)
            selector.cancelled.connect(self.cleanup_selector)
            selector.show()
            selector.raise_()
            selector.activateWindow()
            selector.setFocus()
            if self.surface.input_shape:
                self.surface.input_shape.focus(selector.winId())

        def capture_selected(self, image, origin, initial_scale):
            self.cleanup_selector()
            self.pin(image, origin, initial_scale)

        def cleanup_selector(self):
            selector = self.capture_selector
            self.capture_selector = None
            if selector:
                selector.hide()
                selector.deleteLater()

        def cleanup_capture(self, process):
            self.capture_dir.cleanup()
            self.capture_process = None
            process.deleteLater()

    return QApplication, Manager, Pin


def main():
    parser = argparse.ArgumentParser()
    version = tomllib.loads((PROJECT / 'pyproject.toml').read_text())['project']['version']
    parser.add_argument('--version', action='version', version=f'Image Pin {version}')
    parser.add_argument('command', choices=['capture', 'clipboard', 'file', 'close-all', 'reveal', 'daemon', 'shutdown', 'status'])
    parser.add_argument('path', nargs='?')
    parser.add_argument('--language', choices=['system', 'en', 'ko'], default='system')
    args = parser.parse_args()
    if args.command != 'daemon':
        if args.command in {'shutdown', 'status'}:
            send(args.command, args.path, args.language)
        else:
            launch(args.command, args.path, args.language)
        return
    set_language(args.language)
    QApplication, Manager, _ = gui_types()
    app = QApplication(['image-pin'])
    app.setApplicationName('Image Pin')
    app.setQuitOnLastWindowClosed(False)
    manager = Manager()
    try:
        app.exec_()
    finally:
        manager.server.close()
        if manager.daemon_lock:
            manager.daemon_lock.close()
        manager.surface.hide()
        manager.cleanup_selector()
        if manager.surface.input_shape:
            manager.surface.input_shape.close()
        if manager.capture_process:
            manager.capture_process.kill()
            manager.capture_process.waitForFinished(1000)
            manager.capture_dir.cleanup()
        QLocalServer = __import__('PyQt5.QtNetwork', fromlist=['QLocalServer']).QLocalServer
        QLocalServer.removeServer(str(SOCKET))


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError) as error:
        raise SystemExit(f'Image Pin: {error}')
