"""Marker so `python -m unittest discover` reaches this folder's tests.

Without it the tether tests are invisible to discovery - including
test_tether_damage_route.py, which pins a bug that actually shipped. MAST does not read
this file (the addon's entry point is __init__.mast) and the mastlib packages it
harmlessly. Same marker, same reason, as consoles/ and fabrication/.
"""
