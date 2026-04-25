"""
National Acts & Random Events system for V.I.C.T.O.R.I.A.
Acts: formal proposals any player can table, cabinet passes/blocks.
Events: procedurally triggered each turn with varying severity.

FIXES:
- NationalActsView.send() now uses followup if response already consumed
- ActVotingView uses persistent custom_ids and proper DB inserts
- Voting embed live-updates on every vote
- Voter list (Aye/Noe) shown with character name + Discord ping
- Confirmation message sent after voting
- All Empress/Crown references use Her Majesty / The Empress
"""
import random
import discord
from discord.ui import View, Button, Select
from db.connection import get_pool

# ─────────────────────────────────────────
# ACT DEFINITIONS
# ─────────────────────────────────────────

NATIONAL_ACTS = {
    "war_declaration": {
        "title": "Declaration of War",
        "description": "Formally declare war on a neighbouring NPC nation. Commits the Empire to a military campaign.",
        "ap_cost": 2,
        "requires_cabinet": True,
        "vote_turns": 1,
        "effects": {"war": True, "unrest": "+15", "royal_favour_ambition": "military"},
    },
    "trade_treaty": {
        "title": "International Trade Treaty",
        "description": "Sign a trade agreement with a friendly or neutral NPC nation. Boosts Treasury income.",
        "ap_cost": 1,
        "requires_cabinet": False,
        "vote_turns": 2,
        "effects": {"treasury": "+150 to +300", "royal_favour_ambition": "economy"},
    },
    "industrial_investment": {
        "title": "Act of Industrial Investment",
        "description": "Fund a new industrial sector. Long-term economy boost at upfront cost to the Treasury.",
        "ap_cost": 2,
        "requires_cabinet": True,
        "vote_turns": 2,
        "effects": {"treasury": "-200", "economy_modifier": "+2 turns", "royal_favour_ambition": "industry"},
    },
    "colonial_expansion": {
        "title": "Colonial Expansion Act",
        "description": "Authorise the annexation of a new colonial territory in the name of the Crown.",
        "ap_cost": 3,
        "requires_cabinet": True,
        "vote_turns": 1,
        "effects": {"hex_count": "+1 to +2", "royal_favour_ambition": "expansion"},
    },
    "tax_reform": {
        "title": "Tax Reform Bill",
        "description": "Restructure the national taxation system. Fills the Treasury but risks public unrest.",
        "ap_cost": 2,
        "requires_cabinet": True,
        "vote_turns": 2,
        "effects": {"treasury": "+250", "unrest": "+10"},
    },
    "public_works": {
        "title": "Public Works Programme",
        "description": "Fund infrastructure and civic improvements across the nation. Reduces unrest and boosts stability.",
        "ap_cost": 2,
        "requires_cabinet": False,
        "vote_turns": 2,
        "effects": {"stability": "+10", "unrest": "-15", "treasury": "-150"},
    },
    "press_censorship": {
        "title": "Press Censorship Act",
        "description": "Silence dissenting newspapers. Prevents opposition propaganda actions this cycle.",
        "ap_cost": 2,
        "requires_cabinet": True,
        "vote_turns": 1,
        "effects": {"blocks_propaganda": True, "legitimacy_penalty": "-5 to all cabinet"},
    },
    "military_conscription": {
        "title": "Military Conscription Act",
        "description": "Enact conscription. Dramatically raises military strength at the cost of public unrest.",
        "ap_cost": 3,
        "requires_cabinet": True,
        "vote_turns": 1,
        "effects": {"military": "+3", "unrest": "+20", "royal_favour_ambition": "military"},
    },
    "peace_treaty": {
        "title": "Peace Treaty",
        "description": "Negotiate an end to an active war. Ends the campaign and improves NPC disposition.",
        "ap_cost": 2,
        "requires_cabinet": False,
        "vote_turns": 1,
        "effects": {"war": False, "unrest": "-10", "royal_favour_ambition": "diplomacy"},
    },
    "royal_charter": {
        "title": "Royal Charter of Commerce",
        "description": "Grant a royal charter to a trading company. Boosts the economy and pleases the Empress.",
        "ap_cost": 2,
        "requires_cabinet": True,
        "vote_turns": 2,
        "effects": {"treasury": "+200", "royal_favour": "+10"},
    },
}

# ─────────────────────────────────────────
# RANDOM EVENT DEFINITIONS
# ─────────────────────────────────────────

RANDOM_EVENTS = {
    "minor_unrest": {
        "title": "Civil Disturbance",
        "description": "Protests have broken out in the capital. The constabulary is stretched thin.",
        "severity": "minor", "probability": 0.25,
        "effects": {"unrest": "+8"},
        "response_actions": ["suppress_unrest", "pass_legislation"],
    },
    "bumper_harvest": {
        "title": "Bumper Harvest",
        "description": "An exceptional harvest season has filled the nation's granaries and lifted spirits.",
        "severity": "minor", "probability": 0.20,
        "effects": {"stability": "+5", "unrest": "-5"},
        "response_actions": [],
    },
    "trade_boom": {
        "title": "Trade Boom",
        "description": "Merchant vessels report record profits. The markets are buoyant.",
        "severity": "minor", "probability": 0.20,
        "effects": {"treasury": "+100"},
        "response_actions": [],
    },
    "press_scandal": {
        "title": "Parliamentary Scandal",
        "description": "The press has uncovered impropriety in the corridors of power.",
        "severity": "minor", "probability": 0.18,
        "effects": {"random_cabinet_opinion": "-12"},
        "response_actions": ["propaganda_campaign", "bribe_official"],
    },
    "economic_recession": {
        "title": "Economic Recession",
        "description": "Trade has slowed and factories stand idle. The economy contracts sharply.",
        "severity": "moderate", "probability": 0.10,
        "effects": {"treasury": "-200", "unrest": "+15"},
        "response_actions": ["economic_decree", "pass_legislation"],
    },
    "border_tension": {
        "title": "Border Tensions",
        "description": "A neighbouring power has massed troops on our frontier. War may be imminent.",
        "severity": "moderate", "probability": 0.10,
        "effects": {"random_npc_disposition": "hostile", "unrest": "+10"},
        "response_actions": ["diplomatic_overture", "fund_campaign"],
    },
    "industrial_accident": {
        "title": "Industrial Catastrophe",
        "description": "A catastrophic explosion at a factory has shocked the nation.",
        "severity": "moderate", "probability": 0.08,
        "effects": {"stability": "-10", "unrest": "+12"},
        "response_actions": ["suppress_unrest", "public_works"],
    },
    "royal_displeasure": {
        "title": "Royal Displeasure",
        "description": "Her Majesty has expressed grave dissatisfaction with the Cabinet's performance.",
        "severity": "moderate", "probability": 0.10,
        "effects": {"royal_favour": "-15"},
        "response_actions": ["public_speech", "pass_legislation"],
    },
    "plague_outbreak": {
        "title": "Plague Outbreak",
        "description": "A virulent sickness sweeps through the populous districts. Panic grips the streets.",
        "severity": "major", "probability": 0.04,
        "effects": {"stability": "-20", "unrest": "+25", "treasury": "-300"},
        "response_actions": ["suppress_unrest", "pass_legislation"],
    },
    "foreign_invasion": {
        "title": "Foreign Incursion",
        "description": "Enemy forces have crossed our border. The nation is under attack.",
        "severity": "major", "probability": 0.04,
        "effects": {"military": "-2", "unrest": "+20", "stability": "-15"},
        "response_actions": ["declare_war", "fund_campaign"],
    },
    "assassination_attempt": {
        "title": "Assassination Attempt",
        "description": "A dastardly plot against a senior minister has been narrowly foiled.",
        "severity": "major", "probability": 0.03,
        "effects": {"random_cabinet_opinion": "-20", "unrest": "+15"},
        "response_actions": ["gather_intelligence", "suppress_unrest"],
    },
    "revolution_threat": {
        "title": "Revolutionary Fervour",
        "description": "Radicals and agitators threaten to overthrow the established order itself.",
        "severity": "crisis", "probability": 0.02,
        "effects": {"stability": "-30", "unrest": "+35", "royal_favour": "-20"},
        "response_actions": ["suppress_unrest", "pass_legislation", "propaganda_campaign"],
    },
    "royal_ambition_crisis": {
        "title": "Imperial Decree",
        "description": "Her Majesty has issued an urgent Imperial Decree. The Cabinet must act immediately.",
        "severity": "crisis", "probability": 0.03,
        "effects": {"royal_favour": "-10"},
        "response_actions": [],
    },
}


# ─────────────────────────────────────────
# EVENT GENERATION
# ─────────────────────────────────────────

def roll_events(nation_stability: int, nation_unrest: int) -> list:
    triggered = []
    instability_mod = (100 - nation_stability) / 100.0
    unrest_mod      = nation_unrest / 100.0
    for key, event in RANDOM_EVENTS.items():
        base = event["probability"]
        if event["effects"].get("stability") or event["effects"].get("unrest"):
            adj = base * (1 + instability_mod + unrest_mod)
        else:
            adj = base
        if random.random() < min(adj, 0.6):
            triggered.append(key)
    if len(triggered) > 3:
        order = {"crisis": 0, "major": 1, "moderate": 2, "minor": 3}
        triggered.sort(key=lambda k: order.get(RANDOM_EVENTS[k]["severity"], 3))
        triggered = triggered[:3]
    return triggered


async def apply_event_effects(guild_id: int, event_key: str, conn):
    event = RANDOM_EVENTS.get(event_key)
    if not event:
        return
    effects = event["effects"]
    updates = {}
    if "unrest" in effects:
        val = int(str(effects["unrest"]).replace("+", ""))
        updates["public_unrest"] = f"LEAST(100, public_unrest + {val})"
    if "stability" in effects:
        val = int(str(effects["stability"]).replace("+", ""))
        updates["stability"] = f"LEAST(100, GREATEST(0, stability + {val}))"
    if "treasury" in effects:
        val = int(str(effects["treasury"]).replace("+", ""))
        updates["treasury"] = f"GREATEST(0, treasury + {val})"
    if "military" in effects:
        val = int(str(effects["military"]).replace("+", ""))
        updates["military"] = f"LEAST(10, GREATEST(1, military + {val}))"
    if updates:
        set_clause = ", ".join(f"{col} = {expr}" for col, expr in updates.items())
        await conn.execute(f"UPDATE nation_state SET {set_clause} WHERE guild_id = $1", guild_id)
    if "royal_favour" in effects:
        val = int(str(effects["royal_favour"]).replace("+", ""))
        await conn.execute("""
            UPDATE empress SET royal_favour = LEAST(100, GREATEST(0, royal_favour + $1))
            WHERE guild_id = $2
        """, val, guild_id)
    if "random_cabinet_opinion" in effects:
        val = -abs(int(str(effects["random_cabinet_opinion"]).replace("+","").replace("-","")))
        player = await conn.fetchrow("""
            SELECT p.id FROM players p
            JOIN cabinet_assignments ca ON ca.player_id = p.id AND ca.guild_id = p.guild_id
            WHERE p.guild_id = $1 ORDER BY RANDOM() LIMIT 1
        """, guild_id)
        if player:
            await conn.execute("""
                UPDATE players SET opinion_rating = GREATEST(0, opinion_rating + $1) WHERE id = $2
            """, val, player["id"])


async def save_events(guild_id: int, turn_number: int, event_keys: list, conn):
    for key in event_keys:
        event = RANDOM_EVENTS.get(key, {})
        await conn.execute("""
            INSERT INTO national_events (guild_id, turn_number, event_key, event_title, event_description, severity)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, guild_id, turn_number, key,
            event.get("title", key), event.get("description", ""), event.get("severity", "minor"))


# ─────────────────────────────────────────
# VOTING EMBED BUILDER
# ─────────────────────────────────────────

async def _build_voting_embed(act_record, act_def: dict, guild_id: int, conn, config) -> discord.Embed:
    votes_for     = act_record["votes_for"] or 0
    votes_against = act_record["votes_against"] or 0
    status        = act_record["status"]

    # Fetch individual voter details
    voter_rows = await conn.fetch("""
        SELECT nav.user_id, nav.is_aye, p.character_name
        FROM national_act_votes nav
        LEFT JOIN players p ON p.user_id = nav.user_id AND p.guild_id = nav.guild_id
        WHERE nav.act_id = $1
        ORDER BY nav.voted_at ASC
    """, act_record["id"])

    aye_lines = [f"  {r['character_name'] or 'Unknown'} (<@{r['user_id']}>)" for r in voter_rows if r["is_aye"]]
    nay_lines = [f"  {r['character_name'] or 'Unknown'} (<@{r['user_id']}>)" for r in voter_rows if not r["is_aye"]]
    aye_block = "\n".join(aye_lines) if aye_lines else "  *None yet*"
    nay_block = "\n".join(nay_lines) if nay_lines else "  *None yet*"

    bar_len   = 12
    total     = max(votes_for + votes_against, 1)
    aye_bar   = int((votes_for / total) * bar_len)
    nay_bar   = bar_len - aye_bar

    status_labels = {
        "proposed": "Open for Division",
        "passed":   "PASSED — Royal Assent Granted",
        "rejected": "REJECTED — Motion Defeated",
        "expired":  "LAPSED — Time Expired",
    }
    colours = {"proposed": 0x4169E1, "passed": 0x228B22, "rejected": 0x8B0000, "expired": 0x888888}

    eligibility = "Cabinet majority" if act_def.get("requires_cabinet") else "Player majority"

    desc = (
        f"*Tabled before the {'Cabinet' if act_def.get('requires_cabinet') else 'Full House'} for their consideration.*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{act_def.get('description', '')}\n\n"
        f"**Eligibility:** {eligibility}  ·  **Voting closes:** {act_def.get('vote_turns', 1)} turn(s)\n\n"
        f"**Division Tally**\n"
        f"Ayes `{'█' * aye_bar}{'░' * nay_bar}` Noes  —  **{votes_for} Aye · {votes_against} Noe**\n\n"
        f"**Ayes:**\n{aye_block}\n\n"
        f"**Noes:**\n{nay_block}\n\n"
        f"*Status: {status_labels.get(status, status)}*"
    )

    embed = discord.Embed(
        title=f"📜 {act_def.get('title', 'National Act')}",
        description=desc,
        color=colours.get(status, 0x4169E1),
    )
    try:
        header_url = config["header_image_url"] if config else None
        if header_url:
            embed.set_image(url=header_url)
    except (KeyError, TypeError):
        pass
    embed.set_footer(text="Cast your vote below — your position is final and a matter of record · V.I.C.T.O.R.I.A.")
    return embed


# ─────────────────────────────────────────
# NATIONAL ACTS VIEW
# ─────────────────────────────────────────

class NationalActsView(View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id

        options = [
            discord.SelectOption(
                label=act["title"][:100],
                value=key,
                description=f"AP: {act['ap_cost']} · {'Cabinet vote' if act['requires_cabinet'] else 'Open vote'}"[:100],
            )
            for key, act in NATIONAL_ACTS.items()
        ]
        select = Select(placeholder="Choose an Act to propose before the House...", options=options[:25], row=0)
        select.callback = self.act_selected
        self.add_item(select)

    async def act_selected(self, interaction: discord.Interaction):
        act_key = interaction.data["values"][0]
        act = NATIONAL_ACTS.get(act_key)
        if not act:
            await interaction.response.send_message("Unknown act.", ephemeral=True)
            return

        pool = await get_pool()
        async with pool.acquire() as conn:
            player = await conn.fetchrow("""
                SELECT p.id, p.ap_remaining, ca.seat_number
                FROM players p
                LEFT JOIN cabinet_assignments ca ON ca.player_id = p.id AND ca.guild_id = p.guild_id
                WHERE p.guild_id = $1 AND p.user_id = $2
            """, self.guild_id, interaction.user.id)

            if not player:
                await interaction.response.send_message(
                    "You must register a character before tabling an Act.", ephemeral=True
                )
                return

            if player["ap_remaining"] < act["ap_cost"]:
                await interaction.response.send_message(
                    f"Insufficient Action Points. This Act requires **{act['ap_cost']} AP**.", ephemeral=True
                )
                return

            empress = await conn.fetchrow("SELECT is_crown_rule FROM empress WHERE guild_id = $1", self.guild_id)
            if empress and empress["is_crown_rule"] and act["requires_cabinet"]:
                await interaction.response.send_message(
                    "Her Majesty has invoked Crown Rule — Cabinet Acts are suspended until the next election.",
                    ephemeral=True
                )
                return

            nation = await conn.fetchrow("SELECT turn_number FROM nation_state WHERE guild_id = $1", self.guild_id)
            turn   = nation["turn_number"] if nation else 1

            act_id = await conn.fetchval("""
                INSERT INTO national_acts (guild_id, proposed_by, act_key, act_title, act_description, proposed_turn, expires_turn)
                VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id
            """, self.guild_id, player["id"], act_key, act["title"], act["description"],
                turn, turn + act["vote_turns"])

            await conn.execute(
                "UPDATE players SET ap_remaining = ap_remaining - $1 WHERE id = $2",
                act["ap_cost"], player["id"]
            )

            config = await conn.fetchrow(
                "SELECT channel_events, header_image_url FROM guild_config WHERE guild_id = $1", self.guild_id
            )

        # Respond first, then post to events channel
        await interaction.response.send_message(
            f"*The Clerk rises. A motion has been tabled: **{act['title']}**. "
            f"The House shall divide at the appointed time.*",
            ephemeral=True
        )

        # Post voting embed to events channel
        await _post_act_to_channel(interaction, self.guild_id, act_key, act, act_id, config)

    @discord.ui.button(label="← Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: Button):
        from views.menu import build_menu_embed, MainMenuView
        pool = await get_pool()
        async with pool.acquire() as conn:
            embed = await build_menu_embed(self.guild_id, conn)
            await interaction.response.edit_message(embed=embed, view=MainMenuView(self.guild_id))

    @staticmethod
    async def send(interaction: discord.Interaction, conn):
        guild_id  = interaction.guild_id
        config    = await conn.fetchrow("SELECT header_image_url FROM guild_config WHERE guild_id = $1", guild_id)
        empress   = await conn.fetchrow("SELECT is_crown_rule FROM empress WHERE guild_id = $1", guild_id)
        crown_rule = empress and empress["is_crown_rule"]

        embed = discord.Embed(
            title="📜 The Order Paper — National Acts",
            description=(
                ("⚠️ **Her Majesty has invoked Crown Rule.** Cabinet Acts are suspended until the next election.\n\n" if crown_rule else "") +
                "*The following Acts may be tabled before the House for debate and division. "
                "Cabinet Acts require a majority of sitting ministers. "
                "Open Acts require a majority of all registered players.*\n\n"
                "Select an Act from the order paper below to table it."
            ),
            color=0x8B4513,
        )
        try:
            if config and config["header_image_url"]:
                embed.set_image(url=config["header_image_url"])
        except (KeyError, TypeError):
            pass

        try:
            await interaction.response.send_message(embed=embed, view=NationalActsView(guild_id), ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(embed=embed, view=NationalActsView(guild_id), ephemeral=True)


async def _post_act_to_channel(interaction: discord.Interaction, guild_id: int, act_key: str, act: dict, act_id: int, config):
    """Post or update the voting embed in the events channel."""
    if not config or not config.get("channel_events"):
        return

    channel = interaction.guild.get_channel(config["channel_events"])
    if not channel:
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        act_record = await conn.fetchrow("SELECT * FROM national_acts WHERE id = $1", act_id)
        if not act_record:
            return
        embed = await _build_voting_embed(act_record, act, guild_id, conn, config)
        view  = ActVotingView(guild_id, act_id, act["requires_cabinet"])
        msg   = await channel.send(embed=embed, view=view)
        await conn.execute(
            "UPDATE national_acts SET channel_message_id = $1 WHERE id = $2",
            msg.id, act_id
        )


# ─────────────────────────────────────────
# VOTING VIEW
# ─────────────────────────────────────────

class _ActVoteButton(discord.ui.Button):
    def __init__(self, *, label: str, style: discord.ButtonStyle, custom_id: str, is_aye: bool):
        super().__init__(label=label, style=style, custom_id=custom_id)
        self.is_aye = is_aye

    async def callback(self, interaction: discord.Interaction):
        await self.view._cast_vote(interaction, self.is_aye)


class ActVotingView(View):
    def __init__(self, guild_id: int, act_id: int, requires_cabinet: bool):
        super().__init__(timeout=None)
        self.guild_id        = guild_id
        self.act_id          = act_id
        self.requires_cabinet = requires_cabinet

        self.add_item(_ActVoteButton(
            label="Aye",
            style=discord.ButtonStyle.success,
            custom_id=f"act_vote_aye_{act_id}",
            is_aye=True,
        ))
        self.add_item(_ActVoteButton(
            label="Noe",
            style=discord.ButtonStyle.danger,
            custom_id=f"act_vote_nay_{act_id}",
            is_aye=False,
        ))

    async def _cast_vote(self, interaction: discord.Interaction, is_aye: bool):
        pool = await get_pool()
        async with pool.acquire() as conn:
            act = await conn.fetchrow("SELECT * FROM national_acts WHERE id = $1", self.act_id)
            if not act or act["status"] != "proposed":
                await interaction.response.send_message(
                    "*The division bell has ceased — this vote is no longer open.*",
                    ephemeral=True
                )
                return

            # Check already voted
            already = await conn.fetchval(
                "SELECT COUNT(*) FROM national_act_votes WHERE act_id = $1 AND user_id = $2",
                self.act_id, interaction.user.id
            )
            if already:
                await interaction.response.send_message(
                    "*The Clerk has already recorded your vote. Parliamentary procedure does not permit changes.*",
                    ephemeral=True
                )
                return

            # Cabinet check
            if self.requires_cabinet:
                in_cabinet = await conn.fetchval("""
                    SELECT EXISTS(
                        SELECT 1 FROM players p
                        JOIN cabinet_assignments ca ON ca.player_id = p.id
                        WHERE p.guild_id = $1 AND p.user_id = $2
                    )
                """, self.guild_id, interaction.user.id)
                if not in_cabinet:
                    await interaction.response.send_message(
                        "*Only members of Her Majesty's Cabinet may vote on this Act.*",
                        ephemeral=True
                    )
                    return

            # Check player is registered
            player = await conn.fetchrow(
                "SELECT character_name FROM players WHERE guild_id = $1 AND user_id = $2",
                self.guild_id, interaction.user.id
            )
            if not player:
                await interaction.response.send_message(
                    "*You must be a registered player to participate in the division.*",
                    ephemeral=True
                )
                return

            char_name = player["character_name"]

            # Record vote
            await conn.execute("""
                INSERT INTO national_act_votes (act_id, guild_id, user_id, is_aye)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (act_id, user_id) DO NOTHING
            """, self.act_id, self.guild_id, interaction.user.id, is_aye)

            col = "votes_for" if is_aye else "votes_against"
            await conn.execute(f"""
                UPDATE national_acts SET {col} = {col} + 1 WHERE id = $1
            """, self.act_id)

            # Fetch updated record and rebuild embed
            act_updated = await conn.fetchrow("SELECT * FROM national_acts WHERE id = $1", self.act_id)
            act_def     = NATIONAL_ACTS.get(act_updated["act_key"], {})
            config      = await conn.fetchrow(
                "SELECT header_image_url FROM guild_config WHERE guild_id = $1", self.guild_id
            )
            new_embed = await _build_voting_embed(act_updated, act_def, self.guild_id, conn, config)

        # Live-update the embed
        try:
            msg_id = act_updated.get("channel_message_id")
            if msg_id:
                orig = await interaction.channel.fetch_message(msg_id)
                await orig.edit(embed=new_embed, view=self)
        except Exception as e:
            print(f"Vote embed live-update failed: {e}")

        vote_label = "Aye" if is_aye else "Noe"
        await interaction.response.send_message(
            f"*The Clerk of the House rises and records: **{char_name}** — **{vote_label}**.*\n"
            f"Your position is now entered into the parliamentary record and cannot be altered.",
            ephemeral=True
        )
