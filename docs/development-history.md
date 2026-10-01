# Image Pin

Vicinae commands for draggable, borderless image references on Ubuntu GNOME.

- **Capture & Pin**: select an area with GNOME's selector; release to pin.
- **Pin Clipboard Image**: pin a copied image (or copied local image file).
- **Pin Image File**: choose an existing image.
- **Close All Pins**: close all floating images.

Drag the image directly to move. Scroll scales around the cursor without animation, keeping the image point under it fixed.
Shift+scroll makes fine adjustments. Double-click restores original size. Right-click offers copy, save, lock and close. Escape closes the focused pin.
Multiple pins can remain open. Screenshots use private temporary files, deleted
as soon as loaded, and are not uploaded or added to Pictures automatically.

## Install

Prerequisites: Vicinae, Node/npm, uv, GNOME Screenshot, working DISPLAY/XWayland.

```zsh
cd ~/src/image-pin
uv sync
cd extension
npm ci
npm run build
```

The build registers the local extension in Vicinae without restarting it.
Search for `Capture & Pin` or `Image Pin`. Set a hotkey on the command through
Vicinae's command actions/settings if desired.

The extension expects this project at `~/src/image-pin`. Move it by updating
`extension/src/run.ts` and rebuilding. Qt uses XWayland (`QT_QPA_PLATFORM=xcb`)
so GNOME honors window positioning and the always-on-top hint. Native Wayland
window placement is compositor-controlled. Other desktops are not validated.

The helper uses one transparent desktop surface with an image-only input region.
The native surface stays the same size during zoom and drag; transparent areas
pass pointer input through to the applications below. Multiple pins share the
same surface, and clicking a pin brings it above the others. The helper remains
resident after pins close, allowing multiple commands to
share a process. It is started only on demand, not at login. To stop it:

```zsh
~/src/image-pin/.venv/bin/python ~/src/image-pin/image_pin.py shutdown
```

Errors: `~/.local/state/image-pin/helper.log`.

## Checks

```zsh
uv run test_pin.py
uv run test_desktop.py  # XWayland + xdotool; uses generated test windows
cd extension
npm run typecheck
npm run build
```

References: [Vicinae source install](https://docs.vicinae.com/install-extensions),
[Qt window flags](https://doc.qt.io/qt-5/qt.html#WindowType-enum).

## Verified locally

On the current Ubuntu GNOME Wayland session:
- Four widget tests pass: drag/zoom/lock/Escape, clipboard handling,
  captured-file cleanup, cancellation cleanup.
- GNOME screenshot backend returns a valid image; the validation capture was
  deleted immediately without displaying or retaining desktop content.
- A synthetic pin is visible and has `_NET_WM_STATE_ABOVE`.
- Vicinae's **Close All Pins** command reaches the helper and closes visible pins.
- TypeScript typecheck and the Vicinae build pass.

The interactive area-selection gesture still needs a user trial. No global
hotkeys or autostart settings were changed. The extension uses suspended
navigation when closing Vicinae so the helper request can finish.


## Interaction polish — 2026-10-01

- Removed the blue hover outline and the large hover tooltip.
- Wheel input accumulates a target scale instead of jumping the window size.
- Elapsed-time interpolation in log scale makes proportional zoom smooth;
  animation stops when settled, so idle pins do not run a redraw timer.
- The image point under the cursor remains anchored, including while scrolling
  repeatedly. Direction reversal discards unfinished movement in the old direction.
- Shift+wheel makes smaller adjustments. Dragging, locking, resetting and closing
  stop pending zoom immediately.
- Resizing preserves the image ratio even for thin images; minimum longest edge
  is 64 logical pixels. Maximum enlargement limits unusually large render surfaces.
- Current scale and source dimensions are visible in the right-click menu.

The interaction approach was informed by the local
`~/src/smooth-push-zoom/extension.js`; the pin implementation is independent.
Qt wheel-event behavior was checked against the
[official QWheelEvent documentation](https://doc.qt.io/archives/qt-5.15/qwheelevent.html).
Seven tests now pass, including animated anchoring, rapid input accumulation,
reversal, lock interruption, scale bounds and a border-free rendered image.

### Position jitter correction

Resize and movement now use one `setGeometry` update, avoiding a visible resize
at the previous position before movement catches up. Repeated wheel ticks at a
stationary cursor retain their original anchor rather than recalculating it from
rounded window geometry. Eight tests pass; the new repeated-scroll regression
also passes under XWayland, checking monotonic movement and anchor error no
larger than half a logical pixel per axis. Perceived smoothness still requires
user feedback on the actual display.


### Wheel animation removed after user feedback

The previous interpolation caused each wheel step to produce multiple window
moves, which the user experienced as trembling. Wheel packets now apply their
full scale change immediately in a single geometry update, preserving the
cursor anchor and Shift fine control. No zoom animation or animation timer
remains. Earlier animation checks above describe the superseded approach.
The regression test now checks immediate response and no subsequent movement
while idle.


### Fixed-origin zoom after continued jitter feedback

The user still saw severe jitter after animation was removed. Cursor-anchored
native window repositioning has now been removed entirely: scrolling and reset
only resize the window, leaving its top-left origin unchanged. Moving remains
an explicit drag operation. This supersedes the cursor-anchor behavior above.
The position regression passes under XWayland while varying cursor positions
and zoom direction; perceived screen stability is not established by that test.

Dragging and resizing can be combined: hold the image with the left mouse
button and scroll while moving it. Wheel changes preserve the drag offset
and do not request an extra position change. A regression covers dragging,
zooming in/out while held, and continuing the drag.


### Center-based zoom requested by user

Zoom and reset now preserve the center rather than the top-left. The center is
kept in floating-point coordinates across wheel packets to avoid accumulating
rounding drift. Each packet applies one geometry update, with no animation.
When dragging, resize updates the drag offset so the next pointer event
continues from the resized position without snapping back. Nine tests pass;
center preservation and combined dragging/resizing also pass under XWayland.
Perceived jitter remains subject to user feedback.


## Fixed surface renderer — current implementation

Repeated user feedback showed that coordinate tests did not predict perceived
jitter. Native floating-window resize/move remained present after removing
interpolation, changing anchor choices and combining geometry updates.

The new implementation removes that path entirely. Pins are logical images on
one fixed-size transparent Qt surface. Center coordinates and image extents
remain floating point and are painted in the same frame. Zoom and drag produce
no native window move/resize requests. X11 SHAPE 1.1 updates only the input
region; the visual bounding region is never changed. Damage updates are limited
to the old/new image bounds, avoiding whole-desktop redraw on each input.

The surface uses XWayland override-redirect to avoid window-manager constraints,
full-screen placement, shadow and automatic repositioning. Focus is explicitly
acquired when an image is clicked. Transparent pixels outside image rectangles
do not intercept input. Close All Pins hides the surface entirely.

Verified on Ubuntu 24.04 / GNOME 46 / XWayland:
- 9 interaction, alpha-render, clipboard and temporary-capture regressions pass.
- The prior implementation produced 11 distinct native geometries during 20
  wheel inputs. The new renderer produced **zero server ConfigureNotify events**
  during 24 zoom inputs.
- The input region read back from the X server matches the image bounds.
- A real pointer click outside the image reaches an owned underlying test window.
- Real pointer press, drag, wheel while held, release, keyboard focus and Escape
  all pass. Desktop tests use generated images, and restore the pointer afterward.
- Native transparency, no hover border, pixel cleanup after closing, and constant
  native geometry pass on XWayland.

This removes the suspected resize/repaint race by construction. The exact
previous compositor bug was not isolated through a display-frame recording;
user-visible smoothness still needs confirmation. Earlier native-window and
animation sections describe superseded implementations, retained as history.

References: [X11 SHAPE library](https://xorg.freedesktop.org/archive/X11R7.7/doc/libXext/shapelib.html),
[X11 SHAPE 1.1 protocol](https://www.x.org/releases/X11R7.7/doc/xextproto/shape.html).


### Cursor anchor on the fixed surface

After the user confirmed that the fixed-surface renderer felt good, wheel zoom
was changed from the image center to the cursor. The source-image coordinate
beneath the pointer stays fixed in floating-point space. While holding an image,
zoom also updates the drag offset, so the grabbed image point stays under the
mouse during subsequent movement. Native window geometry remains unchanged.
Ten tests pass, including repeated reversal and moving cursor anchors; the
cursor-anchor and combined-drag regressions pass on XWayland too. The real
pointer and server-event desktop regression still passes with zero native
ConfigureNotify events during zoom.
