# Changelog

## 0.1.0

- Area capture, clipboard images and existing image files through Vicinae.
- Area pins stay exactly over the selected region, including reverse drags,
  with a thin frame distinguishing every pin from the desktop. A frozen-snapshot selector retains the capture coordinates
  and dims the desktop only after a drag begins.
- Cursor-centered zoom, fine zoom and resizing while dragging.
- Stable transparent overlay with image-only input regions.
- Per-image opacity slider and Alt+wheel adjustment.
- English/Korean helper menus and extension language preference.
- Bring Pins into View recovery command.
- Built on Qt 6 through PySide6-Essentials; Qt 5.15 no longer receives
  open-source updates.
- The installer lists every missing prerequisite with a ready-to-run
  `apt` command instead of stopping at the first one.
- `install.sh --helper-only` installs the helper without Node.js or Vicinae.
- Keyboard input (Escape, Ctrl+C, Alt/Shift+wheel) works after switching to a
  Wayland app and back, through a managed key-proxy window. Escape returns
  focus to the previously used app.
- The pin menu keeps its hover highlight when XWayland sends a spurious Leave.
- Errors use non-blocking desktop notifications.
- Under Wayland, clipboard and file pins open near the screen center instead
  of a stale XWayland pointer position.
- Portable installer, safe launcher removal, tests and CI configuration.
