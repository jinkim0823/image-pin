"""Interaction/render regressions; never capture the user's desktop."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt, QPoint, QPointF, QRect, QEvent
from PySide6.QtGui import QPixmap, QColor, QMouseEvent, QWheelEvent, QCursor
from PySide6.QtTest import QTest
from image_pin import gui_types

Application, Manager, Pin = gui_types()
app = Application([])
app.setQuitOnLastWindowClosed(False)


class PinTests(unittest.TestCase):
    def setUp(self):
        self.manager = Manager(serve=False)
        self.image = QPixmap(200, 100)
        self.image.fill(QColor('blue'))

    def tearDown(self):
        self.manager.cleanup_selector()
        self.manager.close_all()
        surface = self.manager.surface
        surface.hide()
        if surface.input_shape:
            surface.input_shape.close()
        surface.deleteLater()
        app.processEvents()

    def pin(self):
        pin = self.manager.pin(self.image)
        app.processEvents()
        return pin

    def wheel(self, pin, delta=120, point=None, modifiers=Qt.KeyboardModifier.NoModifier):
        point = QPointF(point or pin.center)
        origin = self.manager.surface.geometry().topLeft()
        event = QWheelEvent(point - QPointF(origin), point, QPoint(), QPoint(0, delta),
                            Qt.MouseButton.NoButton, modifiers, Qt.ScrollPhase.NoScrollPhase, False)
        self.manager.surface.wheelEvent(event)

    def mouse(self, kind, point, button, buttons):
        surface = self.manager.surface
        point = QPointF(point)
        event = QMouseEvent(kind, point - QPointF(surface.pos()), point, button, buttons, Qt.KeyboardModifier.NoModifier)
        {QEvent.Type.MouseButtonPress: surface.mousePressEvent,
         QEvent.Type.MouseMove: surface.mouseMoveEvent,
         QEvent.Type.MouseButtonRelease: surface.mouseReleaseEvent}[kind](event)

    def test_wheel_does_not_change_native_geometry_or_center(self):
        pin = self.pin()
        native = self.manager.surface.geometry()
        center = QPointF(pin.center)
        for delta in [120, 240, -120, 24, -240] * 6:
            self.wheel(pin, delta)
            QTest.qWait(2)
            self.assertEqual(self.manager.surface.geometry(), native)
            self.assertEqual(pin.center, center)
            self.assertEqual(pin.rect().center(), center)
        geometry = pin.rect()
        QTest.qWait(100)
        self.assertEqual(pin.rect(), geometry)
        self.assertEqual(self.manager.surface.geometry(), native)

    def source_at(self, pin, point):
        return (QPointF(point) - pin.rect().topLeft()) / pin.scale

    def assert_point_close(self, actual, expected):
        self.assertAlmostEqual(actual.x(), expected.x(), places=8)
        self.assertAlmostEqual(actual.y(), expected.y(), places=8)

    def test_cursor_anchor_survives_repeated_zoom_and_direction_changes(self):
        pin = self.pin()
        native = self.manager.surface.geometry()
        point = pin.center + QPointF(60, 30)
        original_source = self.source_at(pin, point)
        for delta in [120] * 6 + [-120] * 6 + [24, -24] * 5:
            self.wheel(pin, delta, point=point)
            self.assert_point_close(self.source_at(pin, point), original_source)
            self.assertEqual(self.manager.surface.geometry(), native)
        for delta in [120, -120, 240, -240]:
            point = pin.rect().topLeft() + QPointF(pin.rect().width() * .2, pin.rect().height() * .8)
            source = self.source_at(pin, point)
            self.wheel(pin, delta, point=point)
            self.assert_point_close(self.source_at(pin, point), source)

    def test_drag_and_cursor_zoom_keep_grabbed_image_point(self):
        pin = self.pin()
        native = self.manager.surface.geometry()
        press = pin.center + QPointF(20, 15)
        source = self.source_at(pin, press)
        self.mouse(QEvent.Type.MouseButtonPress, press, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton)
        self.wheel(pin, point=press)
        self.assertAlmostEqual(pin.scale, 1.1)
        self.assert_point_close(self.source_at(pin, press), source)
        self.assert_point_close(pin.center + pin.anchor, press)
        moved = press + QPointF(40, 30)
        self.mouse(QEvent.Type.MouseMove, moved, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton)
        self.assert_point_close(self.source_at(pin, moved), source)
        self.wheel(pin, -120, point=moved)
        self.assertAlmostEqual(pin.scale, 1.)
        self.assert_point_close(self.source_at(pin, moved), source)
        self.assertEqual(self.manager.surface.geometry(), native)
        self.mouse(QEvent.Type.MouseButtonRelease, moved, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton)
        self.assertIsNone(pin.anchor)

    def test_lock_blocks_resize_and_drag(self):
        pin = self.pin()
        pin.toggle_lock(True)
        before = pin.rect()
        self.wheel(pin)
        pin.begin_drag(pin.center)
        pin.drag(pin.center + QPointF(100, 100))
        self.assertEqual(pin.rect(), before)

    def test_immediate_steps_fine_control_reset_and_limits(self):
        pin = self.pin()
        self.wheel(pin)
        self.assertAlmostEqual(pin.scale, 1.1)
        pin.reset_size()
        self.wheel(pin, modifiers=Qt.KeyboardModifier.ShiftModifier)
        self.assertGreater(pin.scale, 1.)
        self.assertLess(pin.scale, 1.1)
        self.wheel(pin, -120000)
        self.assertEqual(pin.scale, pin.min_scale)
        self.assertAlmostEqual(pin.rect().width() / pin.rect().height(), 2.)
        self.assertGreaterEqual(max(pin.rect().width(), pin.rect().height()), 64)
        center = QPointF(pin.center)
        pin.reset_size()
        self.assertEqual(pin.scale, 1.)
        self.assertEqual(pin.center, center)

    def test_transparent_canvas_no_border_and_old_pixels_cleared(self):
        pin = self.pin()
        surface = self.manager.surface
        origin = QPointF(surface.pos())
        image = surface.grab().toImage()
        corner = (pin.rect().topLeft() - origin + QPointF(1, 1)).toPoint()
        middle = (pin.center - origin).toPoint()
        self.assertEqual(image.pixelColor(corner), QColor('blue'))
        self.assertEqual(image.pixelColor(middle), QColor('blue'))
        empty = QPoint(0, 0)
        self.assertEqual(image.pixelColor(empty).alpha(), 0)
        pin.close()
        app.processEvents()
        cleared = surface.grab().toImage()
        self.assertEqual(cleared.pixelColor(middle).alpha(), 0)
        self.assertEqual(surface.toolTip(), '')

    def test_multiple_images_overlap_hit_order_and_escape(self):
        first = self.pin()
        second = self.pin()
        second.center = QPointF(first.center)
        self.assertIs(self.manager.surface.hit(first.center), second)
        self.manager.surface.active = second
        QTest.keyClick(self.manager.surface, Qt.Key.Key_Escape)
        self.assertEqual(self.manager.pins, [first])
        self.assertIs(self.manager.surface.hit(first.center), first)
        first.close()
        self.assertFalse(self.manager.surface.isVisible())

    def test_opacity_wheel_does_not_zoom_or_move_and_preserves_source(self):
        pin = self.pin()
        original = pin.image.toImage()
        rect, native = pin.rect(), self.manager.surface.geometry()
        self.wheel(pin, -120, modifiers=Qt.KeyboardModifier.AltModifier)
        self.assertAlmostEqual(pin.opacity, .95)
        self.assertEqual(pin.rect(), rect)
        self.assertEqual(self.manager.surface.geometry(), native)
        pin.set_opacity(.5)
        rendered = self.manager.surface.grab().toImage()
        local = (pin.center - QPointF(self.manager.surface.pos())).toPoint()
        self.assertAlmostEqual(rendered.pixelColor(local).alpha(), 128, delta=1)
        self.assertEqual(pin.image.toImage(), original)
        pin.set_opacity(0)
        self.assertEqual(pin.opacity, .1)
        pin.set_opacity(2)
        self.assertEqual(pin.opacity, 1.)
        pin.toggle_lock(True)
        self.wheel(pin, -120, modifiers=Qt.KeyboardModifier.AltModifier)
        self.assertAlmostEqual(pin.opacity, .95)
        self.assertEqual(pin.rect(), rect)

    def test_modifier_wheel_horizontal_translation(self):
        pin = self.pin()
        native = self.manager.surface.geometry()
        point = pin.center
        surface = self.manager.surface
        for modifiers in (Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.AltModifier, Qt.KeyboardModifier.ShiftModifier):
            event = QWheelEvent(point - QPointF(surface.pos()), point, QPoint(), QPoint(-120, 0),
                                Qt.MouseButton.NoButton, modifiers, Qt.ScrollPhase.NoScrollPhase, False)
            surface.wheelEvent(event)
        self.assertAlmostEqual(pin.opacity, .95)
        self.assertGreater(pin.scale, .95)
        self.assertLess(pin.scale, 1.)
        self.assertEqual(surface.geometry(), native)

    def test_opacity_menu_slider_updates_pin(self):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QMenu, QSlider
        pin = self.pin()
        result = []
        def operate_menu():
            menu = app.activePopupWidget()
            self.assertIsInstance(menu, QMenu)
            sliders = menu.findChildren(QSlider)
            self.assertEqual(len(sliders), 1)
            sliders[0].setValue(40)
            result.append(pin.opacity)
            menu.close()
        QTimer.singleShot(10, operate_menu)
        pin.menu(pin.center.toPoint())
        self.assertEqual(result, [.4])

    def test_reveal_recovers_offscreen_pins_without_native_resize(self):
        pin = self.pin()
        pin.center = QPointF(-10000, -10000)
        pin.scale = pin.max_scale
        pin.toggle_lock(True)
        native = self.manager.surface.geometry()
        self.manager.reveal()
        screen = app.screenAt(pin.center.toPoint())
        self.assertIsNotNone(screen)
        self.assertTrue(screen.availableGeometry().contains(pin.rect().toAlignedRect()))
        self.assertTrue(pin.locked)
        self.assertEqual(self.manager.surface.geometry(), native)

    def test_daemon_exclusion_preserves_existing_socket(self):
        import image_pin
        from PySide6.QtNetwork import QLocalServer
        with TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            path = runtime / 'image-pin.sock'
            with patch.object(image_pin, 'RUNTIME', runtime), patch.object(image_pin, 'SOCKET', path):
                first = Manager(serve=True)
                try:
                    self.assertTrue(path.exists())
                    with self.assertRaisesRegex(RuntimeError, 'already running'):
                        Manager(serve=True)
                    self.assertTrue(path.exists())
                finally:
                    first.server.close()
                    first.daemon_lock.close()
                    first.surface.hide()
                    first.surface.deleteLater()
                    QLocalServer.removeServer(str(path))

    def test_rejected_request_never_starts_second_daemon(self):
        import image_pin
        with patch.object(image_pin, 'send', side_effect=RuntimeError('Unknown command')):
            with patch.object(image_pin.subprocess, 'Popen') as start:
                with self.assertRaisesRegex(RuntimeError, 'Unknown command'):
                    image_pin.launch('reveal')
                start.assert_not_called()

    def test_language_selection_and_fallback(self):
        from i18n import tr, set_language
        try:
            set_language('en')
            self.assertEqual(tr('Copy'), 'Copy')
            set_language('ko')
            self.assertEqual(tr('Copy'), '복사')
            self.assertEqual(tr('Capture failed: {detail}', detail='test'), '캡처 실패: test')
            self.assertEqual(tr('Untranslated'), 'Untranslated')
        finally:
            set_language('system')

    def test_clipboard_roundtrip_and_empty(self):
        app.clipboard().setPixmap(self.image)
        self.manager.dispatch('clipboard')
        self.assertEqual(len(self.manager.pins), 1)
        app.clipboard().clear()
        with patch.object(self.manager, 'error') as error:
            self.manager.dispatch('clipboard')
            error.assert_called_once()
        self.assertEqual(len(self.manager.pins), 1)

    def test_capture_consumes_and_removes_temporary_file(self):
        from PySide6.QtCore import QProcess
        directory = TemporaryDirectory()
        destination = Path(directory.name) / 'capture.png'
        self.image.save(str(destination))
        process = QProcess()
        self.manager.capture_dir = directory
        self.manager.capture_process = process
        self.manager.capture_done(process, str(destination), 0)
        self.assertFalse(self.manager.pins)
        self.assertIsNotNone(self.manager.capture_selector)
        self.assertFalse(destination.exists())
        self.assertIsNone(self.manager.capture_process)

    def test_capture_uses_selected_top_left_for_every_drag_direction(self):
        snapshot = QPixmap(app.primaryScreen().geometry().size())
        snapshot.fill(QColor('#ff426b'))
        for start, end in (
            (QPoint(120, 140), QPoint(320, 240)),
            (QPoint(320, 240), QPoint(120, 140)),
            (QPoint(120, 240), QPoint(320, 140)),
            (QPoint(320, 140), QPoint(120, 240)),
        ):
            with self.subTest(start=start, end=end):
                self.manager.select_capture(snapshot)
                selector = self.manager.capture_selector
                with patch.object(QCursor, 'pos', return_value=QPoint(700, 500)):
                    press = QMouseEvent(QEvent.Type.MouseButtonPress, start, start,
                                        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
                    release = QMouseEvent(QEvent.Type.MouseButtonRelease, end, end,
                                          Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
                    selector.mousePressEvent(press)
                    selector.mouseReleaseEvent(release)
                pin = self.manager.pins[-1]
                self.assertEqual(pin.rect().topLeft(), QPointF(120, 140))
                self.assertEqual(pin.image.size(), QRect(0, 0, 200, 100).size())
                self.assertEqual(pin.image.toImage().pixelColor(0, 0), QColor('#ff426b'))
                self.assertIsNone(self.manager.capture_selector)
                self.manager.close_all()

    def test_error_uses_detached_notification_without_blocking(self):
        import image_pin
        from PySide6.QtCore import QProcess
        with patch.object(image_pin.shutil, 'which', return_value='/usr/bin/notify-send'), \
             patch.object(QProcess, 'startDetached', return_value=True) as start:
            self.manager.error('test message')
        program, arguments = start.call_args.args
        self.assertEqual(program, '/usr/bin/notify-send')
        self.assertEqual(arguments[-1], 'test message')
        self.assertIsNone(app.activeModalWidget())
        with patch.object(image_pin.shutil, 'which', return_value=None):
            self.manager.error('fallback message')
        box = self.manager.message_box
        self.assertTrue(box.isVisible())
        self.assertFalse(box.isModal())
        self.assertIsNone(app.activeModalWidget())
        box.close()

    def test_untracked_pointer_places_pins_from_screen_center(self):
        import image_pin
        available = app.primaryScreen().availableGeometry()
        with patch.object(image_pin, 'POINTER_TRACKED', False), \
             patch.object(QCursor, 'pos', return_value=QPoint(-5000, -5000)):
            first = self.pin()
            second = self.pin()
        self.assertTrue(available.contains(first.rect().toAlignedRect()))
        self.assertTrue(available.contains(second.rect().toAlignedRect()))
        self.assertNotEqual(first.center, second.center)
        middle = QPointF(available.center())
        self.assertLess((first.center - middle).manhattanLength(), 120)

    def test_pin_frame_is_drawn_just_outside_the_image(self):
        self.manager.pin(self.image, QPointF(100, 100), 1.)
        surface = self.manager.surface
        origin = surface.geometry().topLeft()
        pixels = surface.grab().toImage()
        inside = QPoint(100, 100) - origin
        frame = QPoint(99, 99) - origin
        self.assertEqual(pixels.pixelColor(inside), QColor('blue'))
        self.assertGreater(pixels.pixelColor(frame).alpha(), 0)
        self.assertNotEqual(pixels.pixelColor(frame), QColor('blue'))

    def test_capture_maps_scaled_snapshot_and_negative_desktop_origin(self):
        from capture_selector import CaptureSelector
        snapshot = QPixmap(400, 300)
        snapshot.fill(QColor('green'))
        pixels = snapshot.toImage()
        pixels.setPixelColor(40, 40, QColor('red'))
        pixels.setPixelColor(279, 219, QColor('blue'))
        snapshot = QPixmap.fromImage(pixels)
        selector = CaptureSelector(snapshot, QRect(-100, -50, 200, 150))
        selected = []
        selector.selected.connect(lambda *args: selected.append(args))
        start, end = QPoint(40, 60), QPoint(-80, -30)
        selector.mousePressEvent(QMouseEvent(QEvent.Type.MouseButtonPress, start, start,
                                            Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
        selector.mouseReleaseEvent(QMouseEvent(QEvent.Type.MouseButtonRelease, end, end,
                                              Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))
        self.assertEqual(len(selected), 1)
        image, origin, scale = selected[0]
        self.assertEqual(origin, QPointF(-80, -30))
        self.assertEqual(image.size(), QRect(0, 0, 240, 180).size())
        self.assertEqual(scale, .5)
        self.assertEqual(image.devicePixelRatioF(), 1.)
        self.assertEqual(image.toImage().pixelColor(0, 0), QColor('red'))
        self.assertEqual(image.toImage().pixelColor(239, 179), QColor('blue'))
        self.assertTrue(selector.snapshot.isNull())
        selector.deleteLater()

    def test_selector_dims_only_after_drag_begins(self):
        from capture_selector import CaptureSelector
        snapshot = QPixmap(200, 150)
        snapshot.fill(QColor('#4080c0'))
        selector = CaptureSelector(snapshot, QRect(0, 0, 200, 150))
        # Mapping must not change the visible desktop before any drag.
        self.assertEqual(selector.grab().toImage().pixelColor(10, 10), QColor('#4080c0'))
        start, end = QPoint(50, 50), QPoint(120, 100)
        selector.mousePressEvent(QMouseEvent(QEvent.Type.MouseButtonPress, start, start,
                                            Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
        selector.mouseMoveEvent(QMouseEvent(QEvent.Type.MouseMove, end, end,
                                           Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
        pixels = selector.grab().toImage()
        self.assertNotEqual(pixels.pixelColor(10, 10), QColor('#4080c0'))
        self.assertEqual(pixels.pixelColor(80, 75), QColor('#4080c0'))
        selector.cancel()
        selector.deleteLater()

    def test_cancel_own_selector_creates_no_pin(self):
        self.manager.select_capture(self.image)
        selector = self.manager.capture_selector
        QTest.keyClick(selector, Qt.Key.Key_Escape)
        self.assertIsNone(self.manager.capture_selector)
        self.assertFalse(self.manager.pins)
        self.manager.select_capture(self.image)
        self.manager.capture_selector.close()
        self.assertIsNone(self.manager.capture_selector)
        self.assertFalse(self.manager.pins)

    def test_capture_cancel_leaves_no_pin(self):
        from PySide6.QtCore import QProcess
        directory = TemporaryDirectory()
        process = QProcess()
        self.manager.capture_dir = directory
        self.manager.capture_process = process
        with patch.object(self.manager, 'error') as error:
            self.manager.capture_done(process, str(Path(directory.name) / 'missing.png'), 0)
            error.assert_not_called()
        self.assertFalse(Path(directory.name).exists())
        self.assertFalse(self.manager.pins)


if __name__ == '__main__':
    unittest.main()
