"""Marker so `python -m unittest discover` reaches this folder's tests.

Without it `test_recipes`, `test_inputs_have_a_source` and `test_fabricate_panel` are
invisible to discovery and only run when named explicitly - which is how the first two
sat out of the suite entirely. Same marker, same reason, as consoles/__init__.py.

MAST does not read this file: the addon's entry point is __init__.mast, and nothing
imports this one, so it defines no MAST globals. The mastlib packages it harmlessly.
"""
