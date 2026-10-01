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

## Capture coordinates

GNOME Screenshot's area command saves an image but does not return the selected
desktop rectangle. Using the cursor afterward placed the pin beside the drag's
release point (usually the bottom-right). Image Pin now freezes the desktop with
GNOME Screenshot, removes the temporary file, and shows its own region selector.
The selector keeps the normalized rectangle, crops the snapshot, and places the
pin exactly over that rectangle with a thin frame. Escape or right-click cancels. The
full snapshot is discarded when selection ends; only the crop becomes a pin.

The selector shows the frozen snapshot without dimming until a drag begins, so
mapping it does not visibly change the screen. GNOME Screenshot 41 still plays
its own full-screen flash when taking the snapshot. GNOME Shell 46 denies its
screenshot D-Bus methods (including area selection and flash control) to
non-allowlisted clients, so Image Pin cannot request the selected rectangle or
a flash-free capture directly.

Snapshot pixels are mapped to Qt desktop coordinates before cropping, preserving
the initial displayed size on uniformly scaled desktops. This mapping assumes
the screenshot covers the virtual desktop with a uniform pixel-to-coordinate
ratio; mixed-DPI multi-monitor behavior still needs hardware verification.

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
