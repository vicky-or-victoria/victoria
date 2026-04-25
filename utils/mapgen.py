"""
Procedural hex map generation for V.I.C.T.O.R.I.A.
Uses axial coordinates on a 19x19 hex grid.
Player nation starts as a 4-hex cluster near center.
"""
import random
import math
from typing import List, Tuple, Dict

# Grid radius (19x19 effective)
GRID_RADIUS = 9

TERRAIN_TYPES = ["plains", "hills", "forest", "coast", "mountain", "sea"]
TERRAIN_WEIGHTS = [35, 20, 20, 10, 10, 5]

GOVERNMENT_TYPES = ["monarchy", "empire", "republic", "theocracy", "oligarchy", "sultanate", "duchy"]

NATION_NAME_PARTS = {
    "prefix": ["Nord", "Sul", "Ast", "Vel", "Kor", "Mar", "Dun", "Eld", "Fen", "Gal",
               "Hav", "Ith", "Jas", "Kal", "Lor", "Mor", "Nav", "Orm", "Per", "Quin"],
    "suffix": ["ia", "heim", "burg", "mark", "land", "ora", "ath", "ess", "on", "um",
               "avia", "thor", "wyn", "ford", "gate", "moor", "vale", "crest", "reach", "hold"],
}

def axial_to_offset(q: int, r: int) -> Tuple[int, int]:
    col = q + (r - (r & 1)) // 2
    row = r
    return col, row

def axial_distance(q1: int, r1: int, q2: int, r2: int) -> int:
    return (abs(q1 - q2) + abs(q1 + r1 - q2 - r2) + abs(r1 - r2)) // 2

def get_neighbors(q: int, r: int) -> List[Tuple[int, int]]:
    directions = [(1,0),(-1,0),(0,1),(0,-1),(1,-1),(-1,1)]
    return [(q+dq, r+dr) for dq, dr in directions]

def in_bounds(q: int, r: int) -> bool:
    return abs(q) <= GRID_RADIUS and abs(r) <= GRID_RADIUS and abs(q+r) <= GRID_RADIUS

def generate_nation_name() -> str:
    return random.choice(NATION_NAME_PARTS["prefix"]) + random.choice(NATION_NAME_PARTS["suffix"])

def generate_hex_map(guild_id: int) -> Dict:
    """
    Returns dict with:
      - hexes: list of (guild_id, q, r, terrain, controlled_by, is_player_nation)
      - npc_nations: list of nation dicts
      - player_hexes: list of (q, r) for player nation start
    """
    rng = random.Random()

    all_hexes = []
    terrain_map = {}

    # Generate all hexes in radius
    for q in range(-GRID_RADIUS, GRID_RADIUS + 1):
        for r in range(-GRID_RADIUS, GRID_RADIUS + 1):
            if abs(q + r) <= GRID_RADIUS:
                terrain = rng.choices(TERRAIN_TYPES, TERRAIN_WEIGHTS)[0]
                terrain_map[(q, r)] = terrain
                all_hexes.append((q, r))

    # Player nation: 4-hex cluster near center (offset slightly from 0,0)
    player_center = (2, -1)
    player_hexes = [player_center]
    for dq, dr in [(1,0),(0,1),(-1,1)]:
        pq, pr = player_center[0]+dq, player_center[1]+dr
        if in_bounds(pq, pr):
            player_hexes.append((pq, pr))
            terrain_map[(pq, pr)] = "plains"

    # Place NPC nations: 8–12 nations, each with 3–7 hex territories
    occupied = set(player_hexes)
    npc_nations = []
    npc_assignments = {}  # hex -> nation name

    num_nations = rng.randint(9, 13)
    attempts = 0
    while len(npc_nations) < num_nations and attempts < 500:
        attempts += 1
        # Pick a random center far enough from player
        candidate = rng.choice(all_hexes)
        cq, cr = candidate
        if axial_distance(cq, cr, player_center[0], player_center[1]) < 5:
            continue
        if candidate in occupied:
            continue

        # Expand territory
        territory = [candidate]
        frontier = [candidate]
        size = rng.randint(3, 7)
        while len(territory) < size and frontier:
            cell = rng.choice(frontier)
            for nq, nr in get_neighbors(*cell):
                if in_bounds(nq, nr) and (nq, nr) not in occupied and len(territory) < size:
                    territory.append((nq, nr))
                    frontier.append((nq, nr))
                    occupied.add((nq, nr))
            frontier.remove(cell)

        if len(territory) < 2:
            continue

        name = generate_nation_name()
        # Ensure unique names
        existing_names = {n["name"] for n in npc_nations}
        tries = 0
        while name in existing_names and tries < 10:
            name = generate_nation_name()
            tries += 1

        nation = {
            "name": name,
            "government_type": rng.choice(GOVERNMENT_TYPES),
            "military": rng.randint(3, 8),
            "economy": rng.randint(3, 8),
            "stability": rng.randint(4, 9),
            "disposition": rng.choices(["friendly","neutral","hostile"], [20,50,30])[0],
            "capital_q": territory[0][0],
            "capital_r": territory[0][1],
            "hexes": territory,
        }
        npc_nations.append(nation)
        for hq, hr in territory:
            npc_assignments[(hq, hr)] = name

    # Build final hex list
    hex_rows = []
    for (q, r) in all_hexes:
        terrain = terrain_map.get((q, r), "plains")
        is_player = (q, r) in player_hexes
        if is_player:
            controlled_by = "player_nation"
        elif (q, r) in npc_assignments:
            controlled_by = npc_assignments[(q, r)]
        else:
            controlled_by = None
        hex_rows.append({
            "guild_id": guild_id,
            "q": q,
            "r": r,
            "terrain": terrain,
            "controlled_by": controlled_by,
            "is_player_nation": is_player,
        })

    return {
        "hexes": hex_rows,
        "npc_nations": npc_nations,
        "player_hexes": player_hexes,
    }


async def save_map_to_db(guild_id: int, conn):
    """Generate and persist a map for a guild."""
    data = generate_hex_map(guild_id)

    # Insert hexes
    await conn.executemany("""
        INSERT INTO hex_map (guild_id, q, r, terrain, controlled_by, is_player_nation)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (guild_id, q, r) DO NOTHING
    """, [
        (h["guild_id"], h["q"], h["r"], h["terrain"], h["controlled_by"], h["is_player_nation"])
        for h in data["hexes"]
    ])

    # Insert NPC nations
    await conn.executemany("""
        INSERT INTO npc_nations (guild_id, name, government_type, military, economy, stability, disposition, capital_q, capital_r)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (guild_id, name) DO NOTHING
    """, [
        (guild_id, n["name"], n["government_type"], n["military"], n["economy"],
         n["stability"], n["disposition"], n["capital_q"], n["capital_r"])
        for n in data["npc_nations"]
    ])

    # Init nation state
    await conn.execute("""
        INSERT INTO nation_state (guild_id, hex_count)
        VALUES ($1, $2)
        ON CONFLICT (guild_id) DO NOTHING
    """, guild_id, len(data["player_hexes"]))

    return data
