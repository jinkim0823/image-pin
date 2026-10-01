# SPDX-License-Identifier: GPL-3.0-only
"""X11 input-only shape: keep a fixed visual surface click-through outside pins."""
import ctypes as C

# Xlib's default handler exits the process on any protocol error, such as
# restoring focus to a window that closed meanwhile. Ignore errors instead.
_ErrorHandler = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_void_p)
_ignore_errors = _ErrorHandler(lambda display, event: 0)


class XRectangle(C.Structure):
    _fields_ = [('x', C.c_short), ('y', C.c_short),
                ('width', C.c_ushort), ('height', C.c_ushort)]


class InputShape:
    def __init__(self):
        self.x11 = C.CDLL('libX11.so.6')
        self.ext = C.CDLL('libXext.so.6')
        self.x11.XOpenDisplay.argtypes = [C.c_char_p]
        self.x11.XOpenDisplay.restype = C.c_void_p
        self.x11.XFlush.argtypes = [C.c_void_p]
        self.x11.XCloseDisplay.argtypes = [C.c_void_p]
        self.x11.XSetInputFocus.argtypes = [C.c_void_p, C.c_ulong, C.c_int, C.c_ulong]
        self.x11.XGetInputFocus.argtypes = [C.c_void_p, C.POINTER(C.c_ulong), C.POINTER(C.c_int)]
        self.x11.XSetErrorHandler.argtypes = [_ErrorHandler]
        self.x11.XSetErrorHandler.restype = C.c_void_p
        self.x11.XSetErrorHandler(_ignore_errors)
        self.ext.XShapeQueryVersion.argtypes = [C.c_void_p, C.POINTER(C.c_int), C.POINTER(C.c_int)]
        self.ext.XShapeCombineRectangles.argtypes = [C.c_void_p, C.c_ulong, C.c_int, C.c_int,
                                                    C.c_int, C.POINTER(XRectangle), C.c_int,
                                                    C.c_int, C.c_int]
        self.ext.XShapeGetRectangles.argtypes = [C.c_void_p, C.c_ulong, C.c_int,
                                                C.POINTER(C.c_int), C.POINTER(C.c_int)]
        self.ext.XShapeGetRectangles.restype = C.POINTER(XRectangle)
        self.x11.XFree.argtypes = [C.c_void_p]
        self.display = self.x11.XOpenDisplay(None)
        if not self.display:
            raise RuntimeError('XWayland display is unavailable')
        major, minor = C.c_int(), C.c_int()
        if not self.ext.XShapeQueryVersion(self.display, C.byref(major), C.byref(minor)) or (major.value, minor.value) < (1, 1):
            self.close()
            raise RuntimeError('X11 SHAPE 1.1 is required for input-only regions')

    def set(self, window, rectangles):
        data = (XRectangle * len(rectangles))(*(XRectangle(*r) for r in rectangles))
        # ShapeInput=2, ShapeSet=0, Unsorted=0. Never touch the visual bounding
        # shape: the compositor sees exactly the same surface at every scale.
        self.ext.XShapeCombineRectangles(self.display, int(window), 2, 0, 0, data, len(data), 0, 0)
        self.x11.XFlush(self.display)

    def get(self, window):
        count, ordering = C.c_int(), C.c_int()
        data = self.ext.XShapeGetRectangles(self.display, int(window), 2, C.byref(count), C.byref(ordering))
        result = [(data[i].x, data[i].y, data[i].width, data[i].height) for i in range(count.value)]
        if data:
            self.x11.XFree(data)
        return result

    def focus(self, window):
        self.x11.XSetInputFocus(self.display, int(window), 1, 0)
        self.x11.XFlush(self.display)

    def current_focus(self):
        window, revert = C.c_ulong(), C.c_int()
        self.x11.XGetInputFocus(self.display, C.byref(window), C.byref(revert))
        return window.value

    def restore_focus(self, window):
        # None (0) and PointerRoot (1) are not windows; PointerRoot lets the
        # window manager choose. A window closed meanwhile is ignored above.
        self.x11.XSetInputFocus(self.display, window if window > 1 else 1, 1, 0)
        self.x11.XFlush(self.display)

    def close(self):
        if self.display:
            self.x11.XCloseDisplay(self.display)
            self.display = None
