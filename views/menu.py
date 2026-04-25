"""
Main Command Menu — persistent live embed for V.I.C.T.O.R.I.A. v2
"""
import discord
from discord.ui import View, Button
from db.connection import get_pool
from utils.gazette import format_vic_date, ordinal


class MainMenuView(View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    async def _handle(self, interaction: discord.Interaction, coro):
        """Defer, run coro, and catch any errors so Discord always gets a response."""
        try:
            await coro
        except Exception as e:
            print(f"[MainMenuView] Error in button handler: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ *Something went wrong. Please try again.*", ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "❌ *Something went wrong. Please try again.*", ephemeral=True
                    )
            except Exception:
                pass

    @discord.ui.button(label="👤 My Character", style=discord.ButtonStyle.secondary,
                       custom_id="menu_my_character", row=0)
    async def my_character(self, interaction: discord.Interaction, button: Button):
        from views.character_panel import CharacterView
        pool = await get_pool()
        async with pool.acquire() as conn:
            await self._handle(interaction, CharacterView.send(interaction, conn))

    @discord.ui.button(label="⚖️ Formal Actions", style=discord.ButtonStyle.primary,
                       custom_id="menu_take_action", row=0)
    async def take_action(self, interaction: discord.Interaction, button: Button):
        from views.action_panel import ActionMenuView
        pool = await get_pool()
        async with pool.acquire() as conn:
            await self._handle(interaction, ActionMenuView.send(interaction, conn))

    @discord.ui.button(label="🗣️ Political Discourse", style=discord.ButtonStyle.primary,
                       custom_id="menu_freeform", row=0)
    async def freeform(self, interaction: discord.Interaction, button: Button):
        from views.freeform_panel import FreeformMenuView
        pool = await get_pool()
        async with pool.acquire() as conn:
            await self._handle(interaction, FreeformMenuView.send(interaction, conn))

    @discord.ui.button(label="🗺️ The Empire", style=discord.ButtonStyle.secondary,
                       custom_id="menu_empire", row=1)
    async def empire(self, interaction: discord.Interaction, button: Button):
        from views.empire_panel import EmpireView
        pool = await get_pool()
        async with pool.acquire() as conn:
            await self._handle(interaction, EmpireView.send(interaction, conn))

    @discord.ui.button(label="🏛️ The Cabinet", style=discord.ButtonStyle.secondary,
                       custom_id="menu_cabinet", row=1)
    async def cabinet(self, interaction: discord.Interaction, button: Button):
        from views.cabinet_panel import CabinetView
        pool = await get_pool()
        async with pool.acquire() as conn:
            await self._handle(interaction, CabinetView.send(interaction, conn))

    @discord.ui.button(label="📰 The Gazette", style=discord.ButtonStyle.secondary,
                       custom_id="menu_events", row=1)
    async def world_events(self, interaction: discord.Interaction, button: Button):
        from views.events_panel import EventsView
        pool = await get_pool()
        async with pool.acquire() as conn:
            await self._handle(interaction, EventsView.send(interaction, conn))

    @discord.ui.button(label="👑 Her Majesty", style=discord.ButtonStyle.secondary,
                       custom_id="menu_empress", row=2)
    async def empress_panel(self, interaction: discord.Interaction, button: Button):
        from utils.empress import build_empress_embed
        async def _send():
            pool = await get_pool()
            async with pool.acquire() as conn:
                embed = await build_empress_embed(interaction.guild_id, conn)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        await self._handle(interaction, _send())

    @discord.ui.button(label="📜 National Acts", style=discord.ButtonStyle.secondary,
                       custom_id="menu_acts", row=2)
    async def national_acts(self, interaction: discord.Interaction, button: Button):
        from utils.national_acts import NationalActsView
        pool = await get_pool()
        async with pool.acquire() as conn:
            await self._handle(interaction, NationalActsView.send(interaction, conn))

    @discord.ui.button(label="🎭 My Dossier", style=discord.ButtonStyle.secondary,
                       custom_id="menu_dossier", row=2)
    async def dossier(self, interaction: discord.Interaction, button: Button):
        pool = await get_pool()
        async with pool.acquire() as conn:
            await self._handle(interaction, _send_dossier(interaction, conn))

    @discord.ui.button(label="⚔️ War Room", style=discord.ButtonStyle.danger,
                       custom_id="menu_war", row=3)
    async def war_room(self, interaction: discord.Interaction, button: Button):
        from views.empire_panel import WarView
        pool = await get_pool()
        async with pool.acquire() as conn:
            await self._handle(interaction, WarView.send(interaction, conn))

    @discord.ui.button(label="🔮 Secret Societies", style=discord.ButtonStyle.danger,
                       custom_id="menu_societies", row=3)
    async def societies(self, interaction: discord.Interaction, button: Button):
        pool = await get_pool()
        async with pool.acquire() as conn:
            await self._handle(interaction, _send_societies(interaction, conn))


async def _send_dossier(interaction: discord.Interaction, conn):
    """Send the player's personal dossier."""
    player = await conn.fetchrow("""
        SELECT id, character_name, opinion_rating, loyalty, legacy_points, role_type
        FROM players WHERE guild_id = $1 AND user_id = $2
    """, interaction.guild_id, interaction.user.id)

    if not player:
        await interaction.response.send_message(
            "You have no dossier yet. Create your character first.", ephemeral=True
        )
        return

    entries = await conn.fetch("""
        SELECT event_type, description, vic_date FROM dossiers
        WHERE guild_id = $1 AND player_id = $2
        ORDER BY occurred_at DESC LIMIT 10
    """, interaction.guild_id, player["id"])

    titles = await conn.fetch("""
        SELECT title_name FROM player_titles
        WHERE guild_id = $1 AND player_id = $2
    """, interaction.guild_id, player["id"])

    alliances = await conn.fetch("""
        SELECT p.character_name, p.user_id FROM alliances a
        JOIN players p ON (p.id = CASE WHEN a.player_a = $2 THEN a.player_b ELSE a.player_a END)
        WHERE a.guild_id = $1 AND (a.player_a = $2 OR a.player_b = $2) AND a.status = 'active'
    """, interaction.guild_id, player["id"])

    title_str = " · ".join(f"*{t['title_name']}*" for t in titles) or "*No titles yet awarded.*"
    alliance_str = (
        ", ".join(f"{a['character_name']} (<@{a['user_id']}>)" for a in alliances)
        or "*None on record.*"
    )

    history_lines = []
    for e in entries:
        icon = {"action": "⚖️", "alliance": "🤝", "betrayal": "🗡️",
                "vote": "🗳️", "accusation": "⚖️", "title": "🏆"}.get(e["event_type"], "📌")
        history_lines.append(f"{icon} *{e['vic_date']}* — {e['description']}")
    history_str = "\n".join(history_lines) or "*No recorded history.*"

    embed = discord.Embed(
        title=f"🎭 Dossier — {player['character_name']}",
        description=(
            f"*Filed by the Office of the Lord Privy Seal. For authorised eyes only.*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"**Role:** {player['role_type'].title()}\n"
            f"**Opinion Rating:** {player['opinion_rating']}/100\n"
            f"**Crown Loyalty:** {player['loyalty']}/100\n"
            f"**Legacy Points:** {player['legacy_points']}\n\n"
            f"**Titles Held:**\n{title_str}\n\n"
            f"**Active Alliances:**\n{alliance_str}\n\n"
            f"**Recent Record:**\n{history_str}"
        ),
        color=0x4B3010,
    )
    embed.set_footer(text="V.I.C.T.O.R.I.A. · Confidential Intelligence Dossier")
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def _send_societies(interaction: discord.Interaction, conn):
    """Send the secret societies panel."""
    player = await conn.fetchrow("""
        SELECT id, character_name FROM players WHERE guild_id = $1 AND user_id = $2
    """, interaction.guild_id, interaction.user.id)

    if not player:
        await interaction.response.send_message(
            "You have no character yet.", ephemeral=True
        )
        return

    # Check if already a member
    membership = await conn.fetchrow("""
        SELECT society_key FROM society_members WHERE guild_id = $1 AND player_id = $2
    """, interaction.guild_id, player["id"])

    societies = await conn.fetch("""
        SELECT * FROM secret_societies WHERE guild_id = $1
    """, interaction.guild_id)

    if membership:
        society = next((s for s in societies if s["society_key"] == membership["society_key"]), None)
        embed = discord.Embed(
            title="🔮 Your Secret Fellowship",
            description=(
                f"*You are a sworn member of a clandestine society. "
                f"What follows is known only to initiates.*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"**{society['name'] if society else 'Unknown Society'}**\n\n"
                f"{society['description'] if society else ''}\n\n"
                f"**Secret Agenda:**\n*{society['agenda'] if society else ''}*\n\n"
                f"**Agenda Progress:** {society['agenda_progress'] if society else 0}/100\n"
                f"**Members:** {society['member_count'] if society else 0}"
            ),
            color=0x2a1a4a,
        )
        embed.set_footer(text="Speak of this to no one · V.I.C.T.O.R.I.A.")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        # Show discovery panel — player learns about societies by joining
        embed = discord.Embed(
            title="🔮 Clandestine Fellowships",
            description=(
                f"*The capital harbours organisations that do not appear in any official register. "
                f"Their membership is secret. Their agendas, more so.*\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"It is rumoured that at least **three** such fellowships operate within the Empire, "
                f"each with its own design upon the future of the nation.\n\n"
                f"Membership is not applied for — it is offered. "
                f"Keep your eyes and ears open. The right connection, "
                f"made at the right moment, may result in an invitation.\n\n"
                f"*Those who have been approached may join below.*"
            ),
            color=0x2a1a4a,
        )
        embed.set_footer(text="V.I.C.T.O.R.I.A. · What is hidden shapes what is seen")

        view = SocietyJoinView(interaction.guild_id, player["id"])
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class SocietyJoinView(View):
    def __init__(self, guild_id: int, player_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.player_id = player_id

    @discord.ui.button(label="I have received an invitation", style=discord.ButtonStyle.secondary)
    async def join(self, interaction: discord.Interaction, button: Button):
        # Pass the original message so the modal can edit it instead of sending a new message
        await interaction.response.send_modal(
            SocietyJoinModal(self.guild_id, self.player_id, interaction.message)
        )


class SocietyJoinModal(discord.ui.Modal, title="Society Invitation Code"):
    code = discord.ui.TextInput(
        label="Enter your invitation code",
        placeholder="The code spoken to you by your contact…",
        max_length=30,
        required=True,
    )

    def __init__(self, guild_id: int, player_id: int, original_message=None):
        super().__init__()
        self.guild_id = guild_id
        self.player_id = player_id
        self.original_message = original_message

    async def _edit_original(self, interaction: discord.Interaction, embed: discord.Embed):
        """Replace the original ephemeral message embed, removing the join button."""
        if self.original_message:
            try:
                await self.original_message.edit(embed=embed, view=None)
                await interaction.response.defer()
                return
            except Exception:
                pass
        # Fallback: send as new followup if edit fails
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)

    async def on_submit(self, interaction: discord.Interaction):
        """Map secret codes to societies."""
        CODES = {
            "reform":    "reformists",
            "empire":    "imperialists",
            "crown":     "loyalists",
        }
        entered = str(self.code).strip().lower()
        society_key = CODES.get(entered)

        if not society_key:
            fail_embed = discord.Embed(
                title="🔮 Code Unrecognised",
                description="*That code is not recognised. Perhaps your contact misspoke.*",
                color=0x2a1a4a,
            )
            fail_embed.set_footer(text="Speak of this to no one · V.I.C.T.O.R.I.A.")
            await self._edit_original(interaction, fail_embed)
            return

        # Defer — DB writes below can exceed the 3-second modal response window
        await interaction.response.defer(ephemeral=True)

        pool = await get_pool()
        async with pool.acquire() as conn:
            society = await conn.fetchrow("""
                SELECT * FROM secret_societies WHERE guild_id = $1 AND society_key = $2
            """, self.guild_id, society_key)

            if not society:
                fail_embed = discord.Embed(
                    title="🔮 Fellowship Not Found",
                    description="*That fellowship does not appear to operate in this jurisdiction.*",
                    color=0x2a1a4a,
                )
                fail_embed.set_footer(text="Speak of this to no one · V.I.C.T.O.R.I.A.")
                if self.original_message:
                    try:
                        await self.original_message.edit(embed=fail_embed, view=None)
                        return
                    except Exception:
                        pass
                await interaction.followup.send(embed=fail_embed, ephemeral=True)
                return

            await conn.execute("""
                INSERT INTO society_members (guild_id, player_id, society_key)
                VALUES ($1, $2, $3)
                ON CONFLICT (guild_id, player_id) DO NOTHING
            """, self.guild_id, self.player_id, society_key)

            await conn.execute("""
                UPDATE secret_societies SET member_count = member_count + 1
                WHERE guild_id = $1 AND society_key = $2
            """, self.guild_id, society_key)

            # Update player role type to reflect society membership
            await conn.execute("""
                UPDATE players SET role_type = CASE
                    WHEN role_type = 'people' THEN 'people'
                    ELSE role_type
                END WHERE id = $1
            """, self.player_id)

        success_embed = discord.Embed(
            title=f"🔮 Welcome to {society['name']}",
            description=(
                f"*The door closes behind you. The candles are lit. Your oath is taken.*\n\n"
                f"**{society['name']}**\n\n"
                f"{society['description']}\n\n"
                f"**Your Secret Agenda:**\n*{society['agenda']}*\n\n"
                f"*Work in shadow. Trust no one outside the fellowship. "
                f"The Empire shall be shaped by those who understand its true nature.*"
            ),
            color=0x2a1a4a,
        )
        success_embed.set_footer(text="Speak of this to no one · V.I.C.T.O.R.I.A.")
        if self.original_message:
            try:
                await self.original_message.edit(embed=success_embed, view=None)
                return
            except Exception:
                pass
        await interaction.followup.send(embed=success_embed, ephemeral=True)


# ─────────────────────────────────────────
# MENU EMBED BUILDER
# ─────────────────────────────────────────

async def build_menu_embed(guild_id: int, conn) -> discord.Embed:
    config  = await conn.fetchrow("SELECT * FROM guild_config WHERE guild_id = $1", guild_id)
    nation  = await conn.fetchrow("SELECT * FROM nation_state WHERE guild_id = $1", guild_id)
    empress = await conn.fetchrow(
        "SELECT royal_favour, displeasure, stage, is_crown_rule, current_ambition FROM empress WHERE guild_id = $1",
        guild_id
    )

    nation_name = config["nation_name"] if config else "The Empire"
    turn        = nation["turn_number"]   if nation  else 1
    stability   = nation["stability"]     if nation  else 70
    treasury    = nation["treasury"]      if nation  else 1000
    unrest      = nation["public_unrest"] if nation  else 20
    military    = nation["military"]      if nation  else 5
    hex_count   = nation["hex_count"]     if nation  else 4

    next_turn   = config["next_turn_at"] if config else None
    turn_str    = f"<t:{int(next_turn.timestamp())}:R>" if next_turn else "Pending"

    vic_date = ""
    if config:
        try:
            vic_date = format_vic_date(config["vic_year"], config["vic_month"], config["vic_day"])
        except (KeyError, TypeError):
            vic_date = "1st January, 1878"

    def bar(val, length=12):
        filled = max(0, min(length, int((val / 100) * length)))
        return "▓" * filled + "░" * (length - filled)

    def mil_bar(val, length=10):
        filled = max(0, min(length, int((val / 10) * length)))
        return "▓" * filled + "░" * (length - filled)

    stab_mark   = "◈" if stability >= 60 else ("◇" if stability >= 35 else "⚠")
    unrest_mark = "◈" if unrest <= 30   else ("◇" if unrest <= 60   else "⚠")

    crown_warning = ""
    empress_block = ""
    if empress:
        favour = empress["royal_favour"]
        displeasure = empress["displeasure"]
        stage = empress["stage"]
        fbar = bar(favour)
        dbar = bar(displeasure)

        if empress["is_crown_rule"]:
            crown_warning = (
                "\n╔══════════════════════════════╗\n"
                "║  ⚠  CROWN RULE IN EFFECT  ⚠  ║\n"
                "║  Parliament stands prorogued. ║\n"
                "╚══════════════════════════════╝\n"
            )

        from utils.empress import STAGES
        stage_data = STAGES.get(stage, STAGES[0])
        stage_label = stage_data["label"]

        empress_block = (
            f"\n**Her Majesty the Empress** — Stage {stage}: *{stage_label}*\n"
            f"  Royal Favour   {fbar}  {favour}/100\n"
            f"  Displeasure    {dbar}  {displeasure}/100\n"
            f"*\"{empress['current_ambition']}\"*"
        )

    description = (
        f"```\n"
        f"  THE IMPERIAL GAZETTE · OFFICIAL DISPATCH\n"
        f"  ══════════════════════════════════════════\n"
        f"  {nation_name}\n"
        f"  Turn the {ordinal(turn)}  ·  {vic_date}\n"
        f"```"
        f"{crown_warning}"
        f"\n"
        f"**THE STATE OF THE NATION**\n"
        f"\n"
        f"  {stab_mark}  Stability       {bar(stability)}  {stability:>3}/100\n"
        f"  {unrest_mark}  Public Unrest   {bar(unrest)}  {unrest:>3}/100\n"
        f"  ◈  Treasury        £{treasury:>10,}\n"
        f"  ◈  Military        {mil_bar(military)}  {military}/10\n"
        f"  ◈  Territories     {hex_count} hexes held\n"
        f"\n"
        f"**Next Dispatch:** {turn_str}\n"
        f"{empress_block}\n"
        f"\n"
        f"*The dispatch box awaits, Minister. Choose your course.*"
    )

    embed = discord.Embed(description=description, color=0x8B0000)

    try:
        header_url = config["header_image_url"] if config else None
    except (KeyError, TypeError):
        header_url = None
    if header_url:
        embed.set_image(url=header_url)

    embed.set_footer(text="V.I.C.T.O.R.I.A.  ·  For Crown and Empire  ·  Omnia pro Imperio")
    return embed


def _ordinal(n: int) -> str:
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(
        n % 10 if n % 100 not in (11, 12, 13) else 0, "th"
    )
    return f"{n}{suffix}"


async def update_menu_embed(bot, guild_id: int, conn):
    config = await conn.fetchrow(
        "SELECT channel_menu, menu_message_id FROM guild_config WHERE guild_id = $1", guild_id
    )
    if not config or not config["channel_menu"] or not config["menu_message_id"]:
        return
    channel = bot.get_channel(config["channel_menu"])
    if not channel:
        return
    try:
        message = await channel.fetch_message(config["menu_message_id"])
        embed = await build_menu_embed(guild_id, conn)
        await message.edit(embed=embed, view=MainMenuView(guild_id))
    except Exception as e:
        print(f"Menu embed update failed: {e}")
