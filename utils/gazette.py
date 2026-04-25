"""
The Imperial Gazette — V.I.C.T.O.R.I.A.
Victorian newspaper-style event reporting system.

Tier A: Full AI narrative (major events)
Tier B: Pre-written Victorian templates (mid-weight events)
Tier C: Silent / private only (bookkeeping events)
"""
import discord
import random
import os
from openai import AsyncOpenAI
from db.connection import get_pool

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ─────────────────────────────────────────
# SECTION COLOURS
# ─────────────────────────────────────────
SECTION_COLOURS = {
    "politics":  0x1a2744,   # deep navy
    "crown":     0x6b0000,   # deep crimson
    "war":       0x1a3a1a,   # dark forest green
    "election":  0x5a4500,   # deep gold
    "crisis":    0x2a0a0a,   # near black
    "society":   0x4B3010,   # parchment brown
    "societies": 0x2a1a4a,   # deep purple
}

# ─────────────────────────────────────────
# VICTORIAN MONTH NAMES
# ─────────────────────────────────────────
MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

DAYS_PER_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def ordinal(n: int) -> str:
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(
        n % 10 if n % 100 not in (11, 12, 13) else 0, "th"
    )
    return f"{n}{suffix}"


def advance_vic_date(year: int, month: int, day: int, days: int = 7):
    """Advance the Victorian calendar by a number of days."""
    day += days
    while day > DAYS_PER_MONTH[month - 1]:
        day -= DAYS_PER_MONTH[month - 1]
        month += 1
        if month > 12:
            month = 1
            year += 1
    return year, month, day


def format_vic_date(year: int, month: int, day: int) -> str:
    return f"{ordinal(day)} {MONTHS[month - 1]}, {year}"


# ─────────────────────────────────────────
# TIER B TEMPLATES
# ─────────────────────────────────────────
# Each template is a tuple of (headline, body) with {placeholders}

TEMPLATES = {
    # ── FREEFORM: DECLARATIONS ──
    "declaration": [
        (
            "{character} ISSUES PUBLIC DECLARATION",
            "{character} ({user_mention}) mounted the steps of the Imperial Hall this day and addressed the assembled public, "
            "declaring before all witnesses: *\"{content}\"* "
            "The galleries received the address with marked attention. "
            "It remains to be seen whether the words shall find favour with the public at large."
        ),
        (
            "PUBLIC ADDRESS BY {character_upper}",
            "In an address that drew considerable attention from the broadsheets, "
            "{character} ({user_mention}) issued the following statement to the citizens of the realm: "
            "*\"{content}\"* "
            "Political observers note the timing of the declaration with interest."
        ),
    ],

    # ── FREEFORM: ACCUSATIONS ──
    "accusation": [
        (
            "{character} LEVELS GRAVE CHARGE AGAINST {target_upper}",
            "{character} ({user_mention}) has this day levelled a most serious accusation against "
            "{target} ({target_mention}), alleging conduct most unbecoming of a public servant. "
            "The charge reads: *\"{content}\"* "
            "{target} has until the close of the current turn to answer the allegation before the House."
        ),
        (
            "SCANDAL ERUPTS AS {character_upper} ACCUSES {target_upper}",
            "The corridors of power were set abuzz today when {character} ({user_mention}) "
            "publicly accused {target} ({target_mention}) of the following: *\"{content}\"* "
            "Political observers await {target}'s response with considerable anticipation. "
            "If the charge is substantiated, the consequences for {target}'s standing may prove severe."
        ),
    ],

    # ── FREEFORM: ACCUSATION RESPONSE ──
    "accusation_response": [
        (
            "{target_upper} ANSWERS CHARGE BY {character_upper}",
            "{target} ({target_mention}) has issued a formal rebuttal to the accusations made by "
            "{character} ({user_mention}), declaring: *\"{content}\"* "
            "The matter shall be weighed at the close of the current turn."
        ),
    ],

    # ── FREEFORM: DEAL ACCEPTED ──
    "deal_accepted": [
        (
            "PRIVATE COMPACT FORMED BETWEEN {character_upper} AND {target_upper}",
            "It has come to this paper's attention that {character} ({user_mention}) "
            "and {target} ({target_mention}) have entered into a formal political compact. "
            "The precise terms of their arrangement remain undisclosed, "
            "though their association is now a matter of public record. "
            "Observers shall watch with interest to see whether the alliance endures."
        ),
    ],

    # ── FREEFORM: DEAL REJECTED ──
    "deal_rejected": [
        (
            "{target_upper} REBUFFS OVERTURE FROM {character_upper}",
            "{target} ({target_mention}) has this day declined a political proposition extended by "
            "{character} ({user_mention}). "
            "The nature of the rejected offer remains a matter of private knowledge, "
            "though its refusal has not gone unnoticed in the political salons of the capital."
        ),
    ],

    # ── FREEFORM: LEGISLATION TABLED ──
    "legislation_tabled": [
        (
            "{character_upper} TABLES NEW BILL BEFORE PARLIAMENT",
            "{character} ({user_mention}) has placed before the House a bill entitled "
            "**{content}**, inviting the consideration of all members. "
            "Parliament shall record its verdict before the close of the current session. "
            "Members are encouraged to make their positions known without delay."
        ),
    ],

    # ── FREEFORM: VOTE PLEDGE ──
    "vote_pledge": [
        (
            "{character_upper} PLEDGES VOTE ON PENDING LEGISLATION",
            "{character} ({user_mention}) has publicly committed their parliamentary vote "
            "in the matter of **{content}**. "
            "This declaration of intent has been entered into the record of the House."
        ),
    ],

    # ── FREEFORM: PROTEST ──
    "protest": [
        (
            "PUBLIC DISTURBANCE REPORTED NEAR THE IMPERIAL QUARTER",
            "A gathering of considerable size assembled today, led by {character} ({user_mention}), "
            "bearing placards and voicing grievances against the current ministry. "
            "The protesters declared: *\"{content}\"* "
            "The Home Office is monitoring the situation. "
            "Should order not be restored, the constabulary stands ready."
        ),
        (
            "{character_upper} LEADS PROTEST IN THE CAPITAL",
            "The streets outside Parliament were thronged today as {character} ({user_mention}) "
            "organised a public demonstration. The assembled crowd chanted and distributed pamphlets "
            "bearing the legend: *\"{content}\"* "
            "Political observers note that public unrest appears to be rising."
        ),
    ],

    # ── FREEFORM: PETITION ──
    "petition": [
        (
            "PETITION OF {count} SIGNATORIES SUBMITTED TO THE HOUSE",
            "A petition bearing {count} signatures, initiated by {character} ({user_mention}), "
            "has been formally submitted to Parliament. "
            "The petition demands: *\"{content}\"* "
            "The Speaker has acknowledged its receipt and it shall be considered at the next sitting."
        ),
    ],

    # ── TURN: LEGISLATION PASSED ──
    "legislation_passed": [
        (
            "PARLIAMENT PASSES {content_upper}",
            "By a vote of the House, the bill proposed by {character} ({user_mention}) "
            "has been carried and shall become law forthwith. "
            "National stability is expected to improve as order and governance are strengthened. "
            "The Minister's standing in the public eye is correspondingly enhanced."
        ),
    ],

    # ── TURN: LEGISLATION FAILED ──
    "legislation_failed": [
        (
            "PARLIAMENT REJECTS BILL PROPOSED BY {character_upper}",
            "The bill tabled by {character} ({user_mention}) has failed to secure the necessary "
            "votes of the House and is accordingly set aside. "
            "The Minister's opponents consider this a significant embarrassment. "
            "The Empress is reported to be displeased."
        ),
    ],

    # ── TURN: CORRUPTION EXPOSED ──
    "corruption_exposed": [
        (
            "SCANDAL: {target_upper} NAMED IN CORRUPTION INQUIRY",
            "This paper can exclusively report that {character} ({user_mention}) has furnished "
            "evidence of financial impropriety on the part of {target} ({target_mention}). "
            "The revelations have dealt a considerable blow to {target}'s public standing. "
            "The Ministry has declined to comment."
        ),
    ],

    # ── TURN: BRIBERY SUCCEEDED ──
    "bribery_succeeded": [
        (
            "REPORTS OF FINANCIAL INDUCEMENTS IN THE HOUSE",
            "Unattributed reports have reached this paper of financial arrangements made by "
            "{character} ({user_mention}) to secure the cooperation of certain unnamed officials. "
            "While no formal charge has been laid, the whispers grow louder in the lobbies of Parliament."
        ),
    ],

    # ── TURN: ECONOMIC DECREE ──
    "economic_decree": [
        (
            "CHANCELLOR ISSUES SWEEPING ECONOMIC DIRECTIVE",
            "{character} ({user_mention}), in their capacity as guardian of the Imperial treasury, "
            "has issued a decree directing the course of national commerce. "
            "Treasury receipts are expected to increase in the coming period. "
            "The mercantile classes have broadly welcomed the development."
        ),
    ],

    # ── TURN: WAR DECLARED ──
    "war_declared": [
        (
            "THE EMPIRE DECLARES WAR UPON {target_upper}",
            "In a solemn sitting of Parliament, {character} ({user_mention}) moved and carried "
            "the declaration of hostilities against {target}. "
            "The drums of empire have sounded. Our forces are mobilising. "
            "The Empress has expressed her desire for swift and decisive victory. "
            "God save the Crown — and God help our enemies."
        ),
    ],

    # ── TURN: CONFIDENCE VOTE CALLED ──
    "confidence_vote": [
        (
            "CONFIDENCE VOTE CALLED AGAINST {target_upper}",
            "{character} ({user_mention}) has moved a vote of no confidence in "
            "{target} ({target_mention}), holder of {seat_title}. "
            "The House shall record its verdict before the turn closes. "
            "Should the motion carry, {target} shall vacate their seat immediately."
        ),
    ],

    # ── SOCIETY: DISCOVERED ──
    "society_discovered": [
        (
            "MYSTERIOUS SOCIETY MAKES ITS PRESENCE KNOWN",
            "A member of the public, {character} ({user_mention}), has encountered agents of a "
            "clandestine organisation known as **{content}**. "
            "The society's purposes and membership remain shrouded in secrecy. "
            "This paper advises readers to remain alert to unusual political developments."
        ),
    ],

    # ── SOCIETY: JOINED ──
    "society_joined": [
        (
            "RUMOURS OF SECRET AFFILIATIONS",
            "Unconfirmed reports suggest that a prominent figure in the capital's political circles "
            "has lately been observed in the company of individuals known to associate with certain "
            "private fellowships. No names have been confirmed by reliable sources."
        ),
    ],

    # ── AP RESET ──
    "turn_ap_reset": [
        (
            "THE DISPATCH BOX OPENS — A NEW TURN BEGINS",
            "The political machinery of the Empire turns once more. "
            "Ministers have taken their places, opposition members have sharpened their quills, "
            "and the people watch with keen attention. "
            "Action Points have been restored to all participants. "
            "The fate of the nation awaits the decisions of the next dispatch."
        ),
    ],
}


def _fill_template(template: str, **kwargs) -> str:
    """Fill a template string with provided kwargs, adding _upper variants automatically."""
    for key, val in list(kwargs.items()):
        if isinstance(val, str):
            kwargs[f"{key}_upper"] = val.upper()
    try:
        return template.format(**kwargs)
    except KeyError:
        return template


def build_gazette_embed(
    *,
    nation_name: str,
    vic_date: str,
    turn_number: int,
    section: str,
    headline: str,
    body: str,
    footer_extra: str = "",
) -> discord.Embed:
    """Build a Victorian newspaper-style Discord embed."""
    colour = SECTION_COLOURS.get(section, 0x4B3010)

    section_labels = {
        "politics":  "HOME AFFAIRS",
        "crown":     "CROWN & IMPERIAL",
        "war":       "WAR & FOREIGN AFFAIRS",
        "election":  "ELECTION RETURNS",
        "crisis":    "URGENT DISPATCHES",
        "society":   "SOCIETY & PUBLIC ORDER",
        "societies": "SECRET INTELLIGENCE",
    }
    section_label = section_labels.get(section, "GENERAL INTELLIGENCE")

    embed = discord.Embed(
        title=f"📰 {headline}",
        description=(
            f"*{nation_name}  ·  Turn the {ordinal(turn_number)}  ·  {vic_date}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{body}"
        ),
        color=colour,
    )
    embed.set_author(
        name=f"THE IMPERIAL GAZETTE  ·  {section_label}",
        icon_url="https://cdn.discordapp.com/emojis/1234567890.png",  # placeholder
    )
    footer = "Printed at the Imperial Press, Westminster  ·  V.I.C.T.O.R.I.A."
    if footer_extra:
        footer += f"  ·  {footer_extra}"
    embed.set_footer(text=footer)
    return embed


async def post_tier_b(
    bot,
    guild_id: int,
    conn,
    *,
    section: str,
    template_key: str,
    **template_kwargs,
) -> discord.Message | None:
    """Post a Tier B templated gazette entry to the events channel."""
    config = await conn.fetchrow(
        "SELECT channel_events, nation_name, vic_year, vic_month, vic_day FROM guild_config WHERE guild_id = $1",
        guild_id,
    )
    if not config or not config["channel_events"]:
        return None

    channel = bot.get_channel(config["channel_events"])
    if not channel:
        return None

    nation = await conn.fetchrow("SELECT turn_number FROM nation_state WHERE guild_id = $1", guild_id)
    turn_number = nation["turn_number"] if nation else 1
    vic_date = format_vic_date(config["vic_year"], config["vic_month"], config["vic_day"])

    templates = TEMPLATES.get(template_key, [])
    if not templates:
        return None

    headline_tmpl, body_tmpl = random.choice(templates)
    headline = _fill_template(headline_tmpl, **template_kwargs)
    body = _fill_template(body_tmpl, **template_kwargs)

    embed = build_gazette_embed(
        nation_name=config["nation_name"],
        vic_date=vic_date,
        turn_number=turn_number,
        section=section,
        headline=headline,
        body=body,
    )

    try:
        msg = await channel.send(embed=embed)
        # Log to gazette_entries
        await conn.execute("""
            INSERT INTO gazette_entries (guild_id, tier, section, headline, body, turn_number, vic_date, message_id)
            VALUES ($1, 'B', $2, $3, $4, $5, $6, $7)
        """, guild_id, section, headline, body, turn_number, vic_date, msg.id)
        return msg
    except Exception as e:
        print(f"Gazette post error: {e}")
        return None


async def post_tier_a(
    bot,
    guild_id: int,
    conn,
    *,
    section: str,
    headline: str,
    ai_prompt: str,
    footer_extra: str = "",
    header_image: bool = False,
) -> discord.Message | None:
    """Post a Tier A AI-generated gazette entry."""
    config = await conn.fetchrow(
        "SELECT channel_events, nation_name, header_image_url, vic_year, vic_month, vic_day FROM guild_config WHERE guild_id = $1",
        guild_id,
    )
    if not config or not config["channel_events"]:
        return None

    channel = bot.get_channel(config["channel_events"])
    if not channel:
        return None

    nation = await conn.fetchrow("SELECT turn_number FROM nation_state WHERE guild_id = $1", guild_id)
    turn_number = nation["turn_number"] if nation else 1
    vic_date = format_vic_date(config["vic_year"], config["vic_month"], config["vic_day"])

    # Generate AI narrative
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            max_tokens=350,
            messages=[{
                "role": "system",
                "content": (
                    "You are the editor of The Imperial Gazette, a Victorian-era broadsheet published in 1878. "
                    "Write in formal, dramatic Victorian journalistic prose. Third person. "
                    "Use phrases like 'this paper understands', 'it is reported', 'sources close to the ministry'. "
                    "Be slightly sensationalist but always dignified. 3-4 sentences maximum."
                )
            }, {
                "role": "user",
                "content": ai_prompt,
            }]
        )
        body = response.choices[0].message.content
    except Exception:
        body = "*Our correspondent was unable to file a report in time for this edition. Details shall follow.*"

    embed = build_gazette_embed(
        nation_name=config["nation_name"],
        vic_date=vic_date,
        turn_number=turn_number,
        section=section,
        headline=headline,
        body=body,
        footer_extra=footer_extra,
    )

    try:
        header_url = config["header_image_url"]
    except (KeyError, TypeError):
        header_url = None

    if header_image and header_url:
        embed.set_image(url=header_url)

    try:
        msg = await channel.send(embed=embed)
        await conn.execute("""
            INSERT INTO gazette_entries (guild_id, tier, section, headline, body, turn_number, vic_date, message_id)
            VALUES ($1, 'A', $2, $3, $4, $5, $6, $7)
        """, guild_id, section, headline, body, turn_number, vic_date, msg.id)
        return msg
    except Exception as e:
        print(f"Gazette Tier A post error: {e}")
        return None


async def post_turn_gazette(bot, guild_id: int, conn, result: dict):
    """Post the full turn resolution as a Tier A gazette entry."""
    config = await conn.fetchrow("SELECT nation_name FROM guild_config WHERE guild_id = $1", guild_id)
    nation_name = config["nation_name"] if config else "The Empire"
    turn = result.get("turn_number", 1)

    # Build context for the AI
    action_summaries = "\n".join(
        f"- {e.get('action_label', 'Unknown')}: {e.get('success', 'unknown')} outcome"
        for e in result.get("events", [])[:8]
    )
    random_events = ", ".join(result.get("random_events", [])) or "none"

    prompt = (
        f"Write a Victorian newspaper summary of a political turn in {nation_name}. "
        f"Turn number: {turn}. "
        f"Actions taken this turn: {action_summaries or 'none recorded'}. "
        f"Random events: {random_events}. "
        f"National stability: {result.get('stability', 70)}. "
        f"Treasury: £{result.get('treasury', 1000):,}. "
        f"Write as the lead article for The Imperial Gazette. 3-4 sentences."
    )

    await post_tier_a(
        bot, guild_id, conn,
        section="politics",
        headline=f"THE IMPERIAL DISPATCH — TURN THE {ordinal(turn)}",
        ai_prompt=prompt,
        footer_extra=f"Turn {turn} resolved",
        header_image=True,
    )


async def post_election_gazette(bot, guild_id: int, conn, result: dict):
    """Post election results as a Tier A gazette entry."""
    config = await conn.fetchrow("SELECT nation_name FROM guild_config WHERE guild_id = $1", guild_id)
    nation_name = config["nation_name"] if config else "The Empire"

    results_text = "\n".join(
        f"Seat {r['seat_number']} ({r['title']}): {r.get('winner_name', 'Vacant')}"
        for r in result.get("results", [])
    )

    prompt = (
        f"Write a Victorian newspaper report on parliamentary election results in {nation_name}. "
        f"Seat results: {results_text}. "
        f"Write with the drama and gravity of a 19th century election night. 3-4 sentences."
    )

    await post_tier_a(
        bot, guild_id, conn,
        section="election",
        headline="ELECTION RETURNS — THE HOUSE RECONSTITUTED",
        ai_prompt=prompt,
        footer_extra="Election night edition",
        header_image=True,
    )


async def post_empress_intervention(bot, guild_id: int, conn, stage: int, nation_name: str):
    """Post an AI-generated Empress intervention gazette entry."""
    stage_context = {
        1: "She is growing restless and has begun sending pointed Royal Decrees to the Cabinet.",
        2: "She is impatient and has begun vetoing legislation she disapproves of.",
        3: "She is wrathful and has issued Royal Warrants against ministers with low loyalty.",
        4: "She is furious and has begun replacing Cabinet seats with her own loyalist appointees.",
        5: "Crown Rule has been invoked. The Empress governs alone. Parliament is prorogued.",
    }
    context = stage_context.get(stage, "Her displeasure grows.")

    prompt = (
        f"You are Empress Victoria I of {nation_name}, an imperious Victorian monarch. "
        f"Your displeasure with the Cabinet has reached a new stage. {context} "
        f"Write a dramatic Royal Proclamation of 2-3 sentences in formal Victorian prose, "
        f"making clear your displeasure and your intentions. "
        f"Sign it: *— Issued under the Seal of Empress Victoria I*"
    )

    await post_tier_a(
        bot, guild_id, conn,
        section="crown",
        headline="ROYAL PROCLAMATION FROM HER MAJESTY THE EMPRESS",
        ai_prompt=prompt,
        footer_extra=f"Displeasure Stage {stage}",
        header_image=True,
    )
