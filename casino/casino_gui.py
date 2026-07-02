"""Shared casino GUI helpers - the reusable bits every card table draws.

Called from within a gui_section in MAST; they add to the current layout.
As more games land, common pieces (seat panels, controls bar) accrete here;
this is the "table framework" in helper form (MAST GUI is imperative, so a
shared-helper framework fits better than shared labels).
"""
from sbs_utils.procedural.gui import gui_image, gui_image_keep_aspect_ratio_center, gui_row
from sbs_utils.procedural.gui.console import gui_activate_console
from sbs_utils.procedural.gui.console_tab import (
    gui_tab_enable_top, gui_tab_back, gui_tab_enable)


def casino_console_header(back_tab):
    """Standard casino page header: activate the hangar console, show the top
    tabs, set the back tab, keep the Casino tab lit. Replaces the repeated
    4-line boilerplate at the top of every casino render label."""
    gui_activate_console("hangar")
    gui_tab_enable_top()
    gui_tab_back(back_tab)
    gui_tab_enable("casino")


def casino_draw_hand(cards, key_fn, back_key, up=None):
    """Draw a row of card images, each keeping its aspect ratio (centered) so
    cards aren't stretched to fill the cell. ``up`` = how many are face-up
    (rest drawn as ``back_key``); None = all face-up. ``key_fn`` maps a card ->
    atlas key."""
    gui_row()
    show = len(cards) if up is None else up
    for i, c in enumerate(cards):
        gui_image_keep_aspect_ratio_center(key_fn(c) if i < show else back_key)
