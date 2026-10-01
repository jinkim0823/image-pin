# Rendering and input architecture

Pins are logical images with floating-point center, scale, opacity and drag
state. A single translucent Qt surface spans the desktop. Native window
geometry changes only when the display layout changes, not when a pin moves or
scales. A frame clears damaged pixels and draws affected pins back to front.

For cursor-centered zoom, the renderer changes scale and translates the image
center so the source point under the pointer remains fixed. During dragging,
the drag offset is updated to that new center. Subsequent motion keeps the same
image point under the pointer rather than snapping to an old offset.

X11 SHAPE 1.1 controls only the surface's **input** region. The visual bounding
region remains unchanged. The input region is the union of visible image
rectangles; transparent areas outside those rectangles pass input through.
Opacity does not change the input footprint. Identical input regions are cached
so opacity-only changes need no shape request.

On XWayland, the surface uses override-redirect to avoid window-manager tiling,
automatic placement and resize constraints. Clicking a pin explicitly focuses
the surface, enabling Ctrl+C and Esc. Closing the last pin hides the surface.
The helper remains resident until explicitly stopped.

## What was verified

The native desktop regression uses generated images and an owned underlying
window. It reads back input regions, observes server-side ConfigureNotify
events, and drives actual pointer press/drag/wheel/release and Escape. It also
checks that a click outside the image reaches the underlying test window.
The pointer is restored afterward; no desktop content is recorded.

This is stronger than checking calculated coordinates alone. It still does not
prove that every GPU/compositor/display combination looks identical. The
validated desktop is Ubuntu 24.04 / GNOME 46 / XWayland. Multi-monitor hotplug
handlers and scaling logic exist; broader hardware coverage remains open.

The earlier native-window approach and the reasoning behind the redesign are
preserved in [development-history.md](development-history.md).
