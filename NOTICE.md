# Licenses and acknowledgments

The Python helper, root scripts and documentation are GPL-3.0-only; see LICENSE.
The independent TypeScript launcher wrapper and its icon under `extension/` are
MIT-licensed; see extension/LICENSE. The wrapper invokes the helper as a separate
executable through command-line arguments and does not import the helper.

PyQt5 is provided under GPLv3 or a commercial license. Its binary wheels include
Qt under its own license. These dependencies are installed separately through uv,
with versions and hashes recorded in uv.lock; they are not included in source
release archives. See https://www.riverbankcomputing.com/software/pyqt/intro.

The interaction idea was informed by Smooth Push Zoom:
https://github.com/jinkim0823/smooth-push-zoom
No source from that extension is copied into the current renderer. Its animated
native magnifier approach differs from this fixed-surface image overlay.

The X11 input-shape implementation follows the SHAPE 1.1 protocol and uses the
system's libX11 and libXext libraries. No library code is included in this repository.
