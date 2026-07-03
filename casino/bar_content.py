"""Bar content loaded from bar.amd - the single authored source for the casino's
patrons, their rumor pools, and ambient chatter. Authors edit one movie-script
file (bar.amd); these helpers pull the pieces out of the parsed document so no
Python edits are needed to add a patron, a rumor, or a chatter line.

bar.mast reads the file once at load and hands the parsed document here via
bar_set_doc(); everything else reads from that cached tree. A rumor node's prose
is what the patron SAYS (the "tip"); its data `intel` is the payoff shown if the
tip pans out. Truth is rolled from the teller's reputation at ask time (see
bar_reputation.py), so entries only carry tip + intel.
"""
import random as _random

_DOC = None   # parsed bar.amd document (set once by bar_set_doc from bar.mast)


def bar_set_doc(doc):
    """Cache the parsed bar.amd document. Returns it (so it can also be stored in
    a shared MAST var). Call once at load from bar.mast."""
    global _DOC
    _DOC = doc
    return doc


def _patron_nodes():
    """Top-level patron headings (every node except the Chatter section)."""
    if _DOC is None:
        return []
    return [n for n in _DOC.get("children", []) if n.get("key") != "chatter"]


def _patron_node(key):
    for n in _patron_nodes():
        if n.get("key") == key:
            return n
    return None


def bar_patrons():
    """Ordered patron definitions from bar.amd: key, call_sign, face_kind,
    reliability. Faces are generated in MAST from face_kind (see
    bar_build_pilots)."""
    out = []
    for n in _patron_nodes():
        d = n.get("data") or {}
        out.append({
            "key": n.get("key"),
            "call_sign": d.get("call_sign", n.get("display_text", "pilot")),
            "face_kind": d.get("face_kind", "terran"),
            "reliability": d.get("reliability", 0.5),
        })
    return out


def patron_base_rep(key):
    """Authored starting reputation (reliability) for a patron key, or None."""
    n = _patron_node(key)
    if n is None:
        return None
    return (n.get("data") or {}).get("reliability")


# ---- rumor pool ------------------------------------------------------------
def _rumor_nodes(key):
    n = _patron_node(key)
    return n.get("children", []) if n is not None else []


def patron_rumor_pool(key):
    """[{tip, intel}] for a patron: tip = the spoken line, intel = the payoff."""
    pool = []
    for r in _rumor_nodes(key):
        pool.append({
            "tip": (r.get("description") or "").strip(),
            "intel": (r.get("data") or {}).get("intel", ""),
        })
    return pool


def patron_has_rumors(key):
    return len(_rumor_nodes(key)) > 0


def pick_rumor(key, rng=None):
    pool = patron_rumor_pool(key)
    if not pool:
        return None
    return (rng or _random).choice(pool)


# ---- chatter ---------------------------------------------------------------
def bar_chatter_lines():
    """Ambient bark lines from the Chatter node, or a small default."""
    if _DOC is not None:
        for n in _DOC.get("children", []):
            if n.get("key") == "chatter":
                lines = (n.get("data") or {}).get("lines")
                if lines:
                    return list(lines)
    return ["House always wins, pilot. Until it doesn't."]


# ---- patron dicts for the runtime (with generated faces) -------------------
def _face_for_kind(faces, kind):
    k = str(kind or "").lower()
    if "torgoth" in k:
        return faces.random_torgoth()
    if "female" in k:
        return faces.random_terran_female()
    if "male" in k:
        return faces.random_terran_male()
    return faces.random_terran()


def bar_build_pilots(faces):
    """Build the shared bar_pilots dict {key: {key, call_sign, face,
    reliability}} from bar.amd, generating each patron's face from its
    face_kind. `faces` is the MAST faces module (passed in so this stays
    import-order agnostic). bar_set_doc must run first."""
    out = {}
    for p in bar_patrons():
        out[p["key"]] = {
            "key": p["key"],
            "call_sign": p["call_sign"],
            "face": _face_for_kind(faces, p["face_kind"]),
            "reliability": p["reliability"],
        }
    return out
