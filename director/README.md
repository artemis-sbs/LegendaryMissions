# director addon

A broadcast director console with **two feeds**:

| Feed | Shown on | Content |
|---|---|---|
| **PROGRAM** | every console in Program mode | what is going out - what you took, or what the rundown advanced to |
| **PREVIEW** | every console in Preview mode | what the editor is building, **live**, or the next item up when nothing is staged |

That is broadcast: every program screen shows the same thing, every preview screen shows the
same thing, and the two are different things. The sentence the main page says is

> **play these rundowns**

- because a console's declared MODE is its selection. There is no screen picker and no wall.

## It is a streaming tool

The Director does **not** commandeer mainscreens or crew seats. Cosmos already has plenty of ways
to put something on a bridge screen, and taking a crew console away mid-game is a way to ruin
somebody's game. Instead you open extra clients and declare what each one is, on an entry screen
that appears whether or not a pin is configured:

| Mode | What that console becomes |
|---|---|
| **Program** | An output screen - what the streamer captures. |
| **Preview** | The same, showing the shot **before** it goes out: whatever is staged, or the next item up when nothing is. |
| **Director** | The control console: the tabs below. |

**Declaring a mode IS the selection.** A console that opens as Program is a program screen, and
Send goes to every one of them. There was a picker here once - two grouped lists, a pre-tick that
had to be one-shot so an un-tick could stick, and a set remembering which ids had been offered -
and it answered a question nobody had: the console had already said what it was, and the list
only restated that, one repaint behind.

Narrowing to this deleted a whole layer: there is no "home console" to remember and no
restore-to-your-old-bridge path, because a director screen never had a bridge. Stop releases the
camera and sends each screen back to its own holding page.

## The Director console's tabs

| Tab | What it is |
|---|---|
| **director** | The main page. Rundowns, Send/Stop/Resume, dwell, auto-director, and the ON AIR line. |
| **rundown** | The editor. The rundown and its items on the left; the tools that make an item on the right, as sub-tabs: **Stage** and **Console**. |
| **capture** | Developer screenshots. Enabled only under `is_dev_build()`. |

The editor is **tools that make rundown items**, plus one button that takes a shot straight to
air. Two earlier versions had this wrong in different ways: the first led with the
Ships x Consoles x Screens pickers and had nowhere to say what should play, and the second split
Stage and Camera into separate tabs - so the rundown you were adding to was never on screen
while you worked. Picking a subject and choosing a shot is one job.

---

## Items and rundowns

An **item** is one thing a screen can show, and there are two kinds because the engine has
two unrelated mechanisms:

```python
{"kind": "cam", "mode": "dolly"|"orbit"|"chase"|"tactical", "subject": id,
 "label": ..., "overlays": [ {"kind": "lower_third", ...}, ... ]}
{"kind": "con", "label": "Helm - Artemis", "ship": id, "console": "helm"}  # -> cv_show
```

They cannot be unified: one is a camera, the other is `assign_client_to_ship` +
`gui_console` + roles. Pretending otherwise is what would break.

### A SHOT is not an ITEM

Two identities, and collapsing them into one cost a whole feature:

| | What it answers | Used by |
|---|---|---|
| `director_item_key` | *is the camera pointed at the same thing, the same way?* - subject + mode | the player's re-route tracking, and **only** that |
| `director_item_ident` | *is this the same item?* - the shot, plus its furniture, plus its hold | Add to rundown, the play-set dedupe, and what is held on air |

The reported case: **"show a station with a lower third, dwell for 7, then show the same
station without the lower third."** That is two beats of one shot and it is ordinary direction.
Keyed on subject + mode alone, the second Add answered *"already in that rundown"* and did
nothing - so a rundown could not hold more than one item per shot at all. The play set
de-duplicated the same way, so the second beat would have been dropped on the way to air even
if it had gone in; and `_PROGRAM_HELD` matched the same way, so advancing from the titled beat
would have found the first match and snapped straight back to it.

Keeping the coarse key for the player's tracking is what makes that cut look right: the SHOT is
unchanged across the two beats, so there is no re-route, the camera keeps orbiting, and only
the cards swap. A double-click still collapses, and a generated orbit of Artemis appearing in
two rundowns still collapses, because everything about those matches.

### The shot vocabulary is the bridge's

A camera item carries a **mode**, not geometry:

| Mode | What a screen does |
|---|---|
| **Dolly** | pushes in and back out, ping-ponging so it does not read as a jump cut |
| **Orbit** | one turn, carrying the yaw over so a lap does not whip back to the start |
| **Chase** | sits behind the subject, re-aimed every tick so it stays there through a turn |
| **Tactical** | a 2D view of the subject on that screen |

Dolly, Orbit and Tactical are `viewscreen.SHOT_LABELS` - the science and weapons **"On Screen"**
list - so a Director shot and a bridge shot of the same ship are the same shot. Framing comes
from `viewscreen_framing()`, which scales off the subject's **hull radius**, which is why a
starbase and a fighter both fill the frame. An earlier version computed its own lens offsets at
a slider-chosen distance, and framed neither well.

**Legs are re-issued when they finish**, independent of whether the screen's item changed: a
22-second dolly on a screen that is not rotating would otherwise run once and freeze on its
last frame. Chase re-aims every tick, which is the whole of what makes it a chase - the engine
does not rotate offsets into the dolly's frame, so a fixed offset trails a ship only until it
turns.

### Overlays

Four toggles on the Stage tab, **several allowed at once** because each draws into a different
screen slot: **Lower third** (name, line), **Hero** (title, subtitle), **Top status** (text) and
**Letterbox** (line). The fields are the ones each builder actually reads - a field a builder
ignores is a text box that silently does nothing.

**They preview on the real thing.** The editor used to carry a 3D pane with the overlays drawn
into Director-scoped slots scaled proportionally into it - an approximation of an approximation,
since overlay slots are screen-relative and a letterbox at its real slot would bury the editor
that asked for it. Every console in Preview mode now shows the actual card at full size, live, so
the pane went; the width it freed is what makes a template box readable.

**Furniture is cleared before the next item.** `rundown.py` does that in its own `_apply`; this
does not use those desks, so nothing would - and a feed advancing through five overlay-carrying
shots would end up showing five lower thirds at once.

#### The text is a TEMPLATE

A generated rundown makes **one item per ship**, so there is nowhere to type "Artemis". Each
field takes a template resolved against **that item's own subject**, one line before
`overlay_kind`:

| Token | Resolves to | How |
|---|---|---|
| `<<name>>` | the ship's name | `obj.name` |
| `<<class>>` | hull display name, "Light Cruiser" | blob `hull_name` override, else `ship_data.get_ship_name(obj.ship_data_key)` |
| `<<side>>` | side display name | `obj.side_display` |
| `<<role>>` | raider / station / monster | first `get_role_list()` entry that is not `__...__` |
| `<<race>>` | origin | `obj.race`, with the literal "no origin" treated as unresolved |
| `<<comms_id>>` | "Artemis (TSN)" | `obj.comms_id` - the engine already builds this |
| `<<hull>>` | hull percent | `viewscreen_hull_percent(subject)` |
| `<<shields>>` | front / rear percent | blob `shield_val` / `shield_max_val`, slots 0 and 1 |

`<<class|contact>>` gives a fallback when a token cannot resolve, so a rock with no hull class
does not leave a blank line. An **unknown** token is left LITERAL rather than raising - the
missing-key-safe contract `amd_fill` settled on - so a typo shows up on air as `<<shpi>>` and is
obvious, instead of blanking the card.

**Why `<<...>>` and not `{...}`.** Not a style choice; braces are fatal on this path. MAST re-runs
any string containing a brace through f-string formatting at ASSIGNMENT, and `gui_text` does it
AGAIN at render - and a failed format does not raise, it silently returns the empty string, so a
lower third with a bad token would not error, it would VANISH. A backtick is deleted twice over
(`gui_text_escape` on the way out, `TextInput._sanitize` on the way in), `$` is the style-key
sigil, and `[` is a link reference in text-area markdown. `<` and `>` appear in **no** parser on
the path - verified by running a string through all four stages - and doubling them means a stray
`<` in "<5%" can never match. They also pass through the `_plain()` brace-stripping the addon
already does, so none of that had to change.

Resolution happens in `director_play_overlays`, **not** in a builder: `banner` and `lower_third`
are cycle kinds whose text is word-wrapped and split into timed segments, so an unresolved token
could be split across two of them.

**Presets** sit beside each row's fields: a picker of built-ins (**Ship ID**, **Ship and side**,
**Condition**, **Contact**) plus anything you Save, in one list, exactly as the rundown picker
mixes generators with your own. A preset name is flattened of `,` `;` `:` before it is stored -
it reaches the wire as one entry of `list: a,b,c;`, so a comma in it would become two entries and
the picker would then hold a name matching no preset. Saving over a name replaces it.

### Rundowns

A **rundown** is a named, ordered list of items. Four ship with the addon and are **built at
runtime from live roles**, so they track ships that spawn and die rather than going stale the
moment you choose one:

| Rundown | Contents |
|---|---|
| **Bridge wall** | a console item per console type per player ship - the classic multiview |
| **Player ships** | an orbit of each player ship |
| **The action** | a chase on each of the most exciting objects right now, best first |
| **Stations & terrain** | orbits of stations and NAMED terrain - the establishing shots |

Plus any you create in the editor. Every generator sorts by id: `role()` returns a **set**, and
without a total order the feed reshuffles every dwell and reads as a fault.

**The play set is the union of the SELECTED rundowns.** Multi-select, so unselected is *off*.
Duplicates across two rundowns collapse to one item, and an item whose subject has gone is
dropped at play time - which is what stops a long session turning a rundown into a list of
dead contacts.

## Playing them

The player is one server task, scheduled once at load. It ticks at **half a second** with a dwell
counter rather than sleeping the whole dwell, because preview has to follow the editor as it is
typed in and a camera leg re-issues when the LEG ends - a 22-second dolly - not when the rundown
advances.

Each tick it computes one PROGRAM item and one PREVIEW item and hands each to every screen in
that mode. A screen is only rerouted when its ITEM changed; a furniture-only change (new overlay
text, a row ticked) re-shows the cards in place, because a reroute rebuilds the page and restarts
the camera, and preview restages on every keystroke.

### The on-air item is held by IDENTITY, not by position

This is the one thing to keep true in here. The play set is **rebuilt every tick** - twelve
times per dwell - so that generated rundowns track ships that spawn and die. **"The action" then
re-sorts it by live `exciting` values on every one of those evaluations**, and its top-N
membership churns in a fight. So indexing that list positionally moved the on-air item whenever
the *sort* moved, with no advance having happened. Reported as: *"The action rundown flickers a
lot. Switching too soon."*

`director_play_feeds` therefore remembers the **key** of what is on air and looks it up each
tick, so the list can reorder underneath it freely. Only the clock moves the feed. Two details
fall out:

- **An advance steps in the CURRENT order.** Held by identity, but the step is taken in the list
  as it stands at that moment - so a rundown that legitimately reordered is honored at the
  instant the dwell fires, rather than being frozen to the order at Send.
- **A vanished item falls to the FRONT, not to its old position.** Its subject died or the
  operator deselected the rundown carrying it. A stale index into a re-sorted list is exactly
  the bug; the front is the honest answer, and acquiring it restarts the clock so the
  replacement gets a full hold instead of inheriting a spent one.

### A hold: how long ONE item stays up

An establishing shot of a starbase wants ten seconds; a chase in a firefight wants three. So a
hold is **part of the item**, set on the Stage tab and carried in the rundown, and the dwell
stays the answer for everything with no opinion - including every generated item. The slider's
bottom stop is 0 and reads back as *"holds for the dwell"*, because a control's low end has to
mean something and half a second would be unwatchable.

The clock lives inside `director_play_feeds` rather than in the player loop, and that is not
tidiness: whether to advance depends on the **held** item's own hold, so a caller that decided
first would have to know what is held before asking what is held. The player hands `elapsed` in
and takes back whatever the function says it now is.

The hold is **not** part of an item's identity (`director_item_key` is subject + mode), so two
rundowns naming the same shot with different holds are still one shot and the first into the
play set wins.

**There is no Send to Preview.** Every control in the editor restages as it is touched, so a
button to push it would only be a way to forget. **Send to Program** skips the rundown entirely:
it puts the current subject, shot and overlays on every program screen at once. It **holds** - on
a six-second dwell an item that did not hold would be overwritten on the next advance and read as
a button that does nothing - until **Resume** or **Stop** on the main page clears it.

**A take also freezes the clock.** Without that, the dwell would expire while the take was up and
the first tick after Resume would cut immediately - so Resume would behave like Skip.

A preview screen with nothing staged shows **the next item up** rather than going blank; blank
reads as broken, and what is coming next is the other thing a director wants to see.

The **auto-director** (the old "auto-follow the ship worth watching") keeps the rundowns you
chose and only decides *which item is up and when*. It ranks by the engine own `exciting`
value - the signal the engine automatic cinematic camera follows, so it agrees with what the
engine would have picked - and holds its choice through noise: a challenger must beat the held
item by `DIRECTOR_AUTO_MARGIN` before the shot moves. Two contacts trading a fractionally
higher score would otherwise swap the feed several times a minute.

In a lull, or headless where nothing populates `exciting` at all and everything reads 0.0, the
ranking falls back to **the order you built**, not to an arbitrary one.

### Why this does not use `rundown.py` desks

`sbs_utils.procedural.gui.rundown` is a vision mixer and it is the right shape for ONE feed:
`_SHOTS` is a single flat table, `_DESK["program"]` is one audience, `_DESK["live"]` is one
shot. Neither fits here - several rundowns selected at once cannot be told apart in one flat
table, and the Director runs two feeds at once, which one `_DESK["live"]` cannot express. So the
desks are **not used**, deliberately; do not "fix" this back to `rundown_program()`.

What *is* reused is everything that fits, and it is most of the library: `camera_dolly` /
`camera_orbit` / `camera_track` all take a client-id **list** and touch no desk, so they run per
screen; `viewscreen_framing` and the `DOLLY_SECONDS` / `ORBIT_SECONDS` / `ORBIT_PITCH` /
`DOLLY_YAW` constants are imported rather than copied, so a Director shot cannot drift from a
bridge one; `overlay_kind` / `overlay_clear` / `overlay_slot_define` are the furniture; and
`camera_auto` is the release path.

---

## The camera each console rides, and the bug that hid in it

On entry the console spawns (or re-uses) an invisible camera and seats itself on it - the Game
Master / OU Admiral cambot pattern. Two things fall out of it that are the point: the operator
holds no bridge seat, and the console never lists itself in its own ship pickers.

### What a program screen's own camera can and cannot do

Each program screen also gets a camera remembered against its client id. It is **not** what a 3D
shot rides, and it cannot be: `cinematic_control` renders a **black frame** when the dolly and
target ids differ (engine-confirmed, CameraRepro rungs 10 and 11), and `camera_track` folds a
separate dolly away and assigns the console to the target. While a Dolly, Orbit or Chase shot is
live, the screen rides the subject. That is the engine's model.

**The cinematic view is sized explicitly.** `gui_console("cinematic")` sets the widget list to
a bare `3dview`, but the engine sizes it from that console's own default rect, which leaves an
inset for furniture that is not there - so a program feed came out letterboxed inside its own
window. `cv_show` follows it with a full-screen section and `gui_layout_widget("3dview")`, which
sends an explicit rect (`send_client_widget_rects`) and is the documented way to size either
view. Its own section, with nothing else in it: an engine widget draws at its own size over
whatever MAST put beside it.

What the screen's own cam IS for: **Tactical** (a 2D view is not a cinematic camera and has none
of that constraint, so the screen keeps its own cam and the view is centered per client with
`science_set_2dview_focus` - which also means two screens can hold different modes for the same
ship), and **parking** a screen that is idle or released instead of leaving it riding whatever
it last filmed.

No tractors. `AddTractorConnection` would drag a camera behind a ship, but nothing would look
through it, and the mock stores the connection without applying the pull - so it would be both
decorative and unverifiable.

**`director_cam_ensure(client_id)` is called at the top of EVERY tab, and that is not
optional.** Staging a shot calls `shot_apply` -> `camera_track`, which does
`sbs.assign_client_to_ship(cid, dolly)` - it must, because the engine only honors a camera
change when the console and the lens ride the same object. Everything the stage tab does is
gated on `has_roles(SCIENCE_ORIGIN_ID, "director_cam")`, and `SCIENCE_ORIGIN_ID` **is**
`sbs.get_ship_of_client(client_id)`. So a console that has previewed anything is no longer on
its cam, `//focus/science` and `//enable/science` stop matching, clicking the 2D view selects
nothing, and **nothing is logged**. That was reported as *"in stage, selecting a subject
eventually gets broken"* - eventually, because it broke the first time the operator opened the
shot tab, and only a trip back through the main page ever fixed it. Guarded by
`test_director_cam.py`.

Three more things the camera needs, each of which had gone missing:

- **`to_object(...) is None` alongside the None check** is the restart guard: the
  `DIRECTOR_CAM` inventory value survives a `sim_create()` that took the object with it.
- **A side.** `player_spawn(..., "#,...")` means *roles only, no side*, and scan data is
  stored per the ORIGIN side - so a cam with an empty side writes into a slot nothing reads
  back and scans silently do not take. The GM and the Admiral both assign one after spawning.
- **The `consoles` link moves with the client.** Left on the old ship, every overlay and
  `announce()` aimed at that ship paints over this panel; and because `get_ship_of_client` now
  answers with the cam, the next console change orphans the old link for good.

**Ask `director_cam_of(client_id)`, never `sbs.get_ship_of_client`,** for "this console own
ship" - the same hazard `viewscreen_home_ship` exists to solve for the main screen.

**The screen names itself.** `director_cam_default_name` writes `CREW_NAME`, which is what the
holding pages and the operator's summary read, so a streamer with four windows open can tell
PROG01 from PRE01 without having typed anything.

**Known and not solved: the cam leaks on disconnect.** LM Game Master and OU Admiral both do
this too; it is called out here rather than quietly inherited.

---

## There is no screen picker

A console's declared mode is its selection, so the main page carries a **count** instead:
`2 program, 1 preview`, or - the case that matters - `no screens - open a client and declare it
Program or Preview`. "Send appears to do nothing" is the commonest confusion on this console and
the reason is invisible otherwise.

**Live refresh.** `cv_watch_task` polls a cheap fingerprint and repaints when a console declares
a mode, disconnects or is renamed; the rundown selection and the scroll position survive. The
fingerprint deliberately **ignores what each screen is showing**, because the player rewrites
`CONSOLE_TYPE` every time it changes a screen item - watching that would repaint the operator
page every dwell, moving the selection under their hands.

**Names follow the mode, and there is nothing to type.** The entry screen names the console
`PROG01`, `PRE01` or `DIR01` - the lowest free number **per prefix**, so a screen that leaves
frees its number and a program screen and a preview screen can both be 01. Moving the mode radio
re-derives it in front of you; Start commits it.

The name field went because it only ever held what the radio above it already implied, and a
streamer opening four windows had to fill it in four times. One consequence is worth knowing:
the derivation now **ignores whatever `CREW_NAME` already holds**. That key is also written by
`common_console_select` from the crew-name flow, so a client that named itself before opening
the Director arrives with a person's name in it - and a program screen called "Doug" says
nothing about what it is. Guarded by `test_director_cam.py`.

---

## Two library contracts that cost a session each

**A checkbox's `state:` in the message is dead weight.** `Checkbox.__init__` parses it and then
immediately clobbers `_value` with the constructor argument - `False` whenever `var=None` - and
`_present` puts `state:` on the wire twice, where the engine takes the first. So
a checkbox with `state:` in its message can never render checked. Assign `.value` after
construction instead (the `manual_weapons.mast` form).

**Every props string must end in `;`.** `gui_input` stores its props RAW and `_present` appends
the cascaded styling straight onto the end, so `gui_input("desc: name")` goes on the wire as
`desc: namefont:gui-2` and the widget draws that as its prompt. Same for `gui_drop_down` and
`gui_checkbox`. `gui_input`s own docstring example has the terminator; fourteen calls in this
addon did not.

**A listbox answers in two different SHAPES.** `get_selected_index()` returns a LIST of indexes
when the listbox was built `multi=True` and a bare INT (or `None`) when it is single-select;
`get_selected()` is the same story with values - a list when multi, the bare ITEM when not.

So a helper that iterated the answer worked on every multi list and raised
`TypeError: 'int' object is not iterable` on every single-select one. **And a failing MAST
expression stops the command**, so the assignment never happened, the task ended, and the button
read as doing nothing at all with *no error anywhere on screen*. That was **Add console items**
(its Ships list is single-select) and the capture tab's **Shoot**. The values case is worse than
a crash because it does not raise: `list("helm")` is `['h','e','l','m']`, so a single-select
console list would have produced four consoles with one-letter names.

Both shapes are normalized once, in `director_screens.py` - the call sites are MAST and cannot
see which shape they are about to get.

**An overlay with an audience and no `seconds` never dies on its own.** It gets a permanent
`_LIVE` record, and a one-second catch-up ticker re-shows it onto any page in the audience whose
slot is empty. Only `overlay_clear` retires it (`_live_drop`) - dropping your own bookkeeping is
**not enough**, the card comes back a second later.

Also worth knowing: the four kinds do not share a lifetime. `lower_third` self-clears when its
text finishes, `banner` loops forever, and `hero` and `letterbox` are sticky until cleared.

---

## The stuck overlay, and the one door that fixed it

Recorded so it is not re-derived a fourth time. **Every one of these was the same shape** - a
transition with no clear on it - and each was fixed individually, at which point a new one grew.

| # | Path | Why nothing cleared |
|---|---|---|
| 1 | **`Send`** | `director_play_reset()` did `_SLOTS.clear()` with no `overlay_clear`. `_SLOTS` is the only record of which slots are up and `overlay_clear` needs the slot name, so every card up at that moment was orphaned **permanently** - and it BEAT Stop, whose release then found an empty `_SLOTS` and cleared nothing |
| 2 | cam item -> **console** item | `cv_show` gated on `cv_shot is not None`, and `director_play_apply_shot` bailed on `kind != "cam"` before reaching the clear |
| 3 | cam item -> **tactical** | `cv_show_2d` never touched overlays *or* `_SHOTS`, so a stale camera kept ticking at a 2D view |
| 4 | leaving the editor any way but **Clear** | the preview clear had exactly one call site; a tab press is a `jump` on the same page, so the card outlived it |
| 5 | preview goes idle | the reroute was skipped for a `None` item, and `_LAST` was then set so it never read as changed again |
| 6 | the preview holding page | the program branch released; the preview branch did not |

**The fix is one door.** Every screen transition ends in `gui_reroute_client(screen, <label>)` and
there are exactly four targets - `cv_show`, `cv_show_2d`, `cv_screen_program`,
`cv_screen_preview`. All four call `director_screen_enter(client_id)` first, which clears the
screen's slots and pops its camera record. The invariant it makes true is *a screen cannot arrive
anywhere with its previous furniture or camera still running*, and one door is cheaper to keep
true than six. `director_play_reset()` **releases before it forgets**, for the same reason.

**Refuted, so it is not chased again:** `gui_reroute_client` does *not* create a new page - it
jumps `page_stack[-1]`'s GUI task, and `OverlayManager` lives on the page and survives rebuilds.
So `overlay_clear` always could find the region. Two earlier fixes were aimed at a page-identity
problem that does not exist.

**Turn the log on when checking this in a browser.** `overlay_debug_log()` is a plain MAST global;
one call at the top of `__init__.mast` writes `LegendaryMissions/overlay_debug.log` with a
numbered `show` / `clear` / `establish` / `present_all` stream. The decision rule is exact: a stuck
card with **no `clear slot=X` line** is a missing clear; a `clear` followed a second later by a
fresh `show` is the `_live_catchup` ticker. Remove the call before shipping.

## Layout rules this obeys

The bottom stack is anchored in **px** and the lists take what is left; a percent section full
of `em` rows is only correct at the resolution it was tuned at. The tab strip owns the top
35px, so content starts at 40.

- **Never `"""..."""` for a label.** A triple-quoted row is a `gui_text_area`; it declines
  measurement, so `row-height: content` on it silently becomes flex and a stack of them comes
  out as equal shares. Use `gui_text("$text:...;", "col-width: content;")`.
- **Sliders and dropdowns decline measurement too** (they fall back to flex, never to zero),
  so each gets an explicit width and a `gui_blank()` absorbs the slack.
- On a listbox: `col-width` flips it horizontal, `row-height: content` raises, and a bare
  number is percent-of-SCREEN. `font:` goes on the listbox, which resolves its own `em`.
- **Escape dynamic text** with `gui_text_escape` - a status line can contain a colon, which is
  a style-property separator.

**The editor's geometry is data, and it is TESTED.** `director_layout.py` declares each section
with the rows it must hold; `director_area(name)` computes the areas, and
`test_director_layout.py` asserts every section fits at 720p and 1080p.

That is not belt-and-braces. The editor page is reachable only by clicking a tab-strip button and
`--exercise-click` cannot press those, so `--audit-layout` has never seen it - it is the one
screen nothing measures. The first version shipped with a 64px section holding two 53px rows (the
item list bled into the rundown buttons) and a control block given 226px to hold 415px of stacked
rows (**Add to rundown** fell off the bottom). Neither was a mock-versus-engine metrics question:
the arithmetic was wrong and nothing checked it.

The control block is stacked and **full width** now. It was two columns while the Stage carried a
3D preview pane beside the radar, which left the overlay rows about 400px to hold a checkbox, a
preset picker, two template boxes and a Save. Dropping that pane gave the width back - and a
full-width row is the difference between a readable template box and one showing six characters
of `<<class|ship>> - <<side>>`. That is a budget that grew by four rows in one edit, which is
exactly what the fit test is for.

The main page is audited clean at 1280x720 and 1920x1080: no overflow, overlap or degenerate
rects.

## Tabs

`//gui/tab/<path>` routes, enabled per build with `gui_tab_enable("stage,shot")` +
`gui_tab_back(CONSOLE_SELECT)`. **The enable set is read at swap time and then cleared, so
every build must re-enable its tabs.**

**Never `gui_tab_add_top`** - it adds the tab to every console in the game and, at a mission
top level, silently collapses the compile (`labels 0/N`, while `--test` still prints PASS).

The tab button text IS the route path, which is why the paths are the short words an operator
reads. They live in a **global** registry, so `stage` / `shot` / `capture` are claimed
mission-wide; LM registers 22 tab paths and none collide.

---

## Testing

```
PYTHONPATH=../sbs_utils python -m unittest \
    director.test_director_cam director.test_director_layout \
    director.test_director_modes director.test_director_overlays \
    director.test_director_play director.test_director_rundowns \
    director.test_director_screens director.test_director_shots
```

Headless drive - note **both** the `COSMOS_SETTINGS` pin and the short dwell:

```
COSMOS_SETTINGS='{"DIRECTOR": {"enable": true, "pin": ""}}' \
PYTHONPATH=../sbs_utils python -m cosmos_dev.mission_runner . --test 150 --map siege \
    --profile director_test \
    --exercise --exercise-console director --exercise-dwell 1 --exercise-click-every 2 \
    --exercise-click "Start,Send to Program,Stop,Resume,Refresh" \
    --audit-gui-handlers --audit-layout --coverage-json /tmp/cov.json
```

- **The pin must come through `COSMOS_SETTINGS`.** Measured 2026-08-20: the `DIRECTOR:` block
  in `profiles/director_test.yaml` does not reach a `cosmos_dev` run, although `AUTO_START`
  from the same file does. Without an empty pin the console sits on the pin prompt for the
  whole run and reports zero coverage while looking exercised.
- **`--exercise-dwell 1`, not 8 or 25.** The cycle visits five gameplay consoles before
  `director`, and on `siege` with `--exercise` the players are wiped in about six seconds, so the
  mission restarts long before a slow cycle reaches the panel. Measured 2026-08-20: at dwell 8 it
  is never opened, and the report says so only indirectly - `gui 0/9` routes and no `cv_` label
  in the coverage JSON.
- **`--exercise-click` cannot press tab-strip buttons.** They are built into
  `pending_layouts` rather than through `page.add_content`, so they never enter the tag map the
  clicker walks. The main page is fully driven headless; **stage, shot and capture must be
  checked in the browser**. `--coverage-json` tells the difference - look for `cv_stage`,
  `cv_shot_ui`, `cv_capture` in its `labels` list.
- `--runs N` ends with a bogus `FAIL - mission executed 0 labels`; read the per-run table and
  the STABLE/divergence line, not the trailing verdict.

Browser (`--gui`, `http://localhost:8765/`) is the only place layout and render are real, and
the **only place the camera can be judged at all**. `cinematic_control` is thinly mocked, and
the black-frame rules - dolly != target, lens sitting on its look-at point, console not
assigned to the dolly - are all engine-observed. Check:

1. **Send repeatedly with something on air** - no card is left behind. *(leak 1)*
2. A camera item with a lower third, then a **console** item: the card goes. *(leak 2)*
3. The same into a **tactical** item: the card goes and the camera stops moving. *(leak 3)*
4. Leave the editor by every route - tab, back tab, console change: nothing stuck. *(leak 4)*
4b. **Console sub-tab**: pick a ship, tick two consoles, **Add console items** - both appear in
    the item list and the status line under the buttons is readable, not off the bottom.
4c. Stage a station with a lower third and a 7s hold, Add; untick the lower third, Add again -
    **two** items in the list, and the feed cuts between them without the orbit restarting.
5. **Clear** the subject while preview screens are live: they go idle and empty. *(leaks 5, 6)*
6. Untick an overlay: it leaves the Preview screens without pressing anything else.
7. Type in an overlay text field: Preview updates and the field keeps its focus and its text.
8. Two program screens show the **same** item; two preview screens likewise.
9. A **Player ships** rundown with a Ship ID lower third names each ship correctly as it
   advances - the whole point of templates.
10. `<<class>>` on a terrain object falls back rather than leaving the line blank.
11. The entry screen reads `PROG01` for Program and re-reads `PRE01` the moment the radio
    moves to Preview, and the holding page it lands on carries the same name.
12. Visit the editor, stage a shot, return to the main page - clicking the 2D view still
    selects. *(the re-seat bug)*

---

## Constraints

- All on-screen text is ASCII (the engine renders ASCII only).
- Screen shots: **single-PC** playtest, **Windows**, **BMP**, server window visible. They
  ALWAYS drive the server screen (client 0), because `gui_screenshot` grabs the desktop of the
  machine running the script and that is the only surface it can reach.
- A program screen has its ship reassigned, so it must be a **dedicated spectator client**.
  Declaring a mode is what enforces that: a crew seat is never a target because it never
  declared.

## Use it

Auto-loads in dev (the mission dir is on the MAST path); listed in `__lib__.json` for
packaging. Pick "Director" from the console selector. Pin-gated by `DIRECTOR.pin` (default
`"000000"`); set it to `""` to skip the prompt. Disable with `DIRECTOR.enable: false`.

## Deferred

- **Cam cleanup on disconnect** (above).
- **A library `set_selected_indexes()`.** There is no multi-select restore API on
  `LayoutListbox`, so `director_restore_ids` assigns `.selected` directly - the same list
  `select_all()` writes - before the first present. One documented function knows about it.
- **`--exercise-click` reaching tab buttons**, so a tabbed console can be driven headless at
  all. This affects every LM console with tabs, not just this one.
