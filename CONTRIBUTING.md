# Contributing

Keep changes focused and run `./scripts/check.sh`. If a change affects native
input routing or transparency, also run `uv run test_desktop.py` in a disposable
X11 session or `./scripts/check.sh --desktop` on the target desktop.
The desktop test briefly operates its own generated windows and restores the
pointer. It is a real X11 input test; running it under Xvfb does not establish
GNOME Wayland compatibility.

Report distribution, GNOME/Vicinae version, session type, display layout/scaling,
input device and exact reproduction steps. Use generated images rather than
private desktop captures. Describe whether movement comes from drag, wheel,
opacity adjustment or a monitor change.

The helper is GPL-3.0-only. The standalone launcher wrapper under `extension/`
is MIT-licensed and calls the helper through ordinary command-line arguments.
Preserve license notices. Keep user-facing wrapper strings in English and add
helper translations through `i18n.py`.
