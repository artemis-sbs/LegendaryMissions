# casino/games — engine modules

Pure-Python game engines (no MAST/GUI, no `sbs` imports). Each is
deterministic — pass in a `random.Random` — so tests and house-edge sims are
reproducible. The MAST/GUI layer calls these; keep game logic here.

- `engines.py` — nibble, gates, blackjack, choga (deck, scoring, dealer/banker
  policy, settlement). Rules confirmed against the original `bundle.js` and
  the info pages (see `../CASINO_RULES.md`, `../rules_text.md`).
- `test_engines.py` — 21 unit tests (scoring, naturals, truth tables, banker
  tableau, rankings, settlement). All green. Run: `python -m unittest
  test_engines` from this folder. (Pure logic — no `test_set_exe_dir()`
  needed; not under `tests/` so not auto-discovered by the project suite yet.)
- `sim.py` — house-edge Monte-Carlo. Run: `python sim.py`.

## House edge (500k hands, naive strategy) — sanity check, not final tuning

| Game | Edge | Notes |
|---|---|---|
| Blackjack | +5.8% | naive "hit to 17"; ~0.5-2% under optimal. Healthy. |
| Nibble | +37% | faithful rules are **very** house-favored; strategy-sensitive. Flag for tuning if it feels punishing. |
| Gates | ~0% | banker-wins-ties barely edges the house under random betting. Consider a small commission (baccarat-style) if a real edge is wanted. |
| Choga | ~7% per ante | under always-raise; ~2.4% per unit actually wagered (raise stakes 3 units). Pay ladder is sound; nudge down for a bigger edge. |

**Takeaways for @doug:**
- **Nibble** is brutal at faithful rules — decide whether to keep (authentic)
  or soften (e.g. player wins ties, or lower dealer `must`).
- **Gates** needs a house mechanism if you want guaranteed profit (tie edge
  alone is ~nil under two-way betting).
- **Choga** pay ladder validated; ~2-3% real edge is fine. No change needed.
- **Blackjack** standard, fine.

These are engine-truth numbers; the GUI layer doesn't affect them.
