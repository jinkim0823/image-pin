# Release readiness review — 0.1.0

## Changes made before public release

| Area | Result |
| --- | --- |
| Language | English wrapper copy; English/Korean helper catalog and preference |
| Portability | Removed the fixed `~/src/image-pin` dependency; executable preference and quoted launcher paths |
| Installation | Locked uv/npm dependencies, installer and ownership-checked removal |
| Rendering | Fixed native surface; cursor-centered image transforms, transparency and click-through input |
| Opacity | 10–100% slider and Alt+wheel; original image data retained |
| Input | Real modifier-wheel behavior checked; Qt horizontal translation handled for Alt/Shift gestures |
| Capture placement | Frozen-snapshot selector retains the normalized rectangle in both drag directions; pins stay in place with a thin frame |
| Recovery | Bring Pins into View command for off-screen images |
| Helper lifecycle | Exclusive daemon lock; rejected requests do not spawn another helper |
| Licensing | GPL-3.0-only helper; independent MIT wrapper, with notices retained in bundled commands |
| Public presentation | English README, generated demo GIF, architecture, changelog, contribution guide and issue template |
| Automation | CI configuration with pinned actions and isolated X11 input test |

## Validation

- 20 unit/render/interaction/language/lifecycle tests passed locally, including
  capture placement, reverse drags, snapshot cropping/scaling and cancellation.
- Installation/removal regression passed from a path with spaces; unrelated
  launcher files were preserved.
- TypeScript typecheck, Vicinae manifest lint and isolated-output build passed.
- Native GNOME 46 / XWayland regression passed: zero ConfigureNotify events over
  24 zoom inputs, correct input shape, click-through, drag with wheel, actual
  Alt+wheel opacity, actual Shift+wheel fine zoom, focus and Escape.
  Native region selection also passed in both drag directions, retaining the
  same top-left placement; Escape cancelled without creating a pin.
- Rendered preview visually inspected; only generated images are included.
  The demo uses 50 fps (350 frames / 7 seconds) and fine-grained scripted input,
  replacing the earlier 20 fps / isolated-wheel-step sequence. A full-color MP4
  is included alongside the GIF. Application interaction code was not changed.
- Source archive is built from committed, tracked files, excluding environments,
  logs, helper state and node_modules.

## Remaining scope and publication status

GitHub Actions is configured but has not run remotely before repository creation.
KDE, other desktop environments, macOS, Windows, ARM and a Wayland-only session
without XWayland are not claimed as supported. Multi-monitor layout handlers
exist, but broader display/hardware coverage remains open.

The extension uses `@vicinae/api` and launches a Linux helper that uses GNOME
Screenshot and X11 SHAPE. Vicinae's ability to run some Raycast extensions does
not make this wrapper or helper compatible with Raycast. A Raycast version would
need a separate platform backend as well as a Raycast wrapper.

The store is a separate review process. The standalone repository can be
published first; a store submission must clearly document the separately
installed helper. No store publication or remote CI completion is claimed.
