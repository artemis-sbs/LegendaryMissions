# console_view addon

Two consoles sharing one primitive (`cv_show` — "show console X for ship Y on a
screen"):

- **Director** (`@console/director`, shippable) — from one control window, pick a
  **program / stream screen** (another connected console), a **ship**, and a
  **console**, and that screen is rerouted to show it. A **carousel** auto-cycles
  the consoles on the program screen. Intended as a streamer "director": one
  window directs what the stream shows. Controller and target are *different*
  clients, so the director keeps its controls while the program screen shows the
  gameplay console.

- **Screen Shots** (`@console/screenshots`, dev-only, `is_dev_build()`) — captures
  engine console screenshots. `gui_screenshot` grabs the desktop of the machine
  running the script (the **server**), so this drives the **server screen
  (client 0)** through each console, lets it render, then grabs. One-click "tour"
  or per-console. Files: `shot_<console>.bmp` in the mission folder.

## Why the two differ
`gui_screenshot` can only capture the server's own desktop, so screenshots must
target client 0. Highlighting has no such limit — it can drive any client — which
is what makes the director useful across windows/machines.

## Constraints / status
- **EXPERIMENTAL — needs in-engine verification.** Built and compile-checked, but
  rendering a gameplay widget list on a rerouted screen and the screenshot grab
  itself were not run in the engine.
- Screen Shots: **single-PC** playtest, **Windows**, **BMP**, server window
  visible (ideally fullscreen — it's a whole-desktop grab).
- **Open question**: do all gameplay widgets render on `client_id 0` (server
  screen)? If a widget refuses, sit a real console on the server screen and use
  the director/manual flow instead.
- The director reassigns the program screen's ship (`assign_client_to_ship`) to
  mirror the chosen ship — use a **dedicated spectator screen** as the program
  out, not an active player's console.

## Use it
The addon auto-loads in dev (mission dir is on the MAST path) and is listed in
`__lib__.json` for packaging. Pick "Director" or "Screen Shots" from the console
selector. Disable the director with `default shared DIRECTOR_enabled = False`.
