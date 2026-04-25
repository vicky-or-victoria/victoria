"""
V.I.C.T.O.R.I.A. — NPC Nation AI
Runs every turn. Each NPC nation takes one action based on its stats and state.
Actions: expand, internal policy, economic growth, military buildup,
         diplomatic shift, crisis, war against player, inter-NPC war.
Results are returned as event strings for the turn narrative.
"""
import random
from utils.mapgen import get_neighbors, in_bounds, axial_distance

# ─────────────────────────────────────────
# ACTION WEIGHTS PER GOVERNMENT TYPE
# ─────────────────────────────────────────
# Keys: expand, policy, economy, military, diplomacy, crisis
GOV_WEIGHTS = {
    "monarchy":   [25, 15, 15, 20, 15, 10],
    "empire":     [35, 10, 10, 25, 10, 10],
    "republic":   [15, 25, 25, 10, 20,  5],
    "theocracy":  [20, 30, 10, 15, 15, 10],
    "oligarchy":  [20, 10, 35, 15, 15,  5],
    "sultanate":  [25, 15, 15, 25, 10, 10],
    "duchy":      [20, 20, 20, 15, 20,  5],
}
ACTION_KEYS = ["expand", "policy", "economy", "military", "diplomacy", "crisis"]


def _pick_action(gov_type: str, nation: dict) -> str:
    weights = list(GOV_WEIGHTS.get(gov_type, GOV_WEIGHTS["monarchy"]))

    # Adjust for current state
    if nation["stability"] < 4:
        weights[ACTION_KEYS.index("crisis")]   += 20
        weights[ACTION_KEYS.index("expand")]   -= 10
    if nation["military"] >= 8:
        weights[ACTION_KEYS.index("expand")]   += 15
        weights[ACTION_KEYS.index("military")] -= 10
    if nation["economy"] >= 8:
        weights[ACTION_KEYS.index("expand")]   += 10
    if nation["economy"] <= 3:
        weights[ACTION_KEYS.index("economy")]  += 20
        weights[ACTION_KEYS.index("expand")]   -= 10

    weights = [max(0, w) for w in weights]
    return random.choices(ACTION_KEYS, weights=weights)[0]


# ─────────────────────────────────────────
# INDIVIDUAL ACTION HANDLERS
# ─────────────────────────────────────────

async def _action_expand(nation: dict, guild_id: int, conn) -> str | None:
    """Claim one adjacent uncontrolled hex."""
    name = nation["name"]
    our_hexes = await conn.fetch(
        "SELECT q, r FROM hex_map WHERE guild_id=$1 AND controlled_by=$2",
        guild_id, name
    )
    if not our_hexes:
        return None

    candidates = []
    for h in our_hexes:
        for nq, nr in get_neighbors(h["q"], h["r"]):
            if not in_bounds(nq, nr):
                continue
            cell = await conn.fetchrow(
                "SELECT controlled_by, terrain FROM hex_map WHERE guild_id=$1 AND q=$2 AND r=$3",
                guild_id, nq, nr
            )
            if cell and cell["controlled_by"] is None and cell["terrain"] != "sea":
                candidates.append((nq, nr))

    if not candidates:
        return None

    q, r = random.choice(candidates)
    await conn.execute(
        "UPDATE hex_map SET controlled_by=$1 WHERE guild_id=$2 AND q=$3 AND r=$4",
        name, guild_id, q, r
    )
    # Small stability cost for expansion
    await conn.execute(
        "UPDATE npc_nations SET stability=GREATEST(1, stability-1) WHERE guild_id=$1 AND name=$2",
        guild_id, name
    )
    return f"**{name}** has expanded its borders, claiming new territory for the {nation['government_type']}."


async def _action_policy(nation: dict, guild_id: int, conn) -> str | None:
    """Internal policy — boost stability."""
    name = nation["name"]
    gain = random.randint(1, 2)
    await conn.execute(
        "UPDATE npc_nations SET stability=LEAST(10, stability+$1) WHERE guild_id=$2 AND name=$3",
        gain, guild_id, name
    )
    policies = [
        f"**{name}** has enacted sweeping domestic reforms, bolstering public order.",
        f"The {nation['government_type']} of **{name}** has issued new edicts to pacify the populace.",
        f"**{name}**'s ruling council has passed stabilising legislation, easing internal tensions.",
        f"A new administration in **{name}** pledges order and prosperity to its subjects.",
    ]
    return random.choice(policies)


async def _action_economy(nation: dict, guild_id: int, conn) -> str | None:
    """Economic growth — boost economy stat."""
    name = nation["name"]
    gain = random.randint(1, 2)
    await conn.execute(
        "UPDATE npc_nations SET economy=LEAST(10, economy+$1) WHERE guild_id=$2 AND name=$3",
        gain, guild_id, name
    )
    lines = [
        f"**{name}** has opened new trade routes, enriching its merchants and filling its coffers.",
        f"Industrial investment in **{name}** has borne fruit — its economy grows stronger.",
        f"A bumper harvest and booming markets have swelled **{name}**'s treasury.",
        f"**{name}** has negotiated favourable tariffs with its neighbours, spurring commerce.",
    ]
    return random.choice(lines)


async def _action_military(nation: dict, guild_id: int, conn) -> str | None:
    """Military buildup."""
    name = nation["name"]
    gain = random.randint(1, 2)
    await conn.execute(
        "UPDATE npc_nations SET military=LEAST(10, military+$1) WHERE guild_id=$2 AND name=$3",
        gain, guild_id, name
    )
    lines = [
        f"**{name}** has conscripted fresh battalions and sharpened its martial edge.",
        f"The armies of **{name}** grow in number and discipline — a warning to its neighbours.",
        f"**{name}** has invested heavily in its armed forces. Its generals grow bold.",
        f"New fortifications and armaments signal **{name}**'s growing military ambition.",
    ]
    return random.choice(lines)


async def _action_diplomacy(nation: dict, guild_id: int, conn) -> str | None:
    """Shift disposition toward player nation — can become more friendly or more hostile."""
    name = nation["name"]
    current = nation["disposition"]
    rng = random.random()

    # High stability/economy → more likely to go friendly; low → hostile
    friendly_chance = 0.3 + (nation["stability"] - 5) * 0.04 + (nation["economy"] - 5) * 0.04

    if current == "hostile":
        if rng < friendly_chance:
            new_disp = "neutral"
            msg = f"**{name}** has extended a cautious hand of diplomacy. Relations shift from hostility toward neutrality."
        else:
            return None  # stays hostile, no event
    elif current == "neutral":
        if rng < friendly_chance:
            new_disp = "friendly"
            msg = f"**{name}** has warmly expressed its desire for amity. Relations with the Empire grow cordial."
        else:
            new_disp = "hostile"
            msg = f"**{name}** has adopted an aggressive posture. Its rhetoric toward the Empire turns hostile."
    else:  # friendly
        if rng < 0.15:
            new_disp = "neutral"
            msg = f"**{name}** has grown cool in its friendship. Relations slip back toward neutrality."
        else:
            return None  # stays friendly

    await conn.execute(
        "UPDATE npc_nations SET disposition=$1 WHERE guild_id=$2 AND name=$3",
        new_disp, guild_id, name
    )
    return msg


async def _action_crisis(nation: dict, guild_id: int, conn) -> str | None:
    """Internal crisis — lose stability, possibly trigger civil war / collapse."""
    name = nation["name"]
    loss = random.randint(1, 3)
    new_stab = max(1, nation["stability"] - loss)
    await conn.execute(
        "UPDATE npc_nations SET stability=$1 WHERE guild_id=$2 AND name=$3",
        new_stab, guild_id, name
    )

    if new_stab <= 2:
        lines = [
            f"**{name}** teeters on the brink of collapse — revolution grips its streets and the government is besieged.",
            f"A coup has rocked **{name}**. The old order crumbles and the future is uncertain.",
            f"**{name}** has descended into civil war. Its armies turn upon each other.",
        ]
    else:
        lines = [
            f"**{name}** is beset by famine and unrest. The people cry out against their rulers.",
            f"Scandal and mismanagement have destabilised **{name}**'s government.",
            f"**{name}** faces a crisis of confidence — its institutions are strained to breaking point.",
            f"Riots have broken out across **{name}**. The constabulary struggles to maintain order.",
        ]
    return random.choice(lines)


async def _action_threaten_player(nation: dict, guild_id: int, conn) -> str | None:
    """
    Hostile nation with high military pressures the player nation:
    raises player unrest slightly and posts a warning.
    Only fires if disposition=hostile and military >= 6.
    """
    if nation["disposition"] != "hostile" or nation["military"] < 6:
        return None
    name = nation["name"]
    unrest_gain = random.randint(3, 8)
    await conn.execute(
        "UPDATE nation_state SET public_unrest=LEAST(100, public_unrest+$1) WHERE guild_id=$2",
        unrest_gain, guild_id
    )
    lines = [
        f"**{name}** has massed troops near our frontier. The populace grows nervous.",
        f"An ultimatum has arrived from **{name}**. The Empire must respond — or face consequences.",
        f"Spies report that **{name}** is mobilising. The war drums beat ever closer.",
        f"**{name}** has conducted provocative military manoeuvres on our border.",
    ]
    return random.choice(lines)


async def _action_inter_npc_war(nation: dict, guild_id: int, conn) -> str | None:
    """
    Two NPC nations fight over a border hex.
    Attacker steals one hex from a neighbour if it wins.
    """
    name = nation["name"]
    # Find neighbouring NPC nations
    our_hexes = await conn.fetch(
        "SELECT q, r FROM hex_map WHERE guild_id=$1 AND controlled_by=$2",
        guild_id, name
    )
    neighbour_names = set()
    border_hexes = {}
    for h in our_hexes:
        for nq, nr in get_neighbors(h["q"], h["r"]):
            cell = await conn.fetchrow(
                "SELECT controlled_by FROM hex_map WHERE guild_id=$1 AND q=$2 AND r=$3",
                guild_id, nq, nr
            )
            if cell and cell["controlled_by"] and cell["controlled_by"] != name \
                    and cell["controlled_by"] != "player_nation":
                neighbour_names.add(cell["controlled_by"])
                border_hexes.setdefault(cell["controlled_by"], []).append((nq, nr))

    if not neighbour_names:
        return None

    target_name = random.choice(list(neighbour_names))
    target = await conn.fetchrow(
        "SELECT military, stability FROM npc_nations WHERE guild_id=$1 AND name=$2 AND is_defeated=FALSE",
        guild_id, target_name
    )
    if not target:
        return None

    # Simple combat roll: attacker military + d6 vs defender military + d6
    att_roll = nation["military"] + random.randint(1, 6)
    def_roll = target["military"] + random.randint(1, 6)

    if att_roll > def_roll:
        # Attacker wins — steal one hex
        stolen_hexes = border_hexes.get(target_name, [])
        if stolen_hexes:
            sq, sr = random.choice(stolen_hexes)
            await conn.execute(
                "UPDATE hex_map SET controlled_by=$1 WHERE guild_id=$2 AND q=$3 AND r=$4",
                name, guild_id, sq, sr
            )
        # Defender loses stability
        await conn.execute(
            "UPDATE npc_nations SET stability=GREATEST(1, stability-2) WHERE guild_id=$1 AND name=$2",
            guild_id, target_name
        )
        return (
            f"**{name}** has launched a war of aggression against **{target_name}**, "
            f"seizing territory by force of arms. {target_name} reels from the assault."
        )
    else:
        # Defender holds — attacker loses stability
        await conn.execute(
            "UPDATE npc_nations SET stability=GREATEST(1, stability-1) WHERE guild_id=$1 AND name=$2",
            guild_id, name
        )
        return (
            f"**{name}** attempted an incursion into **{target_name}** but was repulsed. "
            f"The assault has failed, and {name}'s forces retreat in disorder."
        )


# ─────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────

async def run_npc_turns(guild_id: int, conn) -> list[str]:
    """
    Run one AI turn for every living NPC nation.
    Returns a list of event strings for the turn narrative.
    """
    nations = await conn.fetch("""
        SELECT name, government_type, military, economy, stability, disposition
        FROM npc_nations
        WHERE guild_id=$1 AND is_defeated=FALSE
        ORDER BY name
    """, guild_id)

    events = []

    for nation in nations:
        n = dict(nation)
        action = _pick_action(n["government_type"], n)

        # Occasionally override to threaten player or attack neighbour
        if n["disposition"] == "hostile" and n["military"] >= 6 and random.random() < 0.20:
            action = "threaten"
        if n["military"] >= 7 and random.random() < 0.12:
            action = "inter_npc_war"

        try:
            if action == "expand":
                result = await _action_expand(n, guild_id, conn)
            elif action == "policy":
                result = await _action_policy(n, guild_id, conn)
            elif action == "economy":
                result = await _action_economy(n, guild_id, conn)
            elif action == "military":
                result = await _action_military(n, guild_id, conn)
            elif action == "diplomacy":
                result = await _action_diplomacy(n, guild_id, conn)
            elif action == "crisis":
                result = await _action_crisis(n, guild_id, conn)
            elif action == "threaten":
                result = await _action_threaten_player(n, guild_id, conn)
            elif action == "inter_npc_war":
                result = await _action_inter_npc_war(n, guild_id, conn)
            else:
                result = None

            if result:
                events.append(result)

        except Exception as e:
            print(f"NPC AI error for {n['name']}: {e}")

    # Check for defeated nations (0 hexes left)
    for nation in nations:
        name = nation["name"]
        hex_count = await conn.fetchval(
            "SELECT COUNT(*) FROM hex_map WHERE guild_id=$1 AND controlled_by=$2",
            guild_id, name
        )
        if hex_count == 0:
            await conn.execute(
                "UPDATE npc_nations SET is_defeated=TRUE WHERE guild_id=$1 AND name=$2",
                guild_id, name
            )
            events.append(
                f"**{name}** has been utterly destroyed. Its territories lie vacant, "
                f"awaiting annexation by a bolder power."
            )

    return events
