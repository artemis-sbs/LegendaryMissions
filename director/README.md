# director addon

One console ("Director", `@console/director`) sharing a single primitive
(`cv_show` - "show console X for ship Y on a screen"):

- **Highlight / multiview** (shippable) - three **multi-select** list-box pickers:
  **Program screens**, **Ships**, **Consoles**. Apply pairs them by index with
  round-robin (`screen[i]` shows `console[i % nCon]` for `ship[i % nShip]`): one
  console + N screens = mirror; N screens + N consoles = a multiview wall. The
  selection shape sets the mode - if MORE consoles than screens are selected they
  can't all show at once, so Apply **auto-rotates** them (dwell slider sets the
  speed); equal/fewer is a static wall. No separate carousel toggle. Intended as a
  streamer "director": one control window directs what the program/stream screens
  show. Controller and targets are *different* clients, so the control window
  keeps its UI.

- **Screen shots** (dev only, `is_dev_build()`) - capture buttons in the lower
  section. These ALWAYS drive the **server screen (client 0)**, because
  `gui_screenshot` can only grab the desktop of the machine running the script
  (the server). Per-console ("Capture selected") or all ("Capture ALL"); files
  saved as `shot_<console>.bmp` in the mission folder.

## Why screenshots use the server screen
`gui_screenshot` captures the server's own desktop, so a console must be put on
the server screen (client 0) to be captured - independent of the Program-screen
selection, which is only for highlighting. The UI notes this.

## Constraints / status
- **Confirmed working in-engine** (highlight + rendering a gameplay console on a
  rerouted screen). Screenshot grab still assumes the conditions below.
- All on-screen text is ASCII (engine renders ASCII only).
- Screen shots: **single-PC** playtest, **Windows**, **BMP**, server window
  visible (ideally fullscreen - whole-desktop grab).
- Highlight reassigns the program screen's ship (`assign_client_to_ship`) to
  mirror the chosen ship - use a **dedicated spectator screen** as program out,
  not an active player's console.

## Future polish (deferred)
- The picker lists are built once when the console opens; they don't yet refresh
  as consoles **connect/disconnect** mid-session. Doing that cleanly likely needs
  client connect/disconnect **signals** to re-fire `cv_ui`. Deferred to a later
  polish pass.

## Use it
Auto-loads in dev (mission dir is on the MAST path); listed in `__lib__.json` for
packaging. Pick "Director" from the console selector. Disable with
`default shared DIRECTOR_enabled = False`. The capture section only appears in
dev builds. Console choices include `cinematic` (the 3D cinematic view).
