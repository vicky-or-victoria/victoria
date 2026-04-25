"""
Empress Victoria I — displeasure escalation system for V.I.C.T.O.R.I.A. v2
Six stages of intervention, all AI-generated proclamations.
"""
import random
from openai import AsyncOpenAI
import os
from db.connection import get_pool

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ─────────────────────────────────────────
# AMBITION TEMPLATES
# ─────────────────────────────────────────
AMBITIONS = {
    "expansion": [
        "The Crown demands the annexation of at least two new territories before the next election.",
        "Her Majesty wishes to see the Imperial banner planted on foreign soil. Expand our borders.",
        "The Empress commands that our forces secure the eastern reaches. Territorial growth is paramount.",
    ],
    "economy": [
        "Her Majesty commands that the treasury be grown by no less than five hundred pounds this cycle.",
        "The Crown is displeased with the state of our coffers. Grow the economy or face Her wrath.",
        "The Empress has decreed that trade and industry must flourish. Fill the Imperial treasury.",
    ],
    "military": [
        "The Empress demands a show of military strength. Launch a campaign against a hostile power.",
        "Her Majesty is concerned our armed forces have grown complacent. Strengthen the military.",
        "The Crown requires that we demonstrate martial supremacy. Our enemies must be made to fear us.",
    ],
    "industry": [
        "Her Majesty wishes to see a new industrial sector established within the Empire.",
        "The Crown demands investment in the great industries of the age. Build and innovate.",
    ],
    "diplomacy": [
        "The Empress commands that at least one hostile nation be brought to neutrality through diplomacy.",
        "Her Majesty wishes to forge new alliances. Improve relations with our neighbours.",
    ],
    "stability": [
        "The Empress is alarmed by reports of civil unrest. Restore order and stability at once.",
        "Her Majesty demands that the rabble be silenced. Public unrest must not exceed ten percent.",
    ],
}

AMBITION_ACTIONS = {
    "expansion":  ["annex_hex", "declare_war", "fund_campaign"],
    "economy":    ["economic_decree", "fund_campaign", "diplomatic_overture"],
    "military":   ["declare_war", "fund_campaign", "suppress_unrest"],
    "industry":   ["economic_decree", "pass_legislation"],
    "diplomacy":  ["diplomatic_overture", "forge_alliance", "secret_treaty"],
    "stability":  ["suppress_unrest", "pass_legislation", "propaganda_campaign"],
}

# ─────────────────────────────────────────
# DISPLEASURE STAGE THRESHOLDS & EFFECTS
# ─────────────────────────────────────────
STAGES = {
    0: {
        "label":   "Silent",
        "range":   (0, 20),
        "desc":    "The Empress watches in silence. Occasional commendations reach the Cabinet.",
        "flavour": "Long live the Queen! The Empress is pleased.",
    },
    1: {
        "label":   "Restless",
        "range":   (21, 40),
        "desc":    "The Empress grows restless. Royal Decrees arrive — technically optional, but ignoring them costs opinion.",
        "flavour": "Her Majesty's patience begins to thin.",
        "penalty": "Ignoring decrees costs -5 Opinion Rating per turn.",
    },
    2: {
        "label":   "Impatient",
        "range":   (41, 60),
        "desc":    "The Empress begins vetoing legislation she disapproves of. Overriding her veto costs +2 AP.",
        "flavour": "The Royal veto pen scratches often.",
        "penalty": "Legislation aligned with Royal Ambition requires +2 AP to pass against Her veto.",
    },
    3: {
        "label":   "Wrathful",
        "range":   (61, 80),
        "desc":    "The Empress issues Royal Warrants. Ministers with Loyalty below 30 lose their next turn action.",
        "flavour": "The Crown's displeasure takes a more direct form.",
        "penalty": "Players with Loyalty < 30 are silenced for one turn.",
    },
    4: {
        "label":   "Furious",
        "range":   (81, 99),
        "desc":    "The Empress begins replacing Cabinet seats with NPC loyalists. Players fight to keep their seats.",
        "flavour": "The royal court moves to fill positions with trusted loyalists.",
        "penalty": "Cabinet seats with Loyalty < 20 may be vacated and filled by NPC loyalists.",
    },
    5: {
        "label":   "Crown Rule",
        "range":   (100, 100),
        "desc":    "Crown Rule invoked. The Empress governs alone. Parliament is prorogued.",
        "flavour": "Parliament stands dissolved. The Crown governs alone.",
        "penalty": "All Cabinet seats vacated. Players must coordinate a revolt to restore Parliament.",
    },
}

CONSTITUTIONAL_BILL_TEXT = (
    "**Constitutional Bill of 1709 — Invoked**\n\n"
    "By Royal Decree, as the Cabinet of Her Majesty's Government has failed to uphold "
    "the sacred duties of the Crown, the Monarch hereby assumes direct authority over "
    "all affairs of state. Parliament is prorogued. No subject shall hold ministerial "
    "office until a new election is duly called.\n\n"
    "*— Issued under the Seal of Empress Victoria I*"
)


# ─────────────────────────────────────────
# CORE OPERATIONS
# ─────────────────────────────────────────

async def get_empress(guild_id: int, conn):
    return await conn.fetchrow("SELECT * FROM empress WHERE guild_id = $1", guild_id)


async def seed_empress(guild_id: int, conn):
    ambition_type = random.choice(list(AMBITIONS.keys()))
    ambition_text = random.choice(AMBITIONS[ambition_type])
    await conn.execute("""
        INSERT INTO empress (guild_id, ambition_type, current_ambition, displeasure, stage)
        VALUES ($1, $2, $3, 0, 0)
        ON CONFLICT (guild_id) DO NOTHING
    """, guild_id, ambition_type, ambition_text)


async def issue_new_ambition(guild_id: int, conn) -> dict:
    ambition_type = random.choice(list(AMBITIONS.keys()))
    ambition_text = random.choice(AMBITIONS[ambition_type])
    await conn.execute("""
        UPDATE empress SET
            ambition_type = $1,
            current_ambition = $2,
            ambition_set_at = NOW()
        WHERE guild_id = $3
    """, ambition_type, ambition_text, guild_id)
    return {"ambition_type": ambition_type, "ambition_text": ambition_text}


async def adjust_displeasure(guild_id: int, delta: int, conn, bot=None) -> tuple[int, int]:
    """
    Adjust the Empress displeasure meter.
    Returns (new_displeasure, new_stage).
    Triggers gazette posts on stage transitions.
    """
    empress = await get_empress(guild_id, conn)
    if not empress:
        return 0, 0

    old_stage = empress["stage"]
    old_displeasure = empress["displeasure"]
    new_displeasure = max(0, min(100, old_displeasure + delta))

    # Determine new stage
    new_stage = old_stage
    for stage_num, stage_data in STAGES.items():
        lo, hi = stage_data["range"]
        if lo <= new_displeasure <= hi:
            new_stage = stage_num
            break

    await conn.execute("""
        UPDATE empress SET displeasure = $1, stage = $2 WHERE guild_id = $3
    """, new_displeasure, new_stage, guild_id)

    # Post gazette on stage transition
    if new_stage > old_stage and bot:
        from utils.gazette import post_empress_intervention
        config = await conn.fetchrow("SELECT nation_name FROM guild_config WHERE guild_id = $1", guild_id)
        nation_name = config["nation_name"] if config else "The Empire"
        await post_empress_intervention(bot, guild_id, conn, new_stage, nation_name)
        await _apply_stage_effects(guild_id, new_stage, conn, bot)

    return new_displeasure, new_stage


async def _apply_stage_effects(guild_id: int, stage: int, conn, bot):
    """Apply mechanical effects of a displeasure stage."""
    import discord

    if stage == 3:
        # Silence ministers with Loyalty < 30
        silenced = await conn.fetch("""
            SELECT p.id, p.character_name, ns.turn_number
            FROM players p
            JOIN cabinet_assignments ca ON ca.player_id = p.id AND ca.guild_id = p.guild_id
            CROSS JOIN nation_state ns ON ns.guild_id = p.guild_id
            WHERE p.guild_id = $1 AND p.loyalty < 30 AND p.is_silenced = FALSE
        """, guild_id)
        for row in silenced:
            await conn.execute("""
                UPDATE players SET is_silenced = TRUE, silenced_until_turn = $1
                WHERE id = $2
            """, row["turn_number"] + 1, row["id"])

    elif stage == 4:
        # Vacate seats held by players with Loyalty < 20
        await conn.execute("""
            UPDATE cabinet_assignments ca SET player_id = NULL
            FROM players p
            WHERE ca.player_id = p.id AND ca.guild_id = $1 AND p.loyalty < 20
        """, guild_id)

    elif stage == 5:
        # Crown Rule — vacate all seats
        await conn.execute("""
            UPDATE cabinet_assignments SET player_id = NULL, turns_held = 0
            WHERE guild_id = $1
        """, guild_id)
        decree = await _generate_decree(guild_id, conn)
        await conn.execute("""
            UPDATE empress SET
                is_crown_rule = TRUE,
                crown_rule_since = NOW(),
                last_decree = $1,
                decree_at = NOW()
            WHERE guild_id = $2
        """, decree, guild_id)

        if bot:
            config = await conn.fetchrow(
                "SELECT channel_events, header_image_url FROM guild_config WHERE guild_id = $1", guild_id
            )
            if config and config["channel_events"]:
                channel = bot.get_channel(config["channel_events"])
                if channel:
                    embed = discord.Embed(
                        title="👑 CROWN RULE INVOKED — Constitutional Bill of 1709",
                        description=decree,
                        color=0x6b0000,
                    )
                    try:
                        header_url = config["header_image_url"]
                        if header_url:
                            embed.set_image(url=header_url)
                    except (KeyError, TypeError):
                        pass
                    embed.set_footer(text="The Crown has assumed direct authority · V.I.C.T.O.R.I.A.")
                    await channel.send(embed=embed)


async def adjust_royal_favour(guild_id: int, action_key: str, success: str, conn) -> int:
    """Adjust Royal Favour and consequently Displeasure based on action alignment."""
    empress = await get_empress(guild_id, conn)
    if not empress:
        return 70

    ambition_type = empress["ambition_type"]
    aligned_actions = AMBITION_ACTIONS.get(ambition_type, [])

    favour_delta = 0
    displeasure_delta = 0

    if action_key in aligned_actions:
        if success == "full":
            favour_delta = random.randint(4, 8)
            displeasure_delta = -random.randint(3, 6)
        elif success == "partial":
            favour_delta = random.randint(1, 3)
            displeasure_delta = -random.randint(1, 3)
        else:
            favour_delta = -random.randint(2, 5)
            displeasure_delta = random.randint(3, 6)
    elif action_key in ("foment_unrest", "sabotage_legislation", "undermine_war_effort", "riot"):
        favour_delta = -random.randint(3, 7)
        displeasure_delta = random.randint(4, 8)
    elif action_key == "loyalty_pledge":
        favour_delta = random.randint(2, 5)
        displeasure_delta = -random.randint(2, 4)

    new_favour = max(0, min(100, empress["royal_favour"] + favour_delta))
    await conn.execute("""
        UPDATE empress SET royal_favour = $1 WHERE guild_id = $2
    """, new_favour, guild_id)

    return new_favour


async def check_and_advance_displeasure(guild_id: int, conn, bot=None):
    """Called each turn — check conditions and advance displeasure if warranted."""
    empress = await get_empress(guild_id, conn)
    if not empress or empress["is_crown_rule"]:
        return

    nation = await conn.fetchrow("SELECT * FROM nation_state WHERE guild_id = $1", guild_id)
    if not nation:
        return

    delta = 0

    # Low stability
    if nation["stability"] < 30:
        delta += 5
    elif nation["stability"] < 50:
        delta += 2

    # High unrest
    if nation["public_unrest"] > 70:
        delta += 5
    elif nation["public_unrest"] > 50:
        delta += 2

    # Low royal favour
    if empress["royal_favour"] < 20:
        delta += 8
    elif empress["royal_favour"] < 40:
        delta += 4

    # Cabinet pleasing the Empress lowers displeasure
    if empress["royal_favour"] > 70:
        delta -= 5
    elif empress["royal_favour"] > 50:
        delta -= 2

    if delta != 0:
        await adjust_displeasure(guild_id, delta, conn, bot)


async def lift_crown_rule(guild_id: int, conn):
    """Lift Crown Rule after a successful election."""
    await conn.execute("""
        UPDATE empress SET is_crown_rule = FALSE, crown_rule_since = NULL,
        displeasure = GREATEST(0, displeasure - 20), stage = GREATEST(0, stage - 1)
        WHERE guild_id = $1
    """, guild_id)


async def _generate_decree(guild_id: int, conn) -> str:
    empress = await get_empress(guild_id, conn)
    config = await conn.fetchrow("SELECT nation_name FROM guild_config WHERE guild_id = $1", guild_id)
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": (
                    f"You are Empress Victoria I of {config['nation_name'] if config else 'the Empire'}, "
                    f"a proud and imperious Victorian monarch. The Cabinet has failed to fulfil your royal ambition: "
                    f"'{empress['current_ambition']}'. "
                    f"Write a 2-sentence royal decree invoking the Constitutional Bill of 1709 in dramatic Victorian prose. "
                    f"Sign it as Empress Victoria I."
                )
            }]
        )
        return response.choices[0].message.content
    except Exception:
        return CONSTITUTIONAL_BILL_TEXT


# ─────────────────────────────────────────
# EMPRESS EMBED
# ─────────────────────────────────────────

async def build_empress_embed(guild_id: int, conn):
    import discord
    empress = await get_empress(guild_id, conn)
    config = await conn.fetchrow("SELECT nation_name, header_image_url FROM guild_config WHERE guild_id = $1", guild_id)

    if not empress:
        return discord.Embed(title="Empress not initialised.", color=0x8B0000)

    favour = empress["royal_favour"]
    displeasure = empress["displeasure"]
    stage = empress["stage"]
    stage_data = STAGES.get(stage, STAGES[0])

    favour_bar = "█" * (favour // 10) + "░" * (10 - favour // 10)
    displeasure_bar = "█" * (displeasure // 10) + "░" * (10 - displeasure // 10)
    favour_col = 0x228B22 if favour >= 60 else (0xFFD700 if favour >= 30 else 0x8B0000)

    crown_str = (
        "\n\n⚠️ **CROWN RULE IN EFFECT**\n"
        "*Parliament has been prorogued. The Empress governs directly.*"
    ) if empress["is_crown_rule"] else ""

    stage_warn = ""
    if stage >= 3:
        stage_warn = f"\n\n🔴 **Stage {stage} — {stage_data['label']}**\n*{stage_data['desc']}*"
    elif stage >= 1:
        stage_warn = f"\n\n⚠️ **Stage {stage} — {stage_data['label']}**\n*{stage_data['desc']}*"

    ambition_emoji = {
        "expansion": "🗺️", "economy": "💰", "military": "⚔️",
        "industry": "🏭", "diplomacy": "🤝", "stability": "⚖️"
    }.get(empress["ambition_type"], "📜")

    embed = discord.Embed(
        title=f"👑 {empress['name']}",
        description=(
            f"*Empress of the Realm, Sovereign of the Imperial Crown, Defender of the Faith*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{ambition_emoji} **Royal Ambition:**\n"
            f"*{empress['current_ambition']}*\n\n"
            f"**Royal Favour:**     `{favour_bar}` {favour}/100\n"
            f"**Her Displeasure:** `{displeasure_bar}` {displeasure}/100"
            f"{stage_warn}"
            f"{crown_str}"
        ),
        color=favour_col,
    )

    if empress["portrait_url"]:
        embed.set_image(url=empress["portrait_url"])
    elif config:
        try:
            header_url = config["header_image_url"]
            if header_url:
                embed.set_image(url=header_url)
        except (KeyError, TypeError):
            pass

    if empress["last_decree"]:
        embed.add_field(
            name="📜 Last Royal Proclamation",
            value=empress["last_decree"][:500],
            inline=False,
        )

    embed.set_footer(text="Appease Her Majesty or face the full weight of the Crown · V.I.C.T.O.R.I.A.")
    return embed


async def update_empress_embed(bot, guild_id: int, conn):
    config = await conn.fetchrow(
        "SELECT channel_events, empress_message_id FROM guild_config WHERE guild_id = $1", guild_id
    )
    if not config or not config["empress_message_id"]:
        return
    channel = bot.get_channel(config["channel_events"])
    if not channel:
        return
    try:
        message = await channel.fetch_message(config["empress_message_id"])
        embed = await build_empress_embed(guild_id, conn)
        await message.edit(embed=embed)
    except Exception as e:
        print(f"Empress embed update failed: {e}")
