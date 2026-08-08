"""Sample traffic for the Log Panel bench (comms/log_panel_probe.mast). TEMPORARY.

Kept as data in Python so the MAST side stays a three-line loop, and so the spread is
easy to tune while judging the panel. Delete with the bench.
"""


def log_probe_messages():
    """A realistic spread: every category, every severity, coloured and not, short and
    long. The long one matters - wrapping is what decides whether the panel is readable
    once there is history in it."""
    return [
        # Plain traffic. Most of a real log is this.
        {"text": "Sensor sweep complete, no contacts", "color": None, "cat": "log", "sev": ""},
        {"text": "Course laid in for the outer marker", "color": None, "cat": "log", "sev": ""},
        {"text": "Long range scan shows the lane is clear as far as the relay, though there is "
                 "some interference off the nebula to starboard", "color": None, "cat": "log", "sev": ""},
        # Coloured, the way missions already colour their own broadcasts.
        {"text": "Docking clamps engaged", "color": "green", "cat": "log", "sev": ""},
        {"text": "Power fluctuation in the aft coupling", "color": "yellow", "cat": "log", "sev": ""},
        # Ship tab - the crew's own news.
        {"text": "Docked at DS 1", "color": None, "cat": "ship", "sev": ""},
        {"text": "Damage control reports the port shield emitter is back on line",
         "color": None, "cat": "ship", "sev": ""},
        {"text": "Shields below 40 percent", "color": None, "cat": "ship", "sev": "warning"},
        # Mission tab.
        {"text": "Quest accepted: Rock Breakers", "color": None, "cat": "mission", "sev": ""},
        {"text": "Quest complete: Rock Breakers", "color": None, "cat": "mission", "sev": "tip"},
        # The one that interrupts - watch it pull the log tab to the front.
        {"text": "Hull breach on deck three", "color": None, "cat": "ship", "sev": "danger"},
    ]
