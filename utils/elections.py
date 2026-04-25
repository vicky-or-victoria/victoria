"""
Election resolution for V.I.C.T.O.R.I.A.
Tallies NPC mass opinion to fill cabinet seats.
"""
from db.connection import get_pool


async def resolve_election(guild_id: int, conn) -> dict:
    """
    Resolve an election cycle.
    Top 10 players by opinion_rating fill cabinet seats in order.
    Returns list of seat assignment results.
    """
    # Get all active players sorted by opinion_rating desc
    players = await conn.fetch("""
        SELECT id, user_id, character_name, opinion_rating, legitimacy
        FROM players
        WHERE guild_id = $1 AND is_active = TRUE
        ORDER BY (opinion_rating * 0.7 + legitimacy * 3) DESC
    """, guild_id)

    seats = await conn.fetch("""
        SELECT seat_number, title FROM cabinet_seats
        WHERE guild_id = $1
        ORDER BY seat_number ASC
    """, guild_id)

    results = []

    for i, seat in enumerate(seats):
        seat_number = seat["seat_number"]
        title = seat["title"]

        # Get current holder for leaderboard tracking
        current = await conn.fetchrow("""
            SELECT player_id, turns_held FROM cabinet_assignments
            WHERE guild_id = $1 AND seat_number = $2
        """, guild_id, seat_number)

        new_player = players[i] if i < len(players) else None
        new_player_id = new_player["id"] if new_player else None

        # Record leaderboard entry if seat was held
        if current and current["player_id"] and current["player_id"] != new_player_id:
            await conn.execute("""
                UPDATE leaderboard SET ended_at = NOW()
                WHERE guild_id = $1 AND player_id = $2 AND ended_at IS NULL
            """, guild_id, current["player_id"])

        # Assign new player
        await conn.execute("""
            UPDATE cabinet_assignments
            SET player_id = $1, turns_held = 0, assigned_at = NOW()
            WHERE guild_id = $2 AND seat_number = $3
        """, new_player_id, guild_id, seat_number)

        # Start leaderboard entry for new holder
        if new_player_id:
            await conn.execute("""
                INSERT INTO leaderboard (guild_id, player_id, seat_number, seat_title, started_at)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT DO NOTHING
            """, guild_id, new_player_id, seat_number, title)

        results.append({
            "seat_number": seat_number,
            "title": title,
            "winner_name": new_player["character_name"] if new_player else None,
            "winner_id": new_player_id,
        })

    # Issue new Royal Ambition and lift Crown Rule after election
    from utils.empress import issue_new_ambition, lift_crown_rule
    await lift_crown_rule(guild_id, conn)
    await issue_new_ambition(guild_id, conn)

    return {"results": results}


async def resolve_confidence_vote(vote_id: int, conn) -> dict:
    """
    Resolve a confidence vote by majority.
    Returns outcome dict.
    """
    vote = await conn.fetchrow("""
        SELECT * FROM confidence_votes WHERE id = $1
    """, vote_id)

    if not vote or vote["resolved"]:
        return {"resolved": False}

    total = vote["votes_confidence"] + vote["votes_no_confidence"]
    if total == 0:
        # Auto-resolve: no confidence wins if triggered by low opinion
        no_confidence = True
    else:
        no_confidence = vote["votes_no_confidence"] > vote["votes_confidence"]

    if no_confidence:
        # Vacate the seat
        await conn.execute("""
            UPDATE cabinet_assignments SET player_id = NULL, turns_held = 0
            WHERE guild_id = $1 AND seat_number = $2
        """, vote["guild_id"], vote["seat_number"])

    await conn.execute("""
        UPDATE confidence_votes SET resolved = TRUE, resolved_at = NOW()
        WHERE id = $1
    """, vote_id)

    return {
        "resolved": True,
        "no_confidence": no_confidence,
        "seat_number": vote["seat_number"],
        "votes_for": vote["votes_confidence"],
        "votes_against": vote["votes_no_confidence"],
    }
