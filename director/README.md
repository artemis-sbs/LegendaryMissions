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

### Set it up before the mission starts

A show is configured *before* the curtain, not during it. So the Director is reachable from the
console picker **pre-game**: select it, tick **Ready**, and you go straight to the entry screen
instead of waiting. Declare the window as PROG01, do the same in the next window, and the whole
gallery is standing by before the server presses Start.

**It is opt-in, off the label's own metadata**, so `consoles/common_console_select.mast` names
no addon:

```
@console/director !0 ^94 "Director" if DIRECTOR_enabled
metadata: ``` yaml
pre_game: true
```
```

Most consoles genuinely have nothing to do early - a helm with no world to fly through is just a
screen - so Ready still means "I am waiting" for everything that does not ask.

**THE METADATA BLOCK GOES ABOVE THE DESCRIPTION LINE.** `metadata:` and its closing fence sit at
column 0, so putting them after *any* indented body line - the `"` description included - is an
indentation drop mid-label and fails to compile with *"Bad indentation"*. Measured on
`@console`, `@map` and a plain `==` label alike; MAST_CLAUDE.md's `@map` example has them the
other way round and does **not** compile. A story that does not compile schedules no task at
all, so getting this wrong is a whole-mission failure rather than a local one.
`test_director_mast` compiles the real declaration, and proves the wrong order still fails.

**Surviving the start.** The server reroutes every client through `game_started_console` when it
presses Start, which walks each one into its console the ordinary way - `jump(console.label)`,
landing back on the pin screen. A **one-shot resume flag** is armed when a mode is committed and
spent by the next entry: the start reroute spends it and goes straight to the declared mode, and
an operator who later re-picks Director off the console list finds it spent and gets the screen,
which is the only way to change a mode. Cancel clears the declaration *and* disarms the flag, so
backing out cannot skip the screen it just backed out of.

**Cancel unticks Ready** while the game has not started. `console_ready` is a task variable of
the same GUI task that ran the picker, so the picker's own `select_console_clear_ready` reaches
it from the entry screen. After the start it is a dead flag - `game_started_console` read it once
- and the picker shows a Ready *button* instead of the checkbox, so there is nothing to untick.

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
| **director** | The main page. Rundowns, Send/Stop/Resume, dwell, auto-director and the ON AIR line down the left; the **2D view** down the right. |
| **rundown** | The editor. The rundown and its items on the left; the tools that make an item on the right, as sub-tabs: **Stage** and **Console**. Picking an item RECALLS it onto the bench. |
| **capture** | Developer screenshots. Enabled only under `is_dev_build()`. |

The editor is **tools that make rundown items**, plus one button that takes a shot straight to
air. Two earlier versions had this wrong in different ways: the first led with the
Ships x Consoles x Screens pickers and had nowhere to say what should play, and the second split
Stage and Camera into separate tabs - so the rundown you were adding to was never on screen
while you worked. Picking a subject and choosing a shot is one job.

**The Console sub-tab has no Ships list.** It went when a console item learned to bind its ship:
the Stage's Subject/Bind row already answers *"which ship"*, and two controls that can disagree
about it is the same duplicate the screen picker and the shot-mode picker were each deleted for.
What is left is the one thing that tab is uniquely good at - ticking three stations and getting
three items from one press - with the bench's subject shown read-only above it. **One bench, two
views of it**, which is also what lets a console beat be recalled and replaced like any other.

### The main page's 2D view is a selection surface, not a monitor

It is there so a **bound item** can be re-pointed from the page the show is actually run from.
Click a contact and every `<<selected_id>>` item in the play set re-aims on the next tick,
without the operator going near the editor and without the rundown being edited at all. That is
the whole reason it was added; a confidence monitor would not have earned the width.

Three things it needs, none of them optional:

1. **The console is named `gamemaster_director_sci`,** not `director`. `consoledispatcher`
   routes a 2D-view click by matching substrings of the console name: `sci` sends it to the
   SCIENCE selection, which is what `//focus/science` in `stage.mast` reads. A name matching
   none of them falls through to `normal_target_UID` and every click drives nothing at all,
   **silently**. The `gamemaster_` prefix picks the engine's optimized detached-console network
   path. Same name the Stage sub-tab uses, for the same reason.
2. **A scan-priming pass on build.** Science will not select an object this side has no scan
   data for, so a first click on a never-scanned contact does nothing. `//enable/science` covers
   each click; the loop in `cv_paint` covers what is already on screen when the panel opens.
3. **The selection line updates in place and NEVER repaints.** The tree carries the operator's
   collapse state and their scroll position - a repaint to move a piece of text is exactly what
   `director_tree_recolor` exists to avoid. `director_mode_fingerprint()`, the watcher's repaint
   trigger, deliberately knows nothing about the selection.

The left column dropped from 96% of the width to 58%, so the transport row was re-measured and
the auto-director checkbox lost its explanatory tail rather than the dwell slider losing travel.
Both columns' geometry is in `director_layout.py` now - `cv_ctrl_px = 219` with the arithmetic
spelled out in a comment beside it was the last hand-computed number on a page nothing measures.

---

## Items and rundowns

An **item** is one thing a screen can show, and there are three kinds:

```python
{"kind": "cam", "mode": "dolly"|"orbit"|"chase"|"tactical", "subject": id | "<<chain>>",
 "label": ..., "overlays": [ {"kind": "lower_third", ...}, ... ]}
{"kind": "con", "label": "Helm - Artemis", "ship": id, "console": "helm"}  # -> cv_show
{"kind": "ovl", "label": "Act One", "overlays": [ ... ]}                   # furniture only
```

The first two cannot be unified: one is a camera, the other is `assign_client_to_ship` +
`gui_console` + roles. Pretending otherwise is what would break. The third is not a shot at
all - see below.

### A subject can name a SELECTION instead of an object

`"subject"` may be an object id **or** a binding: a string of `<<token>>` hops resolved at
play time against whatever the director has clicked.

```
<<selected_id>>                            orbit whatever I am pointing at
<<selected_id>><<weapons_selection>>       chase whatever the selected ship is shooting at
<<selected_id>><<science_selection>>       ...whatever its science officer is looking at
```

The chain **seeds from the selection**, so `<<weapons_selection>>` alone means the same thing
and `<<selected_id>>` is just the identity hop. That is not a parser convenience - it is what
makes the picker's labels read as one sentence (*"Selection > weapons target"*) rather than
forcing a prefix nobody would ever omit deliberately.

**Why this exists.** A baked id makes a rundown a list of specific ships, so a show has to be
re-authored whenever the interesting ship changes - and the four dynamic generators exist
mostly to paper over that. One bound item is re-pointable live, mid-show, by clicking a
contact on the 2D view that the main panel now carries. The rundown is not edited at all.

There is **no grid hop.** `grid_selected_UID` names a room or a system on a ship's *internal*
grid, not a space object - there is nothing out there for a camera to point at. It was in the
first version of the table purely because `get_grid_selection` sits beside the other three in
`query.py`.

#### A click on empty space selects a PLACE

The 2D view's other click pans the cam, and **the cam is a real object**, so it is the honest
answer to *"what did I just point at"*. `//focus/science` selects it. That makes a bound item a
shot of a **region**: park the cambot in the middle of a fight, and every `<<selected_id>>` beat
orbits or dollies the fight. The shot then glides with the cam on the next pan, because
`camera_orbit` rebuilds its offset from the subject's live position every dispatcher tick.

Leaving the selection alone there was the gap: the cam moved, the radar moved, and every bound
item went on framing whatever contact had been clicked before.

Two consequences, and neither is cosmetic:

- **A camera point is not framed like a hull.** `viewscreen_framing` sizes a shot off
  `exclusion_radius`, and an invisible cam has none - so it falls to `DEFAULT_RADIUS` (90) and
  gives a 540/1440 shot, which frames one mid-sized ship. Orbiting a battle at 540 units is
  inside the engagement looking at nothing. `director_play._framing` answers
  `DIRECTOR_POINT_NEAR` / `DIRECTOR_POINT_FAR` (2500/7000) for a cam instead, sized against how
  far apart ships actually fight.
- **The cam is nameless on purpose** - `player_spawn(..., "", ...)`, because a name would put it
  in engine lists it is deliberately kept out of. So every labeller would read it back as
  `unnamed`. `director_cam_point_name` names it at the **display layer** instead, after the
  console it belongs to (`DIR01 point`), via the `cam_client` back-pointer that is already there
  for the server-side `//focus` routes.

The pick, the selection and the stage all happen **after** the cam is moved. Staging pushes to
every Preview screen immediately, so announcing the pick first would preview the old position
for a tick and read as lag.

`director_bind.py` owns the resolver. Three rules in it are load-bearing:

- **A hop that leads nowhere falls back to the ship it was asked about.** *"Chase what the
  selected ship is shooting at"* is a shot of that **ship** when it is shooting at nothing. A
  fight is full of moments with no target, and a gap in the rotation every time the weapons
  officer drops theirs is worse direction than the ship itself. Each hop is tried, and the last
  **live** object stands. Three ways a hop leads nowhere and they are all the same thing here:
  the console has no target, it is holding an id that has since been destroyed, or the blob
  read raises (which a tombstoned object can do from inside the engine).
- **`0` is unset, not an id**, and the fallback does not excuse this. `get_weapons_selection`
  pulls `weapon_target_UID` straight out of the blob and the engine's "no target" value is `0`,
  not `None`. A `is None` check would hand **object zero** to the camera instead of falling
  back - a live bug on a real bridge, invisible in the mock.
- **An unknown token kills the chain** - the one failure that does *not* fall back, and
  deliberately the opposite of the overlay resolver, which leaves an unknown token *literal*.
  It is an authoring error rather than a runtime state; a visible `<<shpi>>` on a card is
  informative, but a camera quietly pointed at the selection by a typo looks deliberate.

Two things still resolve to nothing, and those beats are **SKIPPED** by the same filter that
drops a destroyed ship (`director_rundown_play_set`): **nothing selected**, and **the selection
itself is gone**. There is no ship to fall back *to*, so there is nothing to show. The seed is
validated for exactly that reason - every later hop falls back to it, so a dead selection would
otherwise be what the whole chain settled on. The rundown steps straight past the beat and
picks it up again the moment it can be shown; skipping is not removal.

### Two keys, and why they must stay two

This is the part that would be tempting to collapse, and collapsing it looks like *"the show
jumps back to its first shot every time I click something"*.

| | Built from | Answers |
|---|---|---|
| `director_item_ident` | the item **as authored** | *where is the feed?* - `_PROGRAM_HELD`, `_ON_AIR`, the play-set dedupe |
| `director_play_plan`'s key | the authored key **+ the resolved subject** | *is this screen aimed correctly?* |

A bound item is the **same item** in the rundown however the selection moves; only what it is
pointed at changed. If its ident moved on every click, `_index_of` would lose `_PROGRAM_HELD`,
the program would snap to `order[0]`, and the dwell clock would reset - the exact flicker that
identity-holding was written to prevent. But a *screen* is aimed at an id, not at a binding, so
its key has to carry the resolved one: click a different contact and that screen re-routes and
re-aims while the rundown keeps its place.

`director_item_subject(item)` is the authored subject; `director_item_subject_id(item)` is the
live id. Everything that talks to the engine wants the second.

### An item does not need a subject at all

`{"kind": "ovl"}` is furniture and nothing else - a title, an intro, an outro, a speaker card.
It has no shot, so:

- every `ovl` item shares **one** shot key, and `director_play_plan` **inherits** the screen's
  running one rather than using it;
- it never reports `changed`, so there is no reroute, no page rebuild and no restarted camera.
  A title belongs **over** the shot that is running, not instead of it;
- its overlays are applied **unconditionally** rather than on an ovkey difference, because the
  beat before it may have been a camera item that left its own furniture up - and `changed`
  being `False` means nothing else will ever clear it.

It is deliberately not a camera item with an empty subject. Every liveness test in
`director_rundowns.py` asks *"does this item name something that still exists"*, and an item
that names nothing **on purpose** has to be distinguishable from one whose ship blew up.

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

### Picking an item RECALLS it onto the bench

An item already in a rundown used to be a dead end: to fix a typo in a lower third you rebuilt
the whole beat, and a beat is a subject, a binding, a mode, a hold, a distance and up to six
overlays with their templates. Picking one out of the item list now loads all of it back, and
**Replace** writes it down again in place. Add still appends, which is what you want when you
are duplicating a beat rather than fixing one.

**The templates come back as TEMPLATES.** Resolving on the way in would bake the currently
selected ship's name into a beat written to follow whatever it is pointed at - and you would not
see the difference until it went to air naming the wrong ship.

**Replace does not dedupe, where Add does.** Add's *"you already have it"* is right for Add;
Replace means *"make row 4 be this"*, and refusing because row 7 already matches would leave the
operator staring at a row that did not change with nothing on screen to say why.

**The repaint loop is the trap**, and this page has grown one twice. Recall has to repaint - the
bind picker, the mode radio, two sliders, the kind listbox and every field box change in value
*and* in shape, which no `.update()` can express - and the rebuild restores the selection, which
re-fires the handler. The guard is to remember the index in `cv_item_index` and act only when the
selection has actually **moved**; the restored index equals the remembered one, so the second
firing does nothing. Remove forgets the index, because the row underneath takes it and would
recall a different beat.

### How far away the camera sits

Framing comes from the subject's own hull radius and that is still the default. **`Distance` is a
per-item override**, `0` means automatic, and an item that never touches it behaves exactly as it
always did. This is not the return of the hand-built sliders the first version had: those were
the *only* way to size a shot, and a fixed number framed a starbase and a fighter equally badly.

| Mode | automatic | explicit |
|---|---|---|
| orbit | radius = the framing's wide end | radius = the distance |
| chase | back = `near * DIRECTOR_CHASE_BACK` | back = the distance |
| dolly | ping-pong wide ↔ near | ping-pong distance ↔ distance/2 |

Three things worth knowing:

- **The slider is seeded from the automatic framing**, so staging a fighter starts it near 1400
  and a starbase near 4800 - a sensible number for *that* hull to nudge from. The stored value
  stays 0 until you commit one.
- **The slider does not restage**, alone on this page. Everything else pushes to Preview as it is
  touched, which is right for a tick or a keystroke; re-issuing the shot on every step of a drag
  is a cut per step. **Dolly to** is what applies it, and seeing the *move* instead of a cut is
  the whole reason there is a button. **Auto** hands it back.
- **A chase's height does not follow it.** What makes a chase read as behind is the elevation
  *angle*; tying the height to a distance the operator is dragging would tip the shot overhead as
  they came closer - the exact thing halving `DIRECTOR_CHASE_UP` alongside `BACK` avoided.

### The shot vocabulary is the bridge's

A camera item carries a **mode**, not geometry:

| Mode | What a screen does |
|---|---|
| **Dolly** | pushes in and back out, ping-ponging so it does not read as a jump cut |
| **Orbit** | one turn, carrying the yaw over so a lap does not whip back to the start |
| **Chase** | sits close behind the subject, re-aimed every tick so it stays there through a turn |
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
| `<<subject_id>>` | the subject's own id, as text | for `Speaker`'s `ship` field, which takes an ID and not text |
| `<<console>>` | the BEAT's station, "Helm" | the item, not the ship - empty on a camera beat |
| `<<crew_name>>` | who is sitting at that station | the ship's `consoles` link, matched on `CONSOLE_TYPE`, then `CREW_NAME` |

**Two of those come off the ITEM, not the subject.** `<<name>> - <<console>> - <<crew_name>>`
reads as *"Artemis - Helm - Viper"*, and only the first third is a property of the ship - which
is why `director_overlay_resolve` takes the beat as well, and why they live in their own
`_ITEM_TOKENS` table with a different signature rather than being squeezed into `_TOKENS`.

`<<crew_name>>` matches the **beat's** station rather than taking the first client on the ship:
a bridge has five people on it, and naming the wrong one on air is worse than naming nobody. An
empty seat is ordinary on a small bridge, so the stock preset is `<<crew_name|unmanned>>` - a
blank second line reads as a broken card.

**This is why a console item learned to carry overlays.** It could not, which is the real reason
the old bridge rundown went to air unlabelled; `director_item_con` has an `overlays` list now and
`cv_show` puts the cards up for a console beat the same way `director_play_apply_shot` does for a
camera one. One branch or the other, never both - applying twice would clear the cards and
re-show them for nothing.

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

**Presets** sit beside the field editor: a picker of built-ins (**Ship ID**, **Ship and side**,
**Condition**, **Contact**, and per kind a subject-free one for an overlay-only beat) plus
anything you Save, in one list, exactly as the rundown picker mixes generators with your own. A
preset name is flattened of `,` `;` `:` before it is stored - it reaches the wire as one entry of
`list: a,b,c;`, so a comma in it would become two entries and the picker would then hold a name
matching no preset. Saving over a name replaces it.

#### The kinds are a table, not a layout

The editor used to be **one hand-unrolled MAST row per overlay kind** - four checkboxes, four
preset dropdowns, eight text boxes, four Save buttons, about eighty lines. Unrolled for a real
reason: an `on gui_message` registered in a `for` loop captures the loop variable at its LAST
value, so a loop over the kinds would have made all four rows edit the letterbox.

But that put the **vocabulary in the layout**. Offering `lower_third_portrait` (a speaker card)
or `credits` (an intro/outro roll) meant another block of MAST, another entry in two Python
tables that had to agree, and another 46px off the 2D view above. Both kinds already existed in
the library; they were simply unreachable from here.

It is a **kind picker plus one field editor** now:

- a `multi=True` listbox whose **selection is the enabled set** - an untick is a row leaving the
  selection and has no event of its own, so the handler replaces the whole set;
- a dropdown choosing **which kind's text you are typing**, and three unrolled field rows that
  read `DIRECTOR_OVERLAY_KINDS`. Still unrolled - but over the FIELDS of one kind, not over the
  kinds - and three because that is `DIRECTOR_OVERLAY_MAX_FIELDS`, with the spare rows hidden and
  the section sized for the widest kind so it does not resize under the operator.

Ticking and editing are **two questions**, which is why they are two widgets: wanting to write
the hero card before ticking it is ordinary, and one widget meaning both would jump the boxes on
every tick. A seventh kind is now one line in `director_overlays.py` and nothing at all in MAST.

**A slot holds one card.** `lower_third` and `lower_third_portrait` both default to the
`lower_third` slot, so ticking both draws one over the other - an authoring mistake, but one
nothing on screen would otherwise explain. `director_overlay_slot_clash` names the hidden one in
the status line, on every tick, before a subject has even been picked.

**Two fields are not text by the time a builder sees them,** and the editor can only offer a text
box - so `director_overlay_build_fields` converts on the way out. `credits`' `entries` splits on
`;` into a list (a string would be iterated one character at a time and roll the alphabet), and
`Speaker`'s `ship` becomes an int, or is **omitted** when it is empty or zero - its default is
`None`, not `""`, so it has to be absent for the card to draw with no square. That is the
narrator case: a speaker card with nobody to show.

### Rundowns

A **rundown** is a named, ordered list of items. Five ship with the addon and are **built at
runtime from live roles**, so they track ships that spawn and die rather than going stale the
moment you choose one. All five carry furniture, because they are the first thing a new
operator sends to air and a bare shot of an unnamed ship is the least this console can do:

| Rundown | Contents | Furniture |
|---|---|---|
| **Follow the selection** | orbit the selection, chase what it is shooting at, its 2D view - **all bound**, no object named | lower third, Ship ID |
| **Crew consoles** | the SELECTED ship's helm, weapons, science and comms - **all bound** | lower third, *Artemis - Helm / Viper* |
| **Player ships** | an orbit of each player ship | lower third, Ship ID |
| **The action** | a chase on each of the most exciting objects right now, best first | top status, hull and shields |
| **Stations & terrain** | orbits of stations and NAMED terrain - the establishing shots | hero, as a title card |

Plus any you create in the editor. Every generator sorts by id: `role()` returns a **set**, and
without a total order the feed reshuffles every dwell and reads as a fault.

**The furniture is TEMPLATES, and that is what makes it possible at all.** A generator makes one
item per ship, so there is nowhere to type "Artemis" - and for a *bound* beat there is nowhere
to type it even in principle, because the answer changes every time the director clicks.

**"Bridge wall" is gone.** It generated a console item per console per player ship - twelve rows
for a two-ship roster - and its premise died with the screen-distribution model. Every program
screen shows the *same* item, so those twelve beats were never a wall: they were a twelve-beat
rotation the one program feed cycled through on a dwell, one console at a time. Cutting to what
the weapons officer is seeing is a real broadcast move; cycling all of them for every ship is
noise. **Crew consoles** is what a director actually wanted from it.

Generated console beats use `helm, weapons, science, comms` and **not** `CV_CONSOLES`. That list
is what the editor offers when you build one by hand, and it carries `mainscreen` and
`cinematic` - neither is a crew view, and a `cinematic` console beat is the worse of the two: a
full-screen `3dview` with no camera applied to it.

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

### Chase is a tick-driven move, not a tractor

**There is nothing to attach.** The intuitive way to chase is to tractor the camera to the
target and let the engine drag it - but the dolly and the target must be the SAME object or the
frame is black, so the lens already rides the subject. A tractored camera object would be
dragged along with nothing looking through it, and the mock stores the connection without
applying the pull, so it would be decorative *and* unverifiable. Following IS re-aiming; the
engine has no interpolation to do it for us.

**What actually made it flicker was the RATE.** Chase was re-issued from the player's own 0.5s
loop with a lens recomputed there, while dolly and orbit went through `camera_dolly` /
`camera_orbit` - library movers that run on `TickDispatcher.do_interval(_tick, 0)`, every engine
tick. `camera.py` says it outright: *"the driver IS the animation, so a coarser interval is
visible as a stutter rather than a saving."* Those two modes never flickered; chase was the one
mode doing it by hand.

So chase is `camera_chase` now (added to `sbs_utils/procedural/gui/camera.py` beside the other
movers), which rebuilds the offset from the subject's live `forward_vector()` every tick. It is
the one move whose lens is a function of HEADING rather than of time, which works only because
`_drive` calls `lens_at` per tick instead of sampling a path up front. Legs are re-issued on
promise-done like every other mode - a chase has no shape to complete, so the leg exists only so
a dead subject or a stolen camera recovers.

A subject with no usable heading (a rock, an engine object that will not answer) falls back to a
fixed rear offset rather than raising: a chase that is merely not behind the ship still shows
the ship. **That fallback is the one way a chase can come out not-behind**, and it is silent -
the offset is a fixed `-Z`, which is only "behind" for a subject that happens to be heading
`+Z`. The maths on the live-heading path is measured correct at every heading; if a chase ever
reads as beside or in front on a real bridge, `forward_vector()` not answering is the thing to
check first.

#### How far back, and why the height goes with it

Both are multiples of the framing `near`, which is already 6 hull radii:

| | was | now |
|---|---|---|
| `DIRECTOR_CHASE_BACK` | 3.0 | **1.5** |
| `DIRECTOR_CHASE_UP` | 0.5 | **0.25** |

At 3.0 back a light cruiser was chased from about 1600 units out - a wide shot that happens to
follow something rather than a chase.

**The height had to halve with it.** What makes a shot read as *behind* is the elevation
**angle**, not the height, and because back and up are multiples of the same `near` their ratio
*is* that angle: `0.5/3.0` is about 9.5 degrees above the subject's own line, which is over its
shoulder. Halving the distance alone would have left the height where it was and doubled that to
18.4 degrees - tipping the shot toward looking *down* on the ship, which is the opposite of what
a chase is for. Halved together, the angle is unchanged and the shot is simply closer.
`test_the_chase_is_over_the_shoulder_not_overhead` holds that at under 12 degrees.

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

**Live refresh does two different things.** `cv_watch_task` polls at 0.25s and splits them:
a SHAPE change (a console declared a mode, disconnected, was renamed) repaints, because the list
has different rows in it; the ON-AIR item moving only recolours, through
`director_tree_recolor()` -> `gui_update` per changed row. Folding the on-air ident into the
repaint fingerprint - which is what it did first - made every advance of the feed a full rebuild.
The rundown selection and the scroll position survive a repaint; The
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

**`await gui()` must follow a BUILD - and there is now a test for it.** It swaps the pending layout in
(`StoryPage.set_button_layout` -> `swap_layout`), and the previous swap left `pending_layouts`
as a fresh EMPTY section - so a label that builds nothing and then awaits hands the client a
blank page with no way back. A wrong pin did exactly that: the check sat in `director_entry_start`,
updated a widget from the previous build and awaited, and the screen went black. The fix is to
jump back to the label that BUILDS and let it repaint, carrying the message in a variable, which
also clears the pin box after a bad attempt.

(The one legitimate build-free await is `cv_show` for a console item: `gui_console()` sets
`pending_console`/`pending_widgets`, so the engine's own console widgets are the page.)

It happened TWICE - the wrong pin, and then `cv_paint_wait`, the label added to break a repaint
loop one message after the rule was written down here. So `test_director_mast.py` now scans every
`.mast` in the addon for it. Prose mentioning `await gui()` is not a violation; the scan drops
comment lines whole, because an earlier ad-hoc version reported the README's own explanation and
that is how a guard starts getting ignored.

**The rule behind the rule: do not repaint to reflect a change.** Every symptom this feature had
- the black frame, a repaint loop, the operator's collapse being thrown away, the selection
moving under their hand - came from rebuilding the page to show something new. The editor tab
never had any of them, because it sets `.value` on a held widget and never repaints. The main
page did, because its rows live inside a listbox `item_template` where there is no handle to
hold - and *that* is what `gui_update(tag, ...)` is for. Rebuild only when the layout's SHAPE
changes: a mode switch, a rundown added or deleted, Refresh.

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

### Height is for the text; padding is for the air

**A widget FILLS the cell it is given.** That one fact is why every control on this console used
to be a slab: the rows were declared 1.8em to 2.4em - 43 to 58 pixels - so the buttons, typeins
and dropdowns in them were 43 to 58 pixels tall. Reaching for more height to stop things
overlapping makes the overlap go away and leaves the slabs behind, which is exactly what the
first fix for the entry screen did.

Padding comes **out of** the row (`layout.py` shrinks the row's area by it) rather than adding to
it, so a one-line row plus 16px of padding is a **40px row holding a 24px control with room to
breathe**, against a 53px row holding a 53px control with none.

Two helpers say it once, and the budget entries that match them cannot drift:

```python
gui_row(director_row_control())            # buttons, typeins, dropdowns, sliders
gui_row(director_row_text("gui-3", 10))    # a line of text with a gap under it
```

More pad below than above on purpose: the gap **under** a row is what a reader perceives as
separating it from the next one, and an even split spends half of it on a gap nobody reads.

**Horizontally there are two gaps, and both are in PIXELS.** Worth stating, because a bare
number in a style string *is* percent - `LayoutAreaParser` returns `digits` as-is and converts
`px` and `em` into it - so `padding: 2` is 26px at 1280 and 38px at 1920. A margin that grows
with the screen is not what a hairline wants.

| | what it is |
|---|---|
| `DIRECTOR_PAD_SIDE` | insets a row's content from its section's edges, so nothing starts hard against the border |
| `DIRECTOR_COL_GAP` | the gap **between** two controls in one row, via `director_col()` |

Columns are laid out **edge to edge** with no gap of their own - there is no `col-gap`, and
`item-gap` belongs to a listbox - so without the second one a label sits welded to the box it
labels: `Pin` and `Enter pin` with nothing at all between them. `director_col("160px")` is how a
control says its width and its gap together, and it is the one call site to change if a row
still reads as one run-on control.

**The radio is the one that needs `extra`.** `RadioButtonGroup` inherits the base
`Column.measure`, which returns `None` - it declines, falls back to flex, and fills whatever it
is given, so it has nothing to size itself from.

Shrinking the rows gave the space back to the things that wanted it: the Stage's 2D view went
from 231px to **282px** at 720p, and the panel's rundown tree from 402px to **478px**.

### The entry screen, and why it drifted

Every section on this console declares the rows it must hold in `director_layout.py`, and
`test_director_layout` asserts it fits. **The entry screen did not**, and it drifted exactly the
way the editor did before that module existed: a hand-written `area:` with hand-written `em`
rows, nothing measuring it, and it shipped rendering broken. Three faults, all of one kind - a
row declared one size and rendered another - and because the engine does not clip, each one
spilled into whatever sat underneath:

| Fault | Cause |
|---|---|
| radio labels wrapped mid-word - "Direct/r", "Progr/am" | a trailing `gui_blank()` gave the group HALF the row |
| the help text overlapped the pin row | `row-height: 1.4em` over a sentence that wraps to two lines |
| the input and the button drew over each other | `2.2em` is the text height; both are drawn with chrome past it |

**`RadioButtonGroup` is ONE content item.** Its own layout splits its width across the buttons,
so a second flex column beside it starves every label at once - the group got half a card that
was already half the screen, and each of three labels got a sixth of it. Alone on its row it
sizes its buttons to their text.

The help row is `row-height: content` now, which measures the wrapped height at the row's real
width; `_ROWS_ENTRY` reserves `2.8em` so the section has the space to give it. That is only
trustworthy because this card is wide - the measured wrap matches the engine at 600px and up and
diverges below ~300px, so a narrow card would want fixed rows and text short enough not to wrap.

Three tests guard the specific faults, and each was checked to actually fail when the fault is
put back.
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
    director.test_director_bind director.test_director_cam \
    director.test_director_layout director.test_director_mast \
    director.test_director_modes director.test_director_overlays \
    director.test_director_play director.test_director_rundowns \
    director.test_director_screens director.test_director_shots
```

Or, from inside the addon folder:

```
cd director && PYTHONPATH=../../sbs_utils python -m unittest discover -s . -p "test_director_*.py"
```

`test_director_mast` is a **static scan of the addon's own .mast**, for the shapes that fail
silently at runtime: `await gui()` with nothing built (a black screen), an unterminated props
string, and - added with the bindings - **every `director_*(` call resolving to a real public
def**. That last one matters because a misspelled name is a `NameError`, a failing MAST
expression STOPS THE COMMAND, and the button then reads as doing nothing with nothing on screen
to say why. Neither `--test` nor `sbs lint` catches it: the editor's tabs are unreachable to
`--exercise-click` and the panel's handlers only fire on a press.

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
12. With `DIRECTOR.pin` set, press Start with the **wrong** pin: the entry screen comes back
    saying `wrong pin` with the pin box cleared - **not** a black screen. Then the right pin
    goes through, and the message is gone on the next visit.
12. Visit the editor, stage a shot, return to the main page - clicking the 2D view still
    selects. *(the re-seat bug)*

### Selection binding, overlay-only items, and the panel's 2D view

13. On the **main page**, click a contact in the 2D view: the selection line in the header
    changes, and the tree does **not** repaint - collapsed branches stay collapsed and the
    scroll position holds.
14. Author `Orbit / Bind: Selection` and `Chase / Bind: Selection > weapons target`, Send, then
    click a different ship. Program **re-aims**, and the rundown does **not** jump back to its
    first item. *(the two keys)*
15. Deselect: both bound items drop out of the rotation and the show steps past them. Select
    again and they come back. *(skipping is not removal)*
16. Point the selection at a ship whose weapons officer has **no target**: the
    `Selection > weapons target` item shows **that ship**, and nothing is aimed at object zero.
    Give the officer a target and the same beat follows it without the rundown moving.
17. Author `Bind: None - overlays only` with a Hero card and put it in the rundown. The card
    appears **over** the running shot: no cut, no black frame, and the orbit under it does not
    restart.
18. Two overlay-only beats in a row: the cards swap and the camera keeps running.
19. Tick **Lower third** and **Speaker** together: the status line names the one that will be
    hidden. Untick one and the warning goes.
20. Pick **Credits** in the Editing dropdown and type `Kirk; Spock; McCoy` into `entries`: three
    lines roll, not one string spelled out a character at a time.
21. **Speaker** with the built-in preset shows the subject's ship square; the **Narrator**
    preset shows the card with no square at all.
22. Click **empty space** in the 2D view: the cam pans there and the selection line reads
    `DIR01 point`, not `unnamed`. A `Bind: Selection` orbit then frames that spot **wide** -
    park it between two fighting ships and the orbit should hold both, not sit inside them.
23. Pan again while that shot is on air: the orbit glides to the new point without a cut.

### Setting up before the mission starts

24. **Before** the server presses Start: open a client, pick **Director** in the console list,
    tick **Ready**. It goes to the pin/mode screen rather than waiting.
25. Declare it **Program**. Open a second window, declare that one **Preview**, and a third as
    **Director**. All three are standing by with the mission not yet running.
26. Press **Start** on the server. All three stay where they are - **none** of them bounces
    back to the pin screen, and the names PROG01 / PRE01 / DIR01 are unchanged.
27. From the running Director, go back to the console list and pick **Director** again: the pin
    screen **does** appear, because the resume was already spent. That is how a mode is changed.
28. Pre-game, tick Ready on the Director and then press **cancel** on the entry screen: you land
    back on the picker with **Ready unticked** and the console still selectable.
29. Do the same *after* the game has started: cancel returns to the picker, which shows the
    Ready **button** - there is no checkbox to untick and nothing should look stuck.

### The stock rundowns, recall, and the distance

30. Send **Follow the selection** with nothing selected: nothing goes out and the status line
    says so. Click a ship: all three beats play and the lower third names it. Click a different
    one: they re-aim without the rundown losing its place.
31. Send **Crew consoles** and click a player ship: program cycles that ship's helm, weapons,
    science and comms, each with **"Artemis - Helm"** over the crew name - or *unmanned* where
    nobody is sitting there. Click a **rock**: every beat is skipped and the feed moves on,
    rather than showing helm widgets for an asteroid.
32. Send **The action** in a firefight: the top banner reads hull and shields and follows it.
33. Pick an existing item out of the item list: the bind picker, mode, hold, distance and every
    overlay field come back **as templates**. Change the lower third's line, press **Replace** -
    the row updates in place and the list does not reorder or scroll. Press it twice: no loop.
34. Stage a fighter, then a starbase: the distance slider seeds to a different sensible number
    each time while the stored value stays automatic.
35. Set a distance and press **Dolly to**: Preview *moves* to it rather than cutting. **Auto**
    puts it back. Add the item and play it: it holds the distance, and a chase at 800u is still
    over the shoulder rather than looking down.
36. On the Console tab, confirm the subject reads back from the Stage's bind - there is no second
    Ships list to disagree with it. Tick three consoles, Add: three items, all bound, all
    carrying whatever overlays were ticked on the Stage.

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
