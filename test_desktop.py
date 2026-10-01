"""XWayland regression using only generated windows and images.

Tests server-side ConfigureNotify, real pointer routing and input shape.
The pointer is restored after the bounded test. No desktop content is captured.
"""
import os
os.environ['QT_QPA_PLATFORM'] = 'xcb'
import ctypes as C
import subprocess
from PyQt5.QtCore import Qt, QPoint, QPointF
from PyQt5.QtGui import QPixmap, QColor, QWheelEvent
from PyQt5.QtWidgets import QWidget
from PyQt5.QtTest import QTest
from image_pin import gui_types

Application, Manager, _ = gui_types()
app = Application([])
app.setQuitOnLastWindowClosed(False)


class Probe(QWidget):
    def __init__(self):
        # Keep the owned fixture above pre-existing pinned images, while the
        # new test surface is raised above it. No real application receives
        # simulated clicks even when the user has pins open during testing.
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint |
                         Qt.WindowStaysOnTopHint | Qt.X11BypassWindowManagerHint)
        self.setWindowTitle('Image Pin isolated input test')
        self.setGeometry(200, 200, 360, 240)
        self.setStyleSheet('background: #253047;')
        self.clicks = 0

    def mousePressEvent(self, event):
        self.clicks += 1
        event.accept()


def command(*args):
    subprocess.run(['xdotool', *map(str, args)], check=True, capture_output=True)
    QTest.qWait(25)


pointer = subprocess.check_output(['xdotool', 'getmouselocation', '--shell'], text=True)
pointer = dict(line.split('=', 1) for line in pointer.splitlines())
manager = Manager(serve=False)
probe = Probe()
try:
    probe.show()
    probe.raise_()
    app.processEvents()
    image = QPixmap(200, 100)
    image.fill(QColor('#ff426b'))
    pin = manager.pin(image)
    pin.center = QPointF(380, 320)
    manager.changed()
    surface = manager.surface
    app.processEvents()
    QTest.qWait(70)
    wid = int(surface.winId())
    native_geometry = surface.geometry()
    shape = surface.input_shape
    x11 = shape.x11
    x11.XSelectInput.argtypes = [C.c_void_p, C.c_ulong, C.c_long]
    x11.XPending.argtypes = [C.c_void_p]
    x11.XSync.argtypes = [C.c_void_p, C.c_int]
    x11.XNextEvent.argtypes = [C.c_void_p, C.c_void_p]
    x11.XSelectInput(shape.display, wid, 1 << 17)  # StructureNotifyMask
    x11.XSync(shape.display, 0)
    event = (C.c_long * 24)()
    while x11.XPending(shape.display):
        x11.XNextEvent(shape.display, C.byref(event))
    changes = 0
    for delta in [120] * 12 + [-120] * 12:
        point = pin.center
        wheel = QWheelEvent(point - QPointF(surface.pos()), point, QPoint(), QPoint(0, delta),
                            Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
        surface.wheelEvent(wheel)
        QTest.qWait(8)
        x11.XSync(shape.display, 0)
        while x11.XPending(shape.display):
            x11.XNextEvent(shape.display, C.byref(event))
            if C.cast(C.byref(event), C.POINTER(C.c_int))[0] == 22:
                changes += 1
        assert surface.geometry() == native_geometry
    assert changes == 0, changes
    print('Server ConfigureNotify during 24 zoom inputs: 0')

    # The input region must be the image only, not the screen-sized surface.
    rectangles = shape.get(wid)
    expected = pin.rect().translated(-surface.x(), -surface.y()).toAlignedRect()
    assert len(rectangles) == 1, rectangles
    x, y, width, height = rectangles[0]
    assert abs(x - expected.x()) <= 1 and abs(y - expected.y()) <= 1
    assert abs(width - expected.width()) <= 1 and abs(height - expected.height()) <= 1
    print('Input-only shape follows image bounds: PASS')

    # A real click through the transparent part goes to our owned test window.
    command('mousemove', 220, 220)
    command('click', 1)
    assert probe.clicks == 1, probe.clicks
    print('Real click outside image reaches underlying test window: PASS')

    # Real mouse grab, movement and wheel can be combined.
    command('mousemove', 380, 320)
    command('mousedown', 1)
    assert pin.anchor is not None
    command('mousemove', 420, 345)
    assert pin.center == QPointF(420, 345), pin.center
    before = pin.scale
    command('click', 4)
    assert pin.scale > before
    assert pin.center == QPointF(420, 345)
    command('mouseup', 1)
    assert pin.anchor is None
    focus = subprocess.check_output(['xdotool', 'getwindowfocus'], text=True).strip()
    assert int(focus) == wid, (focus, wid)
    # Opacity uses actual Alt+wheel input and must preserve image geometry.
    old_rect, old_scale = pin.rect(), pin.scale
    command('keydown', 'Alt_L')
    try:
        command('click', 5)
    finally:
        command('keyup', 'Alt_L')
    assert abs(pin.opacity - .95) < 1e-9, pin.opacity
    assert pin.rect() == old_rect and pin.scale == old_scale
    assert surface.geometry() == native_geometry
    print('Real Alt+wheel adjusts only opacity: PASS')
    old_scale = pin.scale
    command('keydown', 'Shift_L')
    try:
        command('click', 4)
    finally:
        command('keyup', 'Shift_L')
    assert 1 < pin.scale / old_scale < 1.1
    assert surface.geometry() == native_geometry
    print('Real Shift+wheel uses fine zoom: PASS')
    command('key', 'Escape')
    assert not manager.pins
    assert not surface.isVisible()
    print('Real drag + wheel + focus + Escape: PASS')

    # The area selector owns its frozen, generated background. Every drag
    # direction must place the pin beside the normalized selection origin,
    # never beside the release point. This does not capture desktop content.
    snapshot = QPixmap(surface.size())
    snapshot.fill(QColor('#253047'))
    for start, end in (((260, 240), (460, 340)), ((460, 340), (260, 240))):
        manager.select_capture(snapshot)
        QTest.qWait(70)
        command('mousemove', *start)
        # XTest pointer warps cross a newly mapped XWayland surface; allow
        # Mutter to deliver the matching enter/motion before the press.
        QTest.qWait(70)
        command('mousedown', 1)
        command('mousemove', *end)
        command('mouseup', 1)
        assert manager.capture_selector is None
        assert len(manager.pins) == 1
        pin = manager.pins[0]
        assert pin.rect().topLeft() == QPointF(280, 260), pin.rect()
        assert pin.image.width() == 200 and pin.image.height() == 100
        assert surface.geometry() == native_geometry
        manager.close_all()
    manager.select_capture(snapshot)
    QTest.qWait(70)
    command('key', 'Escape')
    assert manager.capture_selector is None and not manager.pins
    print('Real area selection retains top-left in both directions; Escape cancels: PASS')
finally:
    manager.cleanup_selector()
    manager.close_all()
    manager.surface.hide()
    if manager.surface.input_shape:
        manager.surface.input_shape.close()
    probe.close()
    app.processEvents()
    subprocess.run(['xdotool', 'mousemove', pointer['X'], pointer['Y']], check=True, capture_output=True)
