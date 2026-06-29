"""Clan quest pools for the Open Universe (Epic E/F tie-in).

Clans offer generic jobs (clan_quests.amd) drawn from each clan's quest_pool
(clans.amd), gated and reward-scaled by the captain's standing with that clan
(universe_reputation.clan_standing). Completing a job earns standing with the
offering clan along the poles it values, so doing a clan's work makes it like you.

Generic by design now (one job per pool type, any clan can offer it); authoring
stays open - a clan can later carry bespoke quests and these remain the baseline.
See UNIVERSE_CHANGES.md.
"""
from sbs_utils.procedural.quest import (
    document_get_amd_file, quest_add, quest_get_state, QuestState)
from sbs_utils.mast.mast_node import MastDataObject
# NOTE: no relative sibling imports. Mission .py files are loaded by __init__.mast
# (`import universe_clans.py`, `import universe_reputation.py`) into one shared engine
# namespace - they are not a package, so `from .universe_clans import ...` fails to
# compile in-engine. clan_get / clan_standing / clan_offer_tier / clan_reward_mult are
# already available because __init__.mast imports those files before this one. Only
# absolute `sbs_utils...` imports are valid here.


def universe_parse_clan_quests(content):
    """Parse clan_quests.amd into a doc (each heading key is a pool job type)."""
    return document_get_amd_file(None, "ClanQuests", content=content)


def _clan_job_node(doc, job_type):
    if doc is None:
        return None
    for n in doc.get("children", []):
        if n.get("key") == job_type:
            return n
    return None


def clan_work_offers(agent_id, clans, clan_key, doc):
    """Jobs a clan extends to this captain: its quest_pool entries whose tier the
    captain's standing unlocks, with standing-scaled rewards. Returns a list of
    MastDataObject (type/key/clan/title/objective/credits/tier).

    Empty if the station isn't a known clan, the doc is missing, or the captain
    hasn't earned the right to do business (foe clans need positive standing
    first - "only the dangerous bargain with them").
    """
    clan = clan_get(clans, clan_key)
    if clan is None or doc is None:
        return []
    standing = clan_standing(agent_id, clan)
    if clan.get("diplomacy") == "foe" and standing < 20:
        return []
    tier = clan_offer_tier(standing)
    mult = clan_reward_mult(standing)
    offers = []
    for job_type in (clan.get("quest_pool") or []):
        node = _clan_job_node(doc, job_type)
        if node is None:
            continue
        data = node.get("data") or {}
        if int(data.get("tier", 1)) > tier:
            continue
        base = (data.get("reward") or {}).get("credits", 0)
        offers.append(MastDataObject({
            "type": job_type,
            "key": "clan_" + str(clan_key) + "_" + str(job_type),
            "clan": clan_key,
            "title": node.get("display_text", job_type),
            "objective": data.get("objective", ""),
            "credits": int(base * mult),
            "tier": int(data.get("tier", 1)),
        }))
    return offers


def universe_grant_clan_job(agent_id, clans, clan_key, job_type, doc):
    """Add + activate a clan job on the captain. Reward credits are scaled by
    current standing; a rep block is attached so completing it earns standing with
    the offering clan (along the poles it values). Idempotent while active/secret;
    re-acceptable once completed or failed. Returns the quest id, or None."""
    clan = clan_get(clans, clan_key)
    node = _clan_job_node(doc, job_type)
    if clan is None or node is None:
        return None
    qid = "clan_" + str(clan_key) + "_" + str(job_type)
    st = quest_get_state(agent_id, qid)
    if st == QuestState.ACTIVE or st == QuestState.SECRET:
        return qid
    src = node.get("data") or {}
    standing = clan_standing(agent_id, clan)
    mult = clan_reward_mult(standing)
    tier = int(src.get("tier", 1))
    data = dict(src)
    data["reward"] = dict(src.get("reward") or {})
    base = data["reward"].get("credits", 0)
    data["reward"]["credits"] = int(base * mult)
    data["clan"] = clan_key
    # Completing clan work earns standing with that clan along its valued poles.
    data["rep"] = {clan_key: {pole: 5 * tier for pole in (clan.get("leans") or {})}}
    title = str(clan.get("name")) + ": " + str(node.get("display_text"))
    desc = (node.get("description") or "").strip()
    quest_add(agent_id, qid, title, desc, state=QuestState.ACTIVE, data=data)
    return qid
