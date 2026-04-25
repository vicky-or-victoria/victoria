"""
Cabinet Panel — displays the current cabinet with opinion ratings.
Live-updating persistent embed on the cabinet channel.
FIX: character names now include Discord user pings.
FIX: auto-updates via refresh_all_embeds.
FIX: Victorian flavour language.
"""
import discord
from discord.ui import View, Button
from db.connection import get_pool


class CabinetView(View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id

    @discord.ui.button(label="🗳️ Call Confidence Vote", style=discord.ButtonStyle.danger, custom_id="cabinet_vote")
    async def vote_confidence(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(
            "A motion of confidence may be tabled through **🎭 Take Action** — "
            "select *Call Confidence Vote* or *Demand Confidence Vote* depending on your station.",
            ephemeral=True
        )

    @discord.ui.button(label="← Return to Menu", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: Button):
        from views.menu import build_menu_embed, MainMenuView
        pool = await get_pool()
        async with pool.acquire() as conn:
            embed = await build_menu_embed(self.guild_id, conn)
            await interaction.response.edit_message(embed=embed, view=MainMenuView(self.guild_id))

    @staticmethod
    async def send(interaction: discord.Interaction, conn):
        guild_id = interaction.guild_id
        embed = await build_cabinet_embed(guild_id, conn)
        view = CabinetView(guild_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def build_cabinet_embed(guild_id: int, conn) -> discord.Embed:
    config = await conn.fetchrow("SELECT nation_name, confidence_threshold, header_image_url FROM guild_config WHERE guild_id = $1", guild_id)
    nation_name = config["nation_name"] if config else "The Empire"
    threshold = config["confidence_threshold"] if config else 30
    header_url = config["header_image_url"] if config else None

    seats = await conn.fetch("""
        SELECT cs.seat_number, cs.title, cs.description,
               p.character_name, p.opinion_rating, p.user_id,
               ca.turns_held
        FROM cabinet_seats cs
        LEFT JOIN cabinet_assignments ca ON ca.guild_id = cs.guild_id AND ca.seat_number = cs.seat_number
        LEFT JOIN players p ON p.id = ca.player_id
        WHERE cs.guild_id = $1
        ORDER BY cs.seat_number ASC
    """, guild_id)

    def opinion_bar(val, length=8):
        filled = int((val / 100) * length)
        color = "🟩" if val >= 60 else ("🟨" if val >= 35 else "🟥")
        return color * filled + "⬛" * (length - filled)

    lines = []
    for seat in seats:
        char_name = seat["character_name"]
        user_id = seat["user_id"]
        opinion = seat["opinion_rating"] if seat["opinion_rating"] is not None else 0
        turns = seat["turns_held"] or 0
        at_risk = " ⚠️" if seat["opinion_rating"] is not None and opinion < threshold else ""

        if char_name:
            holder_display = f"{char_name} (<@{user_id}>)" if user_id else char_name
        else:
            holder_display = "*Vacant — Awaiting appointment*"

        lines.append(
            f"**{seat['seat_number']}. {seat['title']}**\n"
            f"└ {holder_display} · {opinion_bar(opinion)} {opinion}%{at_risk} · {turns} turns\n"
        )

    embed = discord.Embed(
        title=f"🏛️ Cabinet of {nation_name}",
        description=(
            f"*Her Majesty's Government — the ministers who bear the weight of empire.*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            + ("\n".join(lines) or "*No ministers have yet been appointed.*")
        ),
        color=0x4169E1,
    )
    embed.set_footer(text=f"⚠️ = Below {threshold}% confidence threshold · V.I.C.T.O.R.I.A.")
    return embed


async def update_cabinet_embed(bot, guild_id: int, conn):
    """Live-refresh the cabinet channel embed."""
    config = await conn.fetchrow(
        "SELECT channel_cabinet, cabinet_message_id FROM guild_config WHERE guild_id = $1", guild_id
    )
    if not config or not config["channel_cabinet"] or not config["cabinet_message_id"]:
        return

    channel = bot.get_channel(config["channel_cabinet"])
    if not channel:
        return

    try:
        message = await channel.fetch_message(config["cabinet_message_id"])
        embed = await build_cabinet_embed(guild_id, conn)
        await message.edit(embed=embed)
    except Exception as e:
        print(f"Cabinet embed update failed: {e}")
