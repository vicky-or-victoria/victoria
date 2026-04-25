"""
Background scheduler for V.I.C.T.O.R.I.A. v2
Handles turn resolution, election timing, and embed refresh.
"""
import asyncio
import discord
from datetime import datetime, timezone
from db.connection import get_pool
from utils.turn_engine import resolve_turn
from utils.gazette import post_turn_gazette, post_election_gazette, post_tier_b


async def run_scheduler(bot):
    """Main scheduler loop — checks every 60 seconds."""
    await bot.wait_until_ready()
    print("✅ Scheduler running.")
    while not bot.is_closed():
        try:
            await _check_all_guilds(bot)
        except Exception as e:
            print(f"Scheduler error: {e}")
        await asyncio.sleep(60)


async def _check_all_guilds(bot):
    pool = await get_pool()
    async with pool.acquire() as conn:
        guilds = await conn.fetch(
            "SELECT guild_id, next_turn_at, next_election_at FROM guild_config WHERE channel_menu IS NOT NULL"
        )
        now = datetime.now(timezone.utc)

        for guild in guilds:
            guild_id = guild["guild_id"]

            # Turn resolution
            if guild["next_turn_at"] and guild["next_turn_at"] <= now:
                try:
                    await _resolve_guild_turn(bot, guild_id, conn)
                except Exception as e:
                    print(f"Turn error guild {guild_id}: {e}")

            # Election
            if guild["next_election_at"] and guild["next_election_at"] <= now:
                try:
                    await _resolve_guild_election(bot, guild_id, conn)
                except Exception as e:
                    print(f"Election error guild {guild_id}: {e}")

            # Refresh all embeds
            try:
                await refresh_all_embeds(bot, guild_id, conn)
            except Exception as e:
                print(f"Embed refresh error guild {guild_id}: {e}")


async def _resolve_guild_turn(bot, guild_id: int, conn):
    from datetime import timedelta

    result = await resolve_turn(guild_id, bot=bot)

    if result:
        await post_turn_gazette(bot, guild_id, conn, result)
        await post_tier_b(
            bot, guild_id, conn,
            section="politics",
            template_key="turn_ap_reset",
            character="", user_mention="", content="",
        )

    # Advance next turn
    config = await conn.fetchrow(
        "SELECT turn_hours FROM guild_config WHERE guild_id = $1", guild_id
    )
    turn_hours = config["turn_hours"] if config else 12
    await conn.execute("""
        UPDATE guild_config
        SET last_turn_at = NOW(), next_turn_at = NOW() + ($1 * INTERVAL '1 hour')
        WHERE guild_id = $2
    """, turn_hours, guild_id)

    await refresh_all_embeds(bot, guild_id, conn)


async def _resolve_guild_election(bot, guild_id: int, conn):
    from datetime import timedelta
    from utils.elections import resolve_election
    from utils.empress import issue_new_ambition, lift_crown_rule

    result = await resolve_election(guild_id, conn)
    await post_election_gazette(bot, guild_id, conn, result)
    await lift_crown_rule(guild_id, conn)
    await issue_new_ambition(guild_id, conn)

    config = await conn.fetchrow(
        "SELECT election_days FROM guild_config WHERE guild_id = $1", guild_id
    )
    election_days = config["election_days"] if config else 5
    await conn.execute("""
        UPDATE guild_config
        SET last_election_at = NOW(), next_election_at = NOW() + ($1 * INTERVAL '1 day')
        WHERE guild_id = $2
    """, election_days, guild_id)

    await refresh_all_embeds(bot, guild_id, conn)


async def refresh_all_embeds(bot, guild_id: int, conn):
    """Refresh all live embeds for a guild."""
    from views.menu import update_menu_embed
    from views.cabinet_panel import build_cabinet_embed
    from utils.empress import update_empress_embed
    from utils.maprender import render_map_for_guild
    from utils.gazette import format_vic_date, ordinal

    await update_menu_embed(bot, guild_id, conn)
    await update_empress_embed(bot, guild_id, conn)

    # Cabinet embed
    config = await conn.fetchrow("SELECT * FROM guild_config WHERE guild_id = $1", guild_id)
    if config and config["cabinet_message_id"] and config["channel_cabinet"]:
        channel = bot.get_channel(config["channel_cabinet"])
        if channel:
            try:
                msg = await channel.fetch_message(config["cabinet_message_id"])
                embed = await build_cabinet_embed(guild_id, conn)
                await msg.edit(embed=embed)
            except Exception as e:
                print(f"Cabinet embed update failed: {e}")

    # Map embed
    if config and config["channel_map"]:
        try:
            channel = bot.get_channel(config["channel_map"])
            if channel:
                nation = await conn.fetchrow("SELECT turn_number, hex_count FROM nation_state WHERE guild_id = $1", guild_id)
                turn_number = nation["turn_number"] if nation else 1
                hex_count = nation["hex_count"] if nation else 0
                nation_name = config["nation_name"] or "The Empire"

                try:
                    vic_date = format_vic_date(config["vic_year"], config["vic_month"], config["vic_day"])
                except (KeyError, TypeError):
                    vic_date = "Unknown Date"

                buf = await render_map_for_guild(guild_id, conn)
                file = discord.File(buf, filename="victoria_map.png")

                map_embed = discord.Embed(
                    title=f"🗺️ Imperial Cartographic Survey — {nation_name}",
                    description=(
                        f"*Issued by the Office of the Surveyor-General of His Majesty's Dominions.*\n\n"
                        f"**Turn {ordinal(turn_number)}** · *{vic_date}* · **Territory Held:** {hex_count} hexes\n\n"
                        f"The crimson regions denote lands under the sovereign authority of the Crown. "
                        f"Coloured borders mark the disposition of neighbouring powers — "
                        f"green for allies, amber for neutrals, crimson for those who bear us ill will."
                    ),
                    color=0x4B3010,
                )
                map_embed.set_image(url="attachment://victoria_map.png")
                map_embed.set_footer(
                    text="Printed at the Office of the Surveyor-General · V.I.C.T.O.R.I.A."
                )

                if config["map_message_id"]:
                    try:
                        old_msg = await channel.fetch_message(config["map_message_id"])
                        await old_msg.delete()
                    except Exception:
                        pass

                new_msg = await channel.send(embed=map_embed, file=file)
                await conn.execute(
                    "UPDATE guild_config SET map_message_id = $1 WHERE guild_id = $2",
                    new_msg.id, guild_id
                )
        except Exception as e:
            print(f"Map render error guild {guild_id}: {e}")
