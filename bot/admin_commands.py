"""
Admin slash commands for V.I.C.T.O.R.I.A.
Only slash commands in the bot — everything else is button-driven.
"""
import os
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta, timezone
from db.connection import get_pool
from db.seed import seed_guild
from utils.mapgen import save_map_to_db
from views.menu import build_menu_embed, MainMenuView
from views.cabinet_panel import build_cabinet_embed
from views.empire_panel import build_leaderboard_embed

BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", "0"))


def is_owner(user_id: int) -> bool:
    return BOT_OWNER_ID != 0 and user_id == BOT_OWNER_ID


async def has_admin_role(interaction: discord.Interaction, conn) -> bool:
    """Check if the user has the configured admin role or is the bot owner."""
    if is_owner(interaction.user.id):
        return True
    config = await conn.fetchrow(
        "SELECT role_admin FROM guild_config WHERE guild_id = $1", interaction.guild_id
    )
    if not config or not config["role_admin"]:
        # Fall back to Discord administrator permission if no admin role is set
        return interaction.user.guild_permissions.administrator
    role = interaction.guild.get_role(config["role_admin"])
    if not role:
        return interaction.user.guild_permissions.administrator
    return role in interaction.user.roles


async def admin_check(interaction: discord.Interaction) -> bool:
    """Guard used at the top of admin command handlers. Sends error and returns False if denied."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        allowed = await has_admin_role(interaction, conn)
    if not allowed:
        await interaction.response.send_message(
            "❌ You don't have permission to use this command.", ephemeral=True
        )
    return allowed


class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ─────────────────────────────────────────
    # /victoria_setup
    # ─────────────────────────────────────────
    @app_commands.command(name="victoria_setup", description="[ADMIN] Initial setup wizard for V.I.C.T.O.R.I.A.")
    @app_commands.default_permissions(administrator=True)
    async def victoria_setup(self, interaction: discord.Interaction):
        if not await admin_check(interaction):
            return
        view = SetupStep1View(interaction.guild)
        await interaction.response.send_message(
            embed=_setup_intro_embed(interaction.guild),
            view=view,
            ephemeral=True,
        )

    # ─────────────────────────────────────────
    # /victoria_config
    # ─────────────────────────────────────────
    @app_commands.command(name="victoria_config", description="[ADMIN] Configure V.I.C.T.O.R.I.A. settings.")
    @app_commands.default_permissions(administrator=True)
    async def victoria_config(self, interaction: discord.Interaction):
        if not await admin_check(interaction):
            return
        pool = await get_pool()
        async with pool.acquire() as conn:
            config = await conn.fetchrow("SELECT * FROM guild_config WHERE guild_id = $1", interaction.guild_id)

        nation_name = config["nation_name"] if config else "Not set"
        turn_hours = config["turn_hours"] if config else 12
        election_days = config["election_days"] if config else 5
        confidence_pct = config["confidence_threshold"] if config else 30
        ultimate_goal = config["ultimate_goal"] if config else "Not set"

        embed = discord.Embed(
            title="⚙️ V.I.C.T.O.R.I.A. Configuration",
            description=(
                "Use the buttons below to configure the bot.\n\n"
                f"**Nation Name:** {nation_name}\n"
                f"**Turn Hours:** {turn_hours}\n"
                f"**Election Days:** {election_days}\n"
                f"**Confidence Threshold:** {confidence_pct}%\n"
                f"**Ultimate Goal:** {ultimate_goal}\n\n"
                "```\n"
                "Rename Guide:\n"
                "  nation_name     — Your nation's name\n"
                "  seat_1..10      — Cabinet seat titles\n"
                "  ultimate_goal   — Win condition text\n"
                "  turn_hours      — Hours per turn (default 12)\n"
                "  election_days   — Days per election cycle (default 5)\n"
                "  confidence_pct  — Opinion threshold for votes (default 30)\n"
                "  ap_senior       — AP for seats 1–5 (default 5)\n"
                "  ap_junior       — AP for seats 6–10 (default 4)\n"
                "  ap_opposition   — AP for opposition (default 3)\n"
                "```"
            ),
            color=0x8B0000,
        )

        view = ConfigView(interaction.guild_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # ─────────────────────────────────────────
    # /victoria_admin
    # ─────────────────────────────────────────
    @app_commands.command(name="victoria_admin", description="[ADMIN] Admin action panel.")
    @app_commands.default_permissions(administrator=True)
    async def victoria_admin(self, interaction: discord.Interaction):
        if not await admin_check(interaction):
            return
        embed = discord.Embed(
            title="🔧 Admin Panel",
            description="Select an admin action below.",
            color=0x8B0000,
        )
        view = AdminPanelView(interaction.guild_id, self.bot)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # ─────────────────────────────────────────
    # /victoria_set_admin_role  (owner only)
    # ─────────────────────────────────────────
    @app_commands.command(name="victoria_set_admin_role", description="[OWNER] Set the admin role for V.I.C.T.O.R.I.A. commands.")
    @app_commands.default_permissions(administrator=True)
    async def victoria_set_admin_role(self, interaction: discord.Interaction, role: discord.Role):
        if not is_owner(interaction.user.id):
            await interaction.response.send_message(
                "❌ Only the bot owner can set the admin role.", ephemeral=True
            )
            return
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE guild_config SET role_admin = $1 WHERE guild_id = $2",
                role.id, interaction.guild_id
            )
        await interaction.response.send_message(
            f"✅ Admin role set to **{role.name}**. Members with this role can now use admin commands.",
            ephemeral=True,
        )


# ─────────────────────────────────────────
# SETUP — channel-select flow (replaces modal)
# ─────────────────────────────────────────

def _setup_intro_embed(guild: discord.Guild) -> discord.Embed:
    return discord.Embed(
        title="🎩 V.I.C.T.O.R.I.A. Setup",
        description=(
            "Welcome! Let's set up your nation step by step.\n\n"
            "**Step 1 of 3 — Core Channels**\n"
            "Use the dropdowns below to pick your channels. "
            "You can choose the same channel for multiple roles if needed.\n\n"
            f"Server: **{guild.name}**"
        ),
        color=0x8B0000,
    )


class SetupStep1View(discord.ui.View):
    """Step 1: pick Menu, Events, Map channels."""

    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=300)
        self.guild = guild
        self.menu_channel_id: int | None = None
        self.events_channel_id: int | None = None
        self.map_channel_id: int | None = None

        self.add_item(ChannelSelect(
            placeholder="📋 Select the Menu channel",
            custom_id="setup_menu_channel",
            callback_attr="menu_channel_id",
            view_ref=self,
            row=0,
        ))
        self.add_item(ChannelSelect(
            placeholder="📰 Select the Events / Gazette channel",
            custom_id="setup_events_channel",
            callback_attr="events_channel_id",
            view_ref=self,
            row=1,
        ))
        self.add_item(ChannelSelect(
            placeholder="🗺️ Select the Map channel",
            custom_id="setup_map_channel",
            callback_attr="map_channel_id",
            view_ref=self,
            row=2,
        ))

    @discord.ui.button(label="Next →", style=discord.ButtonStyle.primary, row=3)
    async def next_step(self, interaction: discord.Interaction, button: discord.ui.Button):
        missing = []
        if not self.menu_channel_id:
            missing.append("Menu")
        if not self.events_channel_id:
            missing.append("Events / Gazette")
        if not self.map_channel_id:
            missing.append("Map")
        if missing:
            await interaction.response.send_message(
                f"❌ Please select all channels first. Missing: **{', '.join(missing)}**",
                ephemeral=True,
            )
            return

        view = SetupStep2View(
            self.guild,
            menu_ch=self.menu_channel_id,
            events_ch=self.events_channel_id,
            map_ch=self.map_channel_id,
        )
        embed = discord.Embed(
            title="🎩 V.I.C.T.O.R.I.A. Setup",
            description=(
                "**Step 2 of 3 — Cabinet Channel & Nation Name**\n"
                "Select the Cabinet channel and type your nation's name."
            ),
            color=0x8B0000,
        )
        await interaction.response.edit_message(embed=embed, view=view)


class SetupStep2View(discord.ui.View):
    """Step 2: pick Cabinet channel."""

    def __init__(self, guild: discord.Guild, menu_ch: int, events_ch: int, map_ch: int):
        super().__init__(timeout=300)
        self.guild = guild
        self.menu_ch = menu_ch
        self.events_ch = events_ch
        self.map_ch = map_ch
        self.cabinet_channel_id: int | None = None

        self.add_item(ChannelSelect(
            placeholder="🏛️ Select the Cabinet channel",
            custom_id="setup_cabinet_channel",
            callback_attr="cabinet_channel_id",
            view_ref=self,
            row=0,
        ))

    @discord.ui.button(label="Next →", style=discord.ButtonStyle.primary, row=1)
    async def next_step(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.cabinet_channel_id:
            await interaction.response.send_message(
                "❌ Please select the Cabinet channel.", ephemeral=True
            )
            return
        await interaction.response.send_modal(
            SetupNationNameModal(
                guild=self.guild,
                menu_ch=self.menu_ch,
                events_ch=self.events_ch,
                map_ch=self.map_ch,
                cabinet_ch=self.cabinet_channel_id,
            )
        )


class ChannelSelect(discord.ui.ChannelSelect):
    """Reusable channel select that writes the chosen ID back to a view attribute."""

    def __init__(self, *, placeholder: str, custom_id: str, callback_attr: str, view_ref, row: int):
        super().__init__(
            placeholder=placeholder,
            custom_id=custom_id,
            channel_types=[discord.ChannelType.text],
            row=row,
        )
        self._callback_attr = callback_attr
        self._view_ref = view_ref

    async def callback(self, interaction: discord.Interaction):
        setattr(self._view_ref, self._callback_attr, self.values[0].id)
        await interaction.response.defer()


class SetupNationNameModal(discord.ui.Modal, title="Nation Name"):
    nation_name = discord.ui.TextInput(
        label="Nation Name",
        placeholder="e.g. The British Empire",
        default="The British Empire",
        max_length=60,
        required=True,
    )

    def __init__(self, *, guild, menu_ch, events_ch, map_ch, cabinet_ch):
        super().__init__()
        self.guild = guild
        self.menu_ch = menu_ch
        self.events_ch = events_ch
        self.map_ch = map_ch
        self.cabinet_ch = cabinet_ch

    async def on_submit(self, interaction: discord.Interaction):
        # Respond immediately — all heavy work happens in a background task
        await interaction.response.send_message(
            f"⚙️ Setting up **{self.nation_name}**… This may take a moment. I'll update you when done.",
            ephemeral=True,
        )
        asyncio.create_task(self._run_setup(interaction))

    async def _run_setup(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        nation = str(self.nation_name)
        pool = await get_pool()

        try:
            next_turn = datetime.now(timezone.utc) + timedelta(hours=12)
            next_election = datetime.now(timezone.utc) + timedelta(days=5)

            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO guild_config (
                        guild_id, nation_name, channel_menu, channel_events, channel_map,
                        channel_cabinet, next_turn_at, next_election_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (guild_id) DO UPDATE SET
                        nation_name = EXCLUDED.nation_name,
                        channel_menu = EXCLUDED.channel_menu,
                        channel_events = EXCLUDED.channel_events,
                        channel_map = EXCLUDED.channel_map,
                        channel_cabinet = EXCLUDED.channel_cabinet,
                        next_turn_at = EXCLUDED.next_turn_at,
                        next_election_at = EXCLUDED.next_election_at
                """, guild_id, nation, self.menu_ch, self.events_ch, self.map_ch,
                    self.cabinet_ch, next_turn, next_election)

                await seed_guild(guild_id, conn)

                from utils.empress import seed_empress, build_empress_embed
                await seed_empress(guild_id, conn)

                await save_map_to_db(guild_id, conn)

                # Post menu embed
                menu_channel = self.guild.get_channel(self.menu_ch)
                if menu_channel:
                    embed = await build_menu_embed(guild_id, conn)
                    msg = await menu_channel.send(embed=embed, view=MainMenuView(guild_id))
                    await conn.execute(
                        "UPDATE guild_config SET menu_message_id = $1 WHERE guild_id = $2",
                        msg.id, guild_id
                    )

                # Post Empress embed
                events_channel = self.guild.get_channel(self.events_ch)
                if events_channel:
                    empress_embed = await build_empress_embed(guild_id, conn)
                    emp_msg = await events_channel.send(embed=empress_embed)
                    try:
                        await emp_msg.pin()
                    except Exception:
                        pass
                    await conn.execute(
                        "UPDATE guild_config SET empress_message_id = $1 WHERE guild_id = $2",
                        emp_msg.id, guild_id
                    )

                # Post cabinet embed
                cab_channel = self.guild.get_channel(self.cabinet_ch)
                if cab_channel:
                    embed = await build_cabinet_embed(guild_id, conn)
                    msg = await cab_channel.send(embed=embed)
                    await conn.execute(
                        "UPDATE guild_config SET cabinet_message_id = $1 WHERE guild_id = $2",
                        msg.id, guild_id
                    )

                # Render and post map
                from utils.maprender import render_map_for_guild
                map_channel = self.guild.get_channel(self.map_ch)
                if map_channel:
                    buf = await render_map_for_guild(guild_id, conn)
                    file = discord.File(buf, filename="victoria_map.png")
                    map_msg = await map_channel.send(file=file)
                    await conn.execute(
                        "UPDATE guild_config SET map_message_id = $1 WHERE guild_id = $2",
                        map_msg.id, guild_id
                    )

            await interaction.followup.send(
                f"✅ **V.I.C.T.O.R.I.A.** has been set up for **{nation}**!\n"
                f"The menu, map, cabinet, and Empress are all live.\n"
                f"Use `/victoria_config` to set a leaderboard channel and header image.\n"
                f"Use `/victoria_set_admin_role` to assign an admin role.\n"
                f"First turn resolves <t:{int(next_turn.timestamp())}:R>.",
                ephemeral=True,
            )

        except Exception as e:
            await interaction.followup.send(
                f"❌ Setup failed: `{e}`\nCheck bot permissions and try again.",
                ephemeral=True,
            )


# ─────────────────────────────────────────
# CONFIG VIEW & MODALS
# ─────────────────────────────────────────
class ConfigView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id

    @discord.ui.button(label="✏️ Rename Nation / Goal", style=discord.ButtonStyle.primary, row=0)
    async def rename_nation(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RenameNationModal(self.guild_id))

    @discord.ui.button(label="🪑 Rename Cabinet Seats", style=discord.ButtonStyle.secondary, row=0)
    async def rename_seats(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RenameSeatModal(self.guild_id))

    @discord.ui.button(label="⏱️ Adjust Timers", style=discord.ButtonStyle.secondary, row=0)
    async def adjust_timers(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TimerModal(self.guild_id))

    @discord.ui.button(label="⚡ Adjust AP", style=discord.ButtonStyle.secondary, row=0)
    async def adjust_ap(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(APModal(self.guild_id))

    @discord.ui.button(label="🖼️ Set Header Image", style=discord.ButtonStyle.secondary, row=1)
    async def set_header_image(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(HeaderImageModal(self.guild_id))

    @discord.ui.button(label="👑 Set Empress Portrait", style=discord.ButtonStyle.secondary, row=1)
    async def set_empress_portrait(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EmpressPortraitModal(self.guild_id))

    @discord.ui.button(label="📊 Set Leaderboard Channel", style=discord.ButtonStyle.secondary, row=1)
    async def set_leaderboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="📊 Set Leaderboard Channel",
            description="Select the channel where the Hall of Power leaderboard will be posted and kept live.",
            color=0x8B0000,
        )
        await interaction.response.send_message(embed=embed, view=LeaderboardChannelView(self.guild_id), ephemeral=True)


class LeaderboardChannelView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        select = discord.ui.ChannelSelect(
            placeholder="Select the leaderboard channel...",
            channel_types=[discord.ChannelType.text],
        )
        select.callback = self.channel_selected
        self.add_item(select)

    async def channel_selected(self, interaction: discord.Interaction):
        channel_id = self.children[0].values[0].id
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE guild_config SET channel_leaderboard = $1 WHERE guild_id = $2",
                channel_id, self.guild_id
            )
            channel = interaction.guild.get_channel(channel_id)
            if channel:
                embed = await build_leaderboard_embed(self.guild_id, conn)
                msg = await channel.send(embed=embed)
                await conn.execute(
                    "UPDATE guild_config SET leaderboard_message_id = $1 WHERE guild_id = $2",
                    msg.id, self.guild_id
                )
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="✅ Leaderboard channel set",
                description=f"The Hall of Power is now live in <#{channel_id}>.",
                color=0x228B22,
            ),
            view=None,
        )


class RenameNationModal(discord.ui.Modal, title="Rename Nation & Goal"):
    nation_name = discord.ui.TextInput(label="Nation Name", max_length=60, required=True)
    ultimate_goal = discord.ui.TextInput(
        label="Ultimate Goal",
        style=discord.TextStyle.paragraph,
        max_length=300,
        required=True,
    )

    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE guild_config SET nation_name = $1, ultimate_goal = $2 WHERE guild_id = $3
            """, str(self.nation_name), str(self.ultimate_goal), self.guild_id)
        await interaction.response.send_message("✅ Nation name and goal updated.", ephemeral=True)


class RenameSeatModal(discord.ui.Modal, title="Rename a Cabinet Seat"):
    seat_number = discord.ui.TextInput(label="Seat Number (1–10)", max_length=2, required=True)
    new_title = discord.ui.TextInput(label="New Title", max_length=60, required=True)
    new_description = discord.ui.TextInput(
        label="New Description",
        style=discord.TextStyle.paragraph,
        max_length=200,
        required=True,
    )

    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            seat_num = int(str(self.seat_number))
            if not 1 <= seat_num <= 10:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ Seat number must be 1–10.", ephemeral=True)
            return

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE cabinet_seats SET title = $1, description = $2
                WHERE guild_id = $3 AND seat_number = $4
            """, str(self.new_title), str(self.new_description), self.guild_id, seat_num)
        await interaction.response.send_message(f"✅ Seat {seat_num} renamed to **{self.new_title}**.", ephemeral=True)


class TimerModal(discord.ui.Modal, title="Adjust Turn & Election Timers"):
    turn_hours = discord.ui.TextInput(label="Turn Duration (hours)", default="12", max_length=3)
    election_days = discord.ui.TextInput(label="Election Cycle (days)", default="5", max_length=3)
    confidence_pct = discord.ui.TextInput(label="Confidence Threshold (%)", default="30", max_length=3)

    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            th = int(str(self.turn_hours))
            ed = int(str(self.election_days))
            cp = int(str(self.confidence_pct))
        except ValueError:
            await interaction.response.send_message("❌ Values must be whole numbers.", ephemeral=True)
            return

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE guild_config SET turn_hours = $1, election_days = $2, confidence_threshold = $3
                WHERE guild_id = $4
            """, th, ed, cp, self.guild_id)
        await interaction.response.send_message(
            f"✅ Timers updated: **{th}h** turns, **{ed}d** elections, **{cp}%** confidence threshold.",
            ephemeral=True
        )


class APModal(discord.ui.Modal, title="Adjust Action Points"):
    ap_senior = discord.ui.TextInput(label="AP — Senior Cabinet (Seats 1–5)", default="5", max_length=2)
    ap_junior = discord.ui.TextInput(label="AP — Junior Cabinet (Seats 6–10)", default="4", max_length=2)
    ap_opposition = discord.ui.TextInput(label="AP — Opposition", default="3", max_length=2)

    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            s = int(str(self.ap_senior))
            j = int(str(self.ap_junior))
            o = int(str(self.ap_opposition))
        except ValueError:
            await interaction.response.send_message("❌ Values must be whole numbers.", ephemeral=True)
            return

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE guild_config SET ap_cabinet_senior = $1, ap_cabinet_junior = $2, ap_opposition = $3
                WHERE guild_id = $4
            """, s, j, o, self.guild_id)
        await interaction.response.send_message(
            f"✅ AP updated: Senior **{s}**, Junior **{j}**, Opposition **{o}**.",
            ephemeral=True
        )


class HeaderImageModal(discord.ui.Modal, title="Set Header Image"):
    image_url = discord.ui.TextInput(
        label="Image URL",
        placeholder="https://cdn.discordapp.com/attachments/...",
        max_length=500,
        required=True,
    )

    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE guild_config SET header_image_url = $1 WHERE guild_id = $2
            """, str(self.image_url), self.guild_id)
        await interaction.response.send_message("✅ Header image updated. It will appear on all embeds.", ephemeral=True)


class EmpressPortraitModal(discord.ui.Modal, title="Set Empress Portrait"):
    portrait_url = discord.ui.TextInput(
        label="Portrait Image URL",
        placeholder="https://cdn.discordapp.com/attachments/...",
        max_length=500,
        required=True,
    )

    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE empress SET portrait_url = $1 WHERE guild_id = $2
            """, str(self.portrait_url), self.guild_id)
        await interaction.response.send_message("✅ Empress portrait updated.", ephemeral=True)


# ─────────────────────────────────────────
# ADMIN PANEL VIEW
# ─────────────────────────────────────────
class AdminPanelView(discord.ui.View):
    def __init__(self, guild_id: int, bot):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.bot = bot

    @discord.ui.button(label="⏭️ Force Turn Resolution", style=discord.ButtonStyle.danger)
    async def force_turn(self, interaction: discord.Interaction, button: discord.ui.Button):
        from utils.turn_engine import resolve_turn
        from utils.scheduler import post_turn_summary, refresh_all_embeds
        await interaction.response.defer(ephemeral=True)
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await resolve_turn(self.guild_id, bot=self.bot)
            if result:
                await post_turn_summary(self.bot, self.guild_id, result, conn)
            await refresh_all_embeds(self.bot, self.guild_id, conn)
        await interaction.followup.send("✅ Turn forced and resolved.", ephemeral=True)

    @discord.ui.button(label="🗳️ Force Election", style=discord.ButtonStyle.danger)
    async def force_election(self, interaction: discord.Interaction, button: discord.ui.Button):
        from utils.elections import resolve_election
        from utils.scheduler import post_election_result, refresh_all_embeds
        await interaction.response.defer(ephemeral=True)
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await resolve_election(self.guild_id, conn)
            await post_election_result(self.bot, self.guild_id, result, conn)
            await refresh_all_embeds(self.bot, self.guild_id, conn)
        await interaction.followup.send("✅ Election forced and resolved.", ephemeral=True)

    @discord.ui.button(label="🔄 Refresh All Embeds", style=discord.ButtonStyle.secondary)
    async def refresh_embeds(self, interaction: discord.Interaction, button: discord.ui.Button):
        from utils.scheduler import refresh_all_embeds
        await interaction.response.defer(ephemeral=True)
        pool = await get_pool()
        async with pool.acquire() as conn:
            await refresh_all_embeds(self.bot, self.guild_id, conn)
        await interaction.followup.send("✅ All embeds refreshed.", ephemeral=True)

    @discord.ui.button(label="🗺️ Regenerate Map", style=discord.ButtonStyle.danger)
    async def regen_map(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RegenMapConfirmModal(self.guild_id))

    @discord.ui.button(label="💀 Full Server Reset", style=discord.ButtonStyle.danger, row=1)
    async def full_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(FullResetModal(self.guild_id, self.bot))


class RegenMapConfirmModal(discord.ui.Modal, title="Confirm Map Regeneration"):
    confirm = discord.ui.TextInput(
        label="Type CONFIRM to regenerate the map",
        max_length=10,
        required=True,
    )

    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        if str(self.confirm).upper() != "CONFIRM":
            await interaction.response.send_message("❌ Cancelled.", ephemeral=True)
            return

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM hex_map WHERE guild_id = $1", self.guild_id)
            await conn.execute("DELETE FROM npc_nations WHERE guild_id = $1", self.guild_id)
            await conn.execute("DELETE FROM nation_state WHERE guild_id = $1", self.guild_id)
            await save_map_to_db(self.guild_id, conn)

        await interaction.response.send_message("✅ Map regenerated.", ephemeral=True)


class FullResetModal(discord.ui.Modal, title="Full Server Reset — IRREVERSIBLE"):
    confirm = discord.ui.TextInput(
        label='Type "RESET EVERYTHING" to confirm',
        placeholder="RESET EVERYTHING",
        max_length=20,
        required=True,
    )

    def __init__(self, guild_id: int, bot):
        super().__init__()
        self.guild_id = guild_id
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        if str(self.confirm).strip().upper() != "RESET EVERYTHING":
            await interaction.response.send_message(
                "❌ Reset cancelled. You must type **RESET EVERYTHING** exactly.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        pool = await get_pool()
        try:
            async with pool.acquire() as conn:
                # Wipe all game data for this guild, preserve guild_config channels/settings
                tables = [
                    "national_act_votes", "turn_actions", "turn_history", "national_events",
                    "national_acts", "war_campaigns", "leaderboard",
                    "cabinet_assignments", "players",
                    "hex_map", "npc_nations", "nation_state",
                    "empress",
                ]
                for table in tables:
                    await conn.execute(f"DELETE FROM {table} WHERE guild_id = $1", self.guild_id)

                # Re-seed fresh game state
                from db.seed import seed_guild
                from utils.mapgen import save_map_to_db
                from utils.empress import seed_empress

                await seed_guild(self.guild_id, conn)
                await seed_empress(self.guild_id, conn)
                await save_map_to_db(self.guild_id, conn)

                # Reset turn timer
                from datetime import datetime, timedelta, timezone
                next_turn = datetime.now(timezone.utc) + timedelta(hours=12)
                await conn.execute(
                    "UPDATE guild_config SET next_turn_at = $1 WHERE guild_id = $2",
                    next_turn, self.guild_id
                )

                # Refresh all persistent embeds
                from utils.scheduler import refresh_all_embeds
                await refresh_all_embeds(self.bot, self.guild_id, conn)

            await interaction.followup.send(
                "✅ **Full reset complete.** All characters, turns, actions, and map data have been wiped. "
                "The game clock has been reset. Channel configuration has been preserved.",
                ephemeral=True,
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Reset failed: `{e}`", ephemeral=True)


async def setup(bot):
    await bot.add_cog(AdminCog(bot))
