"""Reusable top-tab bar for NON-console screens.

The console "top tabs" (helm/weapons/...) are an engine-internal system: a
`TabControl(Text)` row drawn by the page from the global `//gui/tab` registry and
the per-client `console_tabs` inventory, keyed off `CONSOLE_SELECT`. That's right
for real consoles but wrong for a transient full-screen takeover like the game
results screen (shown on every client, including server/operator/gamemaster).

This helper reproduces the *look* of those tabs with plain buttons, so any screen
can have a tab strip without touching the console-tab system. It has no LM-specific
logic and is a candidate to move into sbs_utils later.
"""
from sbs_utils.procedural.gui.button import gui_button


def gui_screen_tabs(tabs, active_key, on_press, active_bg="#999", tab_bg="#333"):
    """Draw a row of tab buttons (call inside a gui_row at the top of a screen).

    Args:
        tabs: list of (key, label) pairs, left to right.
        active_key: the currently selected key; that tab is highlighted.
        on_press (str): name of a MAST label to jump to on click. The clicked
            tab's key arrives as the variable TAB_KEY; the label should store it
            in the screen's tab var and re-jump to the screen, e.g.:

                === results_set_tab
                    RESULTS_TAB = TAB_KEY
                    jump show_game_results_gui

        active_bg / tab_bg: background colors for the active / inactive tabs
            (defaults mirror the console top tabs).
    """
    for key, label in tabs:
        is_active = (key == active_key)
        bg = active_bg if is_active else tab_bg
        color = "black" if is_active else "white"
        gui_button(
            f"$text:{label};justify:center;color:{color};",
            style=f"background:{bg};margin:1px,2px,0,0;",
            data={"TAB_KEY": key},
            on_press=on_press,
        )
