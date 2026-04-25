"""
Events Panel — shows recent Imperial Gazette entries.
"""
import discord
from discord.ui import View
from db.connection import get_pool
from utils.gazette import format_vic_date, ordinal


class EventsView(View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=120)
        self.guild_id = guild_id

    @discord.ui.button(label="📰 Latest Edition", style=discord.ButtonStyle.primary)
    async def latest(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                await _send_latest(interaction, self.guild_id, conn)
        except Exception as e:
            print(f"[EventsView.latest] {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ *Something went wrong.*", ephemeral=True)
            else:
                await interaction.followup.send("❌ *Something went wrong.*", ephemeral=True)

    @discord.ui.button(label="📚 Turn History", style=discord.ButtonStyle.secondary)
    async def history(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                await _send_history(interaction, self.guild_id, conn)
        except Exception as e:
            print(f"[EventsView.history] {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ *Something went wrong.*", ephemeral=True)
            else:
                await interaction.followup.send("❌ *Something went wrong.*", ephemeral=True)

    @staticmethod
    async def send(interaction: discord.Interaction, conn):
        guild_id = interaction.guild_id
        config = await conn.fetchrow(
            "SELECT nation_name, vic_year, vic_month, vic_day FROM guild_config WHERE guild_id = $1", guild_id
        )
        nation = await conn.fetchrow("SELECT turn_number FROM nation_state WHERE guild_id = $1", guild_id)
        turn = nation["turn_number"] if nation else 1

        vic_date = format_vic_date(
            config["vic_year"] if config else 1878,
            config["vic_month"] if config else 1,
            config["vic_day"] if config else 1,
        ) if config else "1st January, 1878"

        embed = discord.Embed(
            title="📰 The Imperial Gazette — Reading Room",
            description=(
                f"*Est. 1837 · Published by Authority of the Crown*\n"
                f"**{config['nation_name'] if config else 'The Empire'}** · "
                f"Turn the {ordinal(turn)} · {vic_date}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"*The Gazette is the paper of record for all affairs of state, "
                f"published continuously as events unfold.*\n\n"
                f"Recent editions are posted directly to the Gazette channel. "
                f"Use the buttons below to browse past dispatches."
            ),
            color=0x1a2744,
        )
        embed.set_footer(text="Printed at the Imperial Press, Westminster · V.I.C.T.O.R.I.A.")
        view = EventsView(guild_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def _send_latest(interaction: discord.Interaction, guild_id: int, conn):
    entries = await conn.fetch("""
        SELECT tier, section, headline, body, vic_date, turn_number
        FROM gazette_entries
        WHERE guild_id = $1
        ORDER BY created_at DESC LIMIT 5
    """, guild_id)

    if not entries:
        await interaction.response.send_message(
            "*No editions have yet been published. The press is warming up.*",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="📰 The Imperial Gazette — Latest Dispatches",
        description="*The five most recent entries from the Gazette archive.*",
        color=0x1a2744,
    )
    for e in entries:
        tier_label = {"A": "🔴 MAJOR", "B": "🟡 NOTABLE", "C": "⚪ MINOR"}.get(e["tier"], "📌")
        date_str = e["vic_date"] or "Unknown date"
        body = e["body"] or "*No content.*"
        value = f"*{date_str}*\n{body[:200]}…" if len(body) > 200 else f"*{date_str}*\n{body}"
        embed.add_field(
            name=f"{tier_label} — {e['headline'][:100]}" or "Untitled",
            value=value,
            inline=False,
        )
    embed.set_footer(text="Printed at the Imperial Press, Westminster · V.I.C.T.O.R.I.A.")
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def _send_history(interaction: discord.Interaction, guild_id: int, conn):
    history = await conn.fetch("""
        SELECT turn_number, narrative, vic_date
        FROM turn_history
        WHERE guild_id = $1
        ORDER BY turn_number DESC LIMIT 8
    """, guild_id)

    if not history:
        await interaction.response.send_message(
            "*No turns have yet been resolved. History is yet to be written.*",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="📚 The Imperial Record — Turn History",
        description="*A chronicle of the Empire's political history, turn by turn.*",
        color=0x4B3010,
    )
    for h in history:
        date_str = h["vic_date"] or "Unknown date"
        narrative = h["narrative"] or "*No record.*"
        embed.add_field(
            name=f"Turn {ordinal(h['turn_number'])} — {date_str}",
            value=narrative[:300],
            inline=False,
        )
    embed.set_footer(text="V.I.C.T.O.R.I.A. · Omnia pro Imperio")
    await interaction.response.send_message(embed=embed, ephemeral=True)
