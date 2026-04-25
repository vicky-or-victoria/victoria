"""
Turn resolution engine for V.I.C.T.O.R.I.A. v2
Handles AP-gated formal actions, dossier updates, title awards, and gazette posts.
"""
import random
import os
from openai import AsyncOpenAI
from db.connection import get_pool
from models.actions import ACTIONS

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ─────────────────────────────────────────
# TITLE DEFINITIONS
# ─────────────────────────────────────────
TITLES = {
    "the_betrayer":       {"name": "The Betrayer",        "condition": "broke_alliances",    "threshold": 3},
    "iron_chancellor":    {"name": "The Iron Chancellor",  "condition": "passed_legislation", "threshold": 10},
    "the_loyalist":       {"name": "The Loyalist",         "condition": "high_favour_turns",  "threshold": 5},
    "the_agitator":       {"name": "The Agitator",         "condition": "unrest_raised",      "threshold": 5},
    "the_spymaster":      {"name": "The Spymaster",        "condition": "intel_gathered",     "threshold": 5},
    "the_orator":         {"name": "The Great Orator",     "condition": "speeches_given",     "threshold": 8},
    "the_warmonger":      {"name": "The Warmonger",        "condition": "wars_declared",      "threshold": 2},
    "the_peacemaker":     {"name": "The Peacemaker",       "condition": "wars_ended",         "threshold": 2},
    "the_scandalmonger":  {"name": "The Scandalmonger",    "condition": "corruptions_exposed","threshold": 5},
    "the_incorruptible":  {"name": "The Incorruptible",    "condition": "bribes_refused",     "threshold": 3},
}


def roll_d10() -> int:
    return random.randint(1, 10)


def resolve_action(action_key: str, player_stats: dict, action_data: dict) -> dict:
    action = ACTIONS.get(action_key)
    if not action:
        return {"success": "fail", "roll": 0, "effects_applied": {}, "narrative_hint": "Unknown action.", "action_key": action_key, "action_label": "Unknown"}

    stat_val = player_stats.get(action["primary_stat"], 3)
    roll = roll_d10() + stat_val
    difficulty = action["difficulty"]

    if roll >= difficulty + 3:
        success = "full"
    elif roll >= difficulty:
        success = "partial"
    else:
        success = "fail"

    return {
        "success": success,
        "roll": roll,
        "difficulty": difficulty,
        "effects_applied": action.get("effects", {}),
        "narrative_hint": f"{action['label']} — {success.upper()} (rolled {roll} vs DC {difficulty})",
        "action_key": action_key,
        "action_label": action["label"],
    }


async def apply_action_effects(guild_id: int, player_id: int, action_key: str, outcome: dict, action_data: dict, conn):
    """Apply mechanical effects of a resolved action."""
    success = outcome["success"]
    if success == "fail":
        return

    multiplier = 1.0 if success == "full" else 0.5

    if action_key == "public_speech":
        delta = int(random.randint(5, 15) * multiplier)
        await conn.execute("""
            UPDATE players SET opinion_rating = LEAST(100, opinion_rating + $1) WHERE id = $2
        """, delta, player_id)
        await _log_dossier(guild_id, player_id, "action",
            f"Delivered a public address. Opinion Rating +{delta}.", conn)

    elif action_key == "suppress_unrest":
        delta = int(random.randint(10, 20) * multiplier)
        await conn.execute("""
            UPDATE nation_state SET public_unrest = GREATEST(0, public_unrest - $1) WHERE guild_id = $2
        """, delta, guild_id)

    elif action_key == "pass_legislation":
        stab = int(random.randint(5, 15) * multiplier)
        op = int(random.randint(3, 10) * multiplier)
        await conn.execute("""
            UPDATE nation_state SET stability = LEAST(100, stability + $1) WHERE guild_id = $2
        """, stab, guild_id)
        await conn.execute("""
            UPDATE players SET opinion_rating = LEAST(100, opinion_rating + $1) WHERE id = $2
        """, op, player_id)
        await _log_dossier(guild_id, player_id, "action",
            f"Passed legislation. Stability +{stab}, Opinion +{op}.", conn)
        await _check_title(guild_id, player_id, "passed_legislation", conn)

    elif action_key == "economic_decree":
        gain = int(random.randint(100, 200) * multiplier)
        await conn.execute("""
            UPDATE nation_state SET treasury = treasury + $1 WHERE guild_id = $2
        """, gain, guild_id)

    elif action_key == "foment_unrest":
        delta = int(random.randint(10, 20) * multiplier)
        await conn.execute("""
            UPDATE nation_state SET public_unrest = LEAST(100, public_unrest + $1),
            stability = GREATEST(0, stability - 5) WHERE guild_id = $2
        """, delta, guild_id)
        await _check_title(guild_id, player_id, "unrest_raised", conn)

    elif action_key == "bribe_official":
        cost = int(random.randint(50, 100))
        gain = int(random.randint(3, 8) * multiplier)
        await conn.execute("""
            UPDATE nation_state SET treasury = GREATEST(0, treasury - $1) WHERE guild_id = $2
        """, cost, guild_id)
        await conn.execute("""
            UPDATE players SET opinion_rating = LEAST(100, opinion_rating + $1) WHERE id = $2
        """, gain, player_id)

    elif action_key == "gather_intelligence":
        # Store intelligence result in action_data for later use
        target_name = action_data.get("target_name", "")
        target = await conn.fetchrow("""
            SELECT id, character_name FROM players
            WHERE guild_id = $1 AND character_name ILIKE $2
        """, guild_id, f"%{target_name}%")
        if target and success == "full":
            # Store pending actions count as intelligence
            pending = await conn.fetchval("""
                SELECT COUNT(*) FROM turn_actions
                WHERE guild_id = $1 AND player_id = $2 AND resolved = FALSE
            """, guild_id, target["id"])
            await conn.execute("""
                UPDATE turn_actions SET action_data = action_data || $1
                WHERE guild_id = $2 AND player_id = $3 AND action_key = 'gather_intelligence' AND resolved = FALSE
            """, f'{{"intel_on": "{target["character_name"]}", "pending_actions": {pending}}}', guild_id, player_id)
        await _check_title(guild_id, player_id, "intel_gathered", conn)

    elif action_key == "expose_corruption":
        target_name = action_data.get("target_name", "")
        target = await conn.fetchrow("""
            SELECT id FROM players WHERE guild_id = $1 AND character_name ILIKE $2
        """, guild_id, f"%{target_name}%")
        if target:
            delta = int(random.randint(10, 25) * multiplier)
            await conn.execute("""
                UPDATE players SET opinion_rating = GREATEST(0, opinion_rating - $1) WHERE id = $2
            """, delta, target["id"])
            await _log_dossier(guild_id, player_id, "action",
                f"Exposed corruption against {target_name}. Their Opinion Rating -{delta}.", conn)
        await _check_title(guild_id, player_id, "corruptions_exposed", conn)

    elif action_key in ("issue_royal_warrant", "arrest_warrant"):
        target_name = action_data.get("target_name", "")
        target = await conn.fetchrow("""
            SELECT id FROM players WHERE guild_id = $1 AND character_name ILIKE $2
        """, guild_id, f"%{target_name}%")
        if target:
            nation = await conn.fetchrow("SELECT turn_number FROM nation_state WHERE guild_id = $1", guild_id)
            turn = nation["turn_number"] if nation else 1
            await conn.execute("""
                UPDATE players SET is_silenced = TRUE, silenced_until_turn = $1 WHERE id = $2
            """, turn + 1, target["id"])

    elif action_key == "dissolve_parliament":
        if success == "full":
            # Trigger snap election — set next election to now
            await conn.execute("""
                UPDATE guild_config SET next_election_at = NOW() WHERE guild_id = $1
            """, guild_id)
            await conn.execute("""
                UPDATE nation_state SET stability = GREATEST(0, stability - 10) WHERE guild_id = $1
            """, guild_id)

    elif action_key == "diplomatic_overture":
        target_nation = action_data.get("target_nation", "")
        if target_nation:
            # Advance disposition: hostile→neutral, neutral→friendly
            current = await conn.fetchrow("""
                SELECT disposition FROM npc_nations WHERE guild_id = $1 AND name ILIKE $2
            """, guild_id, f"%{target_nation}%")
            if current:
                new_disp = {"hostile": "neutral", "neutral": "friendly"}.get(current["disposition"], "friendly")
                await conn.execute("""
                    UPDATE npc_nations SET disposition = $1 WHERE guild_id = $2 AND name ILIKE $3
                """, new_disp, guild_id, f"%{target_nation}%")

    elif action_key == "propaganda_campaign":
        delta = int(random.randint(3, 8) * multiplier)
        # Raise all cabinet members' opinion
        await conn.execute("""
            UPDATE players SET opinion_rating = LEAST(100, opinion_rating + $1)
            WHERE guild_id = $2 AND id IN (
                SELECT player_id FROM cabinet_assignments WHERE guild_id = $2 AND player_id IS NOT NULL
            )
        """, delta, guild_id)

    elif action_key == "campaign_for_election":
        op = int(random.randint(5, 10) * multiplier)
        leg = int(random.randint(1, 2) * multiplier)
        await conn.execute("""
            UPDATE players SET opinion_rating = LEAST(100, opinion_rating + $1),
            legitimacy = LEAST(10, legitimacy + $2) WHERE id = $3
        """, op, leg, player_id)

    elif action_key == "manipulate_treasury":
        target_name = action_data.get("target_name", "")
        target = await conn.fetchrow("""
            SELECT id FROM players WHERE guild_id = $1 AND character_name ILIKE $2
        """, guild_id, f"%{target_name}%")
        if target:
            await conn.execute("""
                UPDATE players SET wealth = GREATEST(1, wealth - 2) WHERE id = $1
            """, target["id"])

    elif action_key == "fund_campaign":
        gain = int(random.randint(10, 25) * multiplier)
        await conn.execute("""
            UPDATE war_campaigns SET attacker_strength = attacker_strength + $1
            WHERE guild_id = $2 AND status = 'active'
        """, gain, guild_id)

    elif action_key == "declare_war":
        target_nation = action_data.get("target_nation", "")
        if target_nation and success != "fail":
            await conn.execute("""
                INSERT INTO war_campaigns (guild_id, target_nation, status, started_turn, attacker_strength, defender_strength)
                SELECT $1, $2, 'active', turn_number, 10, 10 FROM nation_state WHERE guild_id = $1
                ON CONFLICT DO NOTHING
            """, guild_id, target_nation)
            await conn.execute("""
                UPDATE nation_state SET public_unrest = LEAST(100, public_unrest + 10) WHERE guild_id = $1
            """, guild_id)
            await _log_dossier(guild_id, player_id, "action",
                f"Declared war upon {target_nation}.", conn)
        await _check_title(guild_id, player_id, "wars_declared", conn)

    elif action_key == "secret_armistice":
        await conn.execute("""
            UPDATE war_campaigns SET status = 'peace', ended_turn = (
                SELECT turn_number FROM nation_state WHERE guild_id = $1
            ) WHERE guild_id = $1 AND status = 'active'
        """, guild_id)
        await _check_title(guild_id, player_id, "wars_ended", conn)

    elif action_key == "riot":
        await conn.execute("""
            UPDATE nation_state SET public_unrest = LEAST(100, public_unrest + 25),
            stability = GREATEST(0, stability - 15) WHERE guild_id = $1
        """, guild_id)
        await conn.execute("""
            UPDATE players SET opinion_rating = GREATEST(0, opinion_rating - 10) WHERE id = $1
        """, player_id)

    elif action_key == "loyalty_pledge":
        await conn.execute("""
            UPDATE players SET loyalty = LEAST(100, loyalty + 10) WHERE id = $1
        """, player_id)
        from utils.empress import adjust_royal_favour
        pool = await get_pool()
        async with pool.acquire() as c:
            await adjust_royal_favour(guild_id, "loyalty_pledge", "full", c)


async def _log_dossier(guild_id: int, player_id: int, event_type: str, description: str, conn):
    """Add an entry to a player's dossier."""
    from utils.gazette import format_vic_date
    config = await conn.fetchrow(
        "SELECT vic_year, vic_month, vic_day FROM guild_config WHERE guild_id = $1", guild_id
    )
    nation = await conn.fetchrow("SELECT turn_number FROM nation_state WHERE guild_id = $1", guild_id)
    vic_date = format_vic_date(
        config["vic_year"] if config else 1878,
        config["vic_month"] if config else 1,
        config["vic_day"] if config else 1,
    )
    turn = nation["turn_number"] if nation else 1
    await conn.execute("""
        INSERT INTO dossiers (guild_id, player_id, event_type, description, turn_number, vic_date)
        VALUES ($1, $2, $3, $4, $5, $6)
    """, guild_id, player_id, event_type, description, turn, vic_date)


async def _check_title(guild_id: int, player_id: int, condition: str, conn):
    """Award titles based on dossier milestones."""
    for title_key, title_data in TITLES.items():
        if title_data["condition"] != condition:
            continue
        # Count matching dossier entries
        count = await conn.fetchval("""
            SELECT COUNT(*) FROM dossiers
            WHERE guild_id = $1 AND player_id = $2 AND description ILIKE $3
        """, guild_id, player_id, f"%{condition.replace('_', ' ')}%")

        if (count or 0) >= title_data["threshold"]:
            await conn.execute("""
                INSERT INTO player_titles (guild_id, player_id, title_key, title_name)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (guild_id, player_id, title_key) DO NOTHING
            """, guild_id, player_id, title_key, title_data["name"])


async def resolve_turn(guild_id: int, bot=None) -> dict:
    """Main turn resolution. Returns result dict for gazette posting."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        nation = await conn.fetchrow("SELECT * FROM nation_state WHERE guild_id = $1", guild_id)
        if not nation:
            return {}

        turn_number = nation["turn_number"]

        # Fetch all pending actions
        actions = await conn.fetch("""
            SELECT ta.*, p.influence, p.charisma, p.cunning, p.resolve, p.wealth,
                   p.legitimacy, p.character_name, p.user_id, p.is_silenced
            FROM turn_actions ta
            JOIN players p ON p.id = ta.player_id
            WHERE ta.guild_id = $1 AND ta.turn_number = $2 AND ta.resolved = FALSE
            ORDER BY ta.submitted_at ASC
        """, guild_id, turn_number)

        events = []
        gazette_posts = []

        for action_row in actions:
            # Skip silenced players
            if action_row["is_silenced"]:
                await conn.execute("""
                    UPDATE turn_actions SET resolved = TRUE, outcome = 'silenced'
                    WHERE id = $1
                """, action_row["id"])
                continue

            player_stats = {
                "influence": action_row["influence"],
                "charisma": action_row["charisma"],
                "cunning": action_row["cunning"],
                "resolve": action_row["resolve"],
                "wealth": action_row["wealth"],
                "legitimacy": action_row["legitimacy"],
            }

            outcome = resolve_action(
                action_row["action_key"], player_stats,
                action_row["action_data"] or {}
            )

            await apply_action_effects(
                guild_id, action_row["player_id"],
                action_row["action_key"], outcome,
                action_row["action_data"] or {}, conn
            )

            # Adjust royal favour
            from utils.empress import adjust_royal_favour
            await adjust_royal_favour(guild_id, action_row["action_key"], outcome["success"], conn)

            # Mark resolved
            await conn.execute("""
                UPDATE turn_actions SET resolved = TRUE, outcome = $1, roll_result = $2
                WHERE id = $3
            """, outcome["success"], outcome["roll"], action_row["id"])

            events.append({
                **outcome,
                "character_name": action_row["character_name"],
                "user_id": action_row["user_id"],
            })

            # Gazette post for significant turn actions
            gazette_posts.append({
                "action_key": action_row["action_key"],
                "character_name": action_row["character_name"],
                "user_id": action_row["user_id"],
                "outcome": outcome["success"],
                "action_label": outcome["action_label"],
            })

        # Lift silences that have expired
        await conn.execute("""
            UPDATE players SET is_silenced = FALSE, silenced_until_turn = NULL
            WHERE guild_id = $1 AND is_silenced = TRUE AND silenced_until_turn <= $2
        """, guild_id, turn_number)

        # Advance cabinet turns_held
        await conn.execute("""
            UPDATE cabinet_assignments SET turns_held = turns_held + 1
            WHERE guild_id = $1 AND player_id IS NOT NULL
        """, guild_id)

        # Passive nation decay
        await conn.execute("""
            UPDATE nation_state SET
                public_unrest = LEAST(100, public_unrest + 2),
                stability = GREATEST(0, stability - 1),
                turn_number = turn_number + 1
            WHERE guild_id = $1
        """, guild_id)

        # Advance Victorian calendar
        config = await conn.fetchrow(
            "SELECT vic_year, vic_month, vic_day FROM guild_config WHERE guild_id = $1", guild_id
        )
        if config:
            from utils.gazette import advance_vic_date
            ny, nm, nd = advance_vic_date(
                config["vic_year"], config["vic_month"], config["vic_day"], days=7
            )
            await conn.execute("""
                UPDATE guild_config SET vic_year = $1, vic_month = $2, vic_day = $3
                WHERE guild_id = $4
            """, ny, nm, nd, guild_id)

        # Refresh nation state for result
        nation = await conn.fetchrow("SELECT * FROM nation_state WHERE guild_id = $1", guild_id)

        # Reset AP for all players
        await _reset_ap(guild_id, conn)

        # Check displeasure escalation
        from utils.empress import check_and_advance_displeasure
        await check_and_advance_displeasure(guild_id, conn, bot)

        # Gazette posts for notable actions
        if bot:
            await _post_action_gazette(bot, guild_id, conn, gazette_posts)

        result = {
            "turn_number": turn_number,
            "events": events,
            "stability": nation["stability"] if nation else 70,
            "treasury": nation["treasury"] if nation else 1000,
            "unrest": nation["public_unrest"] if nation else 20,
            "random_events": [],
        }

        # Store turn history
        await conn.execute("""
            INSERT INTO turn_history (guild_id, turn_number, narrative, raw_events, vic_date)
            VALUES ($1, $2, $3, $4::jsonb, $5)
        """, guild_id, turn_number,
            f"Turn {turn_number} resolved. {len(events)} actions processed.",
            str(events).replace("'", '"'),
            f"{config['vic_year']}-{config['vic_month']:02d}-{config['vic_day']:02d}" if config else ""
        )

        return result


async def _reset_ap(guild_id: int, conn):
    """Reset AP for all players based on their role."""
    config = await conn.fetchrow("""
        SELECT ap_cabinet_senior, ap_cabinet_junior, ap_opposition, ap_parliament
        FROM guild_config WHERE guild_id = $1
    """, guild_id)
    if not config:
        return

    senior_ap = config["ap_cabinet_senior"]
    junior_ap = config["ap_cabinet_junior"]
    opp_ap = config["ap_opposition"]
    parl_ap = config["ap_parliament"]

    # Senior cabinet (seats 1–5)
    await conn.execute("""
        UPDATE players SET ap_remaining = $1
        WHERE guild_id = $2 AND id IN (
            SELECT player_id FROM cabinet_assignments
            WHERE guild_id = $2 AND seat_number BETWEEN 1 AND 5 AND player_id IS NOT NULL
        )
    """, senior_ap, guild_id)

    # Junior cabinet (seats 6–10)
    await conn.execute("""
        UPDATE players SET ap_remaining = $1
        WHERE guild_id = $2 AND id IN (
            SELECT player_id FROM cabinet_assignments
            WHERE guild_id = $2 AND seat_number BETWEEN 6 AND 10 AND player_id IS NOT NULL
        )
    """, junior_ap, guild_id)

    # Parliament members
    await conn.execute("""
        UPDATE players SET ap_remaining = $1
        WHERE guild_id = $2 AND id IN (
            SELECT player_id FROM parliament_members WHERE guild_id = $2
        ) AND role_type = 'parliament'
    """, parl_ap, guild_id)

    # Everyone else (The People / opposition)
    await conn.execute("""
        UPDATE players SET ap_remaining = $1
        WHERE guild_id = $2 AND role_type = 'people'
    """, opp_ap, guild_id)


async def _post_action_gazette(bot, guild_id: int, conn, posts: list):
    """Post Tier B gazette entries for notable resolved actions."""
    from utils.gazette import post_tier_b
    import discord

    NOTABLE_ACTIONS = {
        "pass_legislation":   ("legislation_passed", "politics"),
        "expose_corruption":  ("corruption_exposed", "crisis"),
        "declare_war":        ("war_declared", "war"),
        "economic_decree":    ("economic_decree", "politics"),
        "propaganda_campaign":("legislation_passed", "society"),
        "bribe_official":     ("bribery_succeeded", "society"),
    }

    for post in posts:
        ak = post["action_key"]
        if ak not in NOTABLE_ACTIONS:
            continue
        template_key, section = NOTABLE_ACTIONS[ak]

        user = bot.get_user(post["user_id"])
        user_mention = user.mention if user else f"<@{post['user_id']}>"

        await post_tier_b(
            bot, guild_id, conn,
            section=section,
            template_key=template_key,
            character=post["character_name"],
            user_mention=user_mention,
            content=post["action_label"],
            target="",
            target_mention="",
            seat_title="",
        )
