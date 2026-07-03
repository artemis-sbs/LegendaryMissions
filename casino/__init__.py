# Package marker so `python -m unittest discover` (and VS Code Test Explorer)
# can find the casino/games/test_*.py suites and nest them under the
# LegendaryMissions folder. Runtime MAST loads these modules by file path
# (import casino_economy.py), so this marker has no effect on the mission.
