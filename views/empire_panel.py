"""
Empire Panel — shows nation stats, hex count, NPC nations, ultimate goal.
FIX: Added map image render inline when The Empire button is pressed (request #9).
FIX: EventsView moved to views/events_panel.py (this file keeps WarView + leaderboard).
FIX: Victorian-era immersive language throughout.
FIX: Character names show Discord ping.
"""
import discord
from discord.ui import View, Button
from db.connection import get_pool


class EmpireView(View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id

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
        config = await conn.fetchrow("SELECT nation_name, ultimate_goal, header_image_url FROM guild_config WHERE guild_id = $1", guild_id)
        nation = await conn.fetchrow("SELECT * FROM nation_state WHERE guild_id = $1", guild_id)

        total_hexes = await conn.fetchval("SELECT COUNT(*) FROM hex_map WHERE guild_id = $1", guild_id)
        npc_nations = await conn.fetch("""
            SELECT name, government_type, military, economy, stability, disposition, is_defeated
            FROM npc_nations WHERE guild_id = $1 ORDER BY military DESC LIMIT 10
        """, guild_id)

        nation_name = config["nation_name"] if config else "The Empire"
        goal = config["ultimate_goal"] if config else "Achieve Imperial status."
        header_url = config["header_image_url"] if config else None
        hex_count = nation["hex_count"] if nation else 4
        at_war = nation["at_war_with"] if nation else []
        goal_pct = round((hex_count / max(total_hexes or 1, 1)) * 100, 1)

        def disp_emoji(d):
            return {"friendly": "🟢", "neutral": "🟡", "hostile": "🔴"}.get(d, "⬜")

        gov_titles = {
            "monarchy": "Kingdom", "empire": "Empire", "republic": "Republic",
            "theocracy": "Theocracy", "oligarchy": "Oligarchy", "sultanate": "Sultanate", "duchy": "Duchy"
        }

        npc_lines = []
        for n in npc_nations:
            status = "~~" if n["is_defeated"] else ""
            war_str = " ⚔️ *AT WAR*" if n["name"] in (at_war or []) else ""
            gov = gov_titles.get(n["government_type"], n["government_type"].title())
            npc_lines.append(
                f"{disp_emoji(n['disposition'])} {status}**{n['name']}**{status} "
                f"— {gov} · ⚔️ {n['military']}/10 · 💰 {n['economy']}/10{war_str}"
            )

        war_str_display = ", ".join(f"**{w}**" for w in at_war) if at_war else "*No active hostilities*"

        embed = discord.Embed(
            title=f"🗺️ {nation_name} — The Known World",
            description=(
                f"*A survey of the realm as known to the Imperial Cartographic Office.*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"**Imperial Ambition:** {goal}\n"
                f"**Territorial Holdings:** {hex_count} hexes — {goal_pct}% of the known world\n"
                f"**Current Belligerents:** {war_str_display}\n\n"
                f"**Known Powers of the World:**\n" + "\n".join(npc_lines or ["*No foreign powers yet charted.*"])
            ),
            color=0x228B22,
        )

        if header_url:
            embed.set_image(url=header_url)

        embed.set_footer(text="🟢 Allied · 🟡 Neutral · 🔴 Hostile · ⚔️ Military · 💰 Economy · V.I.C.T.O.R.I.A.")

        # Render and attach the map image inline
        try:
            from utils.maprender import render_map_for_guild
            import io
            buf = await render_map_for_guild(guild_id, conn)
            map_file = discord.File(buf, filename="empire_map.png")
            await interaction.response.send_message(
                embed=embed,
                file=map_file,
                view=EmpireView(guild_id),
                ephemeral=True
            )
        except Exception as e:
            print(f"Map render inline error: {e}")
            # Fall back to embed-only if map fails
            await interaction.response.send_message(embed=embed, view=EmpireView(guild_id), ephemeral=True)


# ─────────────────────────────────────────────────────────────────────
# WAR PANEL
# ─────────────────────────────────────────────────────────────────────

class WarView(View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id

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
        campaigns = await conn.fetch("""
            SELECT * FROM war_campaigns WHERE guild_id = $1 AND status = 'active'
            ORDER BY created_at DESC
        """, guild_id)

        nation = await conn.fetchrow("SELECT military FROM nation_state WHERE guild_id = $1", guild_id)
        config = await conn.fetchrow("SELECT header_image_url FROM guild_config WHERE guild_id = $1", guild_id)
        mil = nation["military"] if nation else 5
        header_url = config["header_image_url"] if config else None

        if not campaigns:
            embed = discord.Embed(
                title="⚔️ The War Office",
                description=(
                    f"*The halls of the War Office stand silent. No campaigns are presently in the field.*\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"**National Military Strength:** {mil}/10\n\n"
                    "To commit the Empire's forces to war, issue a **Declare War** action "
                    "through the 🎭 **Take Action** menu. Only the Prime Minister and "
                    "Secretary of State for War may authorise hostilities."
                ),
                color=0x8B0000,
            )
        else:
            lines = []
            for c in campaigns:
                bar_len = 10
                total = max(c["attacker_strength"] + c["defender_strength"], 1)
                att = min(int((c["attacker_strength"] / total) * bar_len), bar_len)
                def_bar = bar_len - att
                lines.append(
                    f"**Campaign vs. {c['target_nation']}** *(Since Turn {c['started_turn']})*\n"
                    f"Imperial Forces: `{'█' * att}{'░' * def_bar}` vs. Enemy: `{'█' * def_bar}{'░' * att}`\n"
                    f"Hexes Contested: **{len(c['hexes_contested'])}**\n"
                )
            embed = discord.Embed(
                title="⚔️ The War Office — Active Campaigns",
                description=(
                    f"*Dispatches from the front, as received by the Secretary of State for War.*\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    + "\n".join(lines)
                ),
                color=0x8B0000,
            )

        if header_url:
            embed.set_image(url=header_url)
        embed.set_footer(text="V.I.C.T.O.R.I.A. · Secretary of State for War")
        await interaction.response.send_message(embed=embed, view=WarView(guild_id), ephemeral=True)


# ─────────────────────────────────────────────────────────────────────
# LEADERBOARD PANEL (persistent channel embed)
# ─────────────────────────────────────────────────────────────────────

async def build_leaderboard_embed(guild_id: int, conn) -> discord.Embed:
    config = await conn.fetchrow("SELECT nation_name FROM guild_config WHERE guild_id = $1", guild_id)
    nation_name = config["nation_name"] if config else "The Empire"

    records = await conn.fetch("""
        SELECT p.character_name, p.user_id, l.seat_title, l.turns_served, l.started_at, l.ended_at
        FROM leaderboard l
        JOIN players p ON p.id = l.player_id
        WHERE l.guild_id = $1
        ORDER BY l.turns_served DESC
        LIMIT 15
    """, guild_id)

    lines = []
    medals = ["🥇", "🥈", "🥉"]
    for i, r in enumerate(records):
        medal = medals[i] if i < 3 else f"`{i+1}.`"
        status = "*(In office)*" if not r["ended_at"] else ""
        user_ping = f" <@{r['user_id']}>" if r["user_id"] else ""
        lines.append(
            f"{medal} **{r['character_name']}**{user_ping} — {r['seat_title']}\n"
            f"   └ {r['turns_served']} turns served {status}"
        )

    embed = discord.Embed(
        title=f"📊 {nation_name} — Hall of Power",
        description=(
            "*Here are enshrined the names of those who have served the Empire with distinction.*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            + ("\n".join(lines) or "*No records yet. Be the first to serve the Empire!*")
        ),
        color=0xFFD700,
    )
    embed.set_footer(text="Ranked by longest tenure · V.I.C.T.O.R.I.A.")
    return embed


async def update_leaderboard_embed(bot, guild_id: int, conn):
    config = await conn.fetchrow(
        "SELECT channel_leaderboard, leaderboard_message_id FROM guild_config WHERE guild_id = $1", guild_id
    )
    if not config or not config["channel_leaderboard"] or not config["leaderboard_message_id"]:
        return

    channel = bot.get_channel(config["channel_leaderboard"])
    if not channel:
        return

    try:
        message = await channel.fetch_message(config["leaderboard_message_id"])
        embed = await build_leaderboard_embed(guild_id, conn)
        await message.edit(embed=embed)
    except Exception as e:
        print(f"Leaderboard embed update failed: {e}")
