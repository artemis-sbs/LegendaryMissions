"""Marker so `python -m unittest discover` reaches this folder's tests.

Without it the console tests are invisible to discovery (only `casino` had one, so
only casino's tests ever ran). MAST does not read this file - the addon's entry point
is __init__.mast - and the mastlib packages it harmlessly.
"""
