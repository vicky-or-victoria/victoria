"""
Character Panel — shows a player's stats, seat, AP, and opinion rating.
FIX: Victorian-era immersive language.
FIX: Shows Discord ping beside character name.
"""
import discord
from discord.ui import View, Button
from db.connection import get_pool


class CharacterView(View):
    def __init__(self, guild_id: int, player_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.player_id = player_id

    @discord.ui.button(label="← Back to Menu", style=discord.ButtonStyle.secondary, row=0)
    async def back(self, interaction: discord.Interaction, button: Button):
        from views.menu import build_menu_embed, MainMenuView
        pool = await get_pool()
        async with pool.acquire() as conn:
            embed = await build_menu_embed(self.guild_id, conn)
            await interaction.response.edit_message(embed=embed, view=MainMenuView(self.guild_id))

    @staticmethod
    async def send(interaction: discord.Interaction, conn):
        guild_id = interaction.guild_id
        user_id = interaction.user.id

        player = await conn.fetchrow("""
            SELECT p.*, ca.seat_number, cs.title as seat_title
            FROM players p
            LEFT JOIN cabinet_assignments ca ON ca.player_id = p.id AND ca.guild_id = p.guild_id
            LEFT JOIN cabinet_seats cs ON cs.guild_id = p.guild_id AND cs.seat_number = ca.seat_number
            WHERE p.guild_id = $1 AND p.user_id = $2
        """, guild_id, user_id)

        if not player:
            embed = discord.Embed(
                title="👤 No Character on Record",
                description=(
                    "*The clerk consults the register and finds no entry under your name.*\n\n"
                    "You have not yet entered the political arena of the Empire. "
                    "Press **Join the Game** below to create your personage and begin your rise to power."
                ),
                color=0x8B0000,
            )
            view = JoinGameView(guild_id)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            return

        def stat_bar(val, length=8):
            filled = int((val / 10) * length)
            return "█" * filled + "░" * (length - filled)

        seat_str = (
            f"**{player['seat_title']}** — Seat {player['seat_number']}"
            if player["seat_number"] else "**Opposition Benches**"
        )
        opinion_bar = "█" * int(player["opinion_rating"] / 10) + "░" * (10 - int(player["opinion_rating"] / 10))
        user_ping = f"<@{user_id}>"

        embed = discord.Embed(
            title=f"👤 {player['character_name']}",
            description=(
                f"*Minister's dossier, as maintained by the Imperial Registry.*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"**Personage:** {player['character_name']} ({user_ping})\n"
                f"**Position:** {seat_str}\n"
                f"**Action Points Remaining:** {player['ap_remaining']}\n"
                f"**Public Standing:** `{opinion_bar}` {player['opinion_rating']}/100\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"**Influence**  `{stat_bar(player['influence'])}` {player['influence']}/10\n"
                f"**Charisma**   `{stat_bar(player['charisma'])}` {player['charisma']}/10\n"
                f"**Cunning**    `{stat_bar(player['cunning'])}` {player['cunning']}/10\n"
                f"**Resolve**    `{stat_bar(player['resolve'])}` {player['resolve']}/10\n"
                f"**Wealth**     `{stat_bar(player['wealth'])}` {player['wealth']}/10\n"
                f"**Legitimacy** `{stat_bar(player['legitimacy'])}` {player['legitimacy']}/10\n"
            ),
            color=0x8B0000,
        )
        embed.set_footer(text="V.I.C.T.O.R.I.A. · Personal Dossier — Eyes Only")

        view = CharacterView(guild_id, player["id"])
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class JoinGameView(View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id

    @discord.ui.button(label="🎩 Enter the Political Arena", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, button: Button):
        modal = JoinModal(self.guild_id)
        await interaction.response.send_modal(modal)


class JoinModal(discord.ui.Modal, title="Register Your Character"):
    character_name = discord.ui.TextInput(
        label="Character Name",
        placeholder="e.g. Lord Edmund Blackwood, Lady Cecilia Frome…",
        max_length=50,
        required=True,
    )

    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        pool = await get_pool()
        async with pool.acquire() as conn:
            existing = await conn.fetchrow("""
                SELECT id FROM players WHERE guild_id = $1 AND user_id = $2
            """, self.guild_id, interaction.user.id)

            if existing:
                await interaction.response.send_message(
                    "You are already registered in the Imperial rolls.", ephemeral=True
                )
                return

            await conn.execute("""
                INSERT INTO players (guild_id, user_id, character_name)
                VALUES ($1, $2, $3)
            """, self.guild_id, interaction.user.id, str(self.character_name))

        embed = discord.Embed(
            title="🎩 Welcome to the Imperial Arena",
            description=(
                f"*The clerk inscribes your name upon the register with a flourish of his quill.*\n\n"
                f"**{self.character_name}** (<@{interaction.user.id}>) has entered the political stage.\n\n"
                "You begin your career upon the **Opposition Benches**. "
                "Build your reputation, cultivate alliances, and campaign for office "
                "to secure a seat in Her Majesty's Cabinet.\n\n"
                "*The Empire watches. Make it count.*"
            ),
            color=0x8B0000,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        try:
            await interaction.response.send_message("❌ An error occurred registering your character. Please try again.", ephemeral=True)
        except Exception:
            await interaction.followup.send("❌ An error occurred.", ephemeral=True)
