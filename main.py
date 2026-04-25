"""
V.I.C.T.O.R.I.A. — Valor, Intrigue, Court, Tyranny, Order, Resistance, Influence, Authority
A Victorian-era political RPG Discord bot.
"""
import asyncio
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from db.connection import get_pool, close_pool
from utils.scheduler import run_scheduler

load_dotenv()

INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.members = True


class Victoria(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!vic_",
            intents=INTENTS,
            help_command=None,
        )

    async def setup_hook(self):
        # Auto-migrate on every startup (safe — all IF NOT EXISTS)
        from db.migrate import migrate
        await migrate()
        print("✅ Database migrations applied.")

        # Load cogs
        await self.load_extension("bot.admin_commands")
        print("✅ Admin commands loaded.")

        # Restore persistent views (menu + act votes) once the bot is ready
        asyncio.create_task(self._restore_persistent_views())

        # Start scheduler
        asyncio.create_task(run_scheduler(self))

        # Sync slash commands
        await self.tree.sync()
        print("✅ Slash commands synced.")

    async def _restore_persistent_views(self):
        await self.wait_until_ready()
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Restore one MainMenuView per guild with the correct guild_id
            try:
                from views.menu import MainMenuView
                guilds = await conn.fetch("SELECT guild_id FROM guild_config")
                for row in guilds:
                    self.add_view(MainMenuView(row["guild_id"]))
                print(f"✅ Restored {len(guilds)} MainMenuView(s).")
            except Exception as e:
                print(f"MainMenuView restore error: {e}")

            # Restore live ActVotingViews
            try:
                from utils.national_acts import ActVotingView, NATIONAL_ACTS
                open_acts = await conn.fetch("""
                    SELECT id, guild_id, act_key FROM national_acts WHERE status = 'proposed'
                """)
                for act in open_acts:
                    act_def = NATIONAL_ACTS.get(act["act_key"], {})
                    requires_cabinet = act_def.get("requires_cabinet", False)
                    self.add_view(ActVotingView(act["guild_id"], act["id"], requires_cabinet))
                print(f"✅ Restored {len(open_acts)} live ActVotingView(s).")
            except Exception as e:
                print(f"ActVotingView restore error: {e}")

    async def on_ready(self):
        print(f"🎩 V.I.C.T.O.R.I.A. is online as {self.user} ({self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="the Empire endure · V.I.C.T.O.R.I.A."
            )
        )
        await get_pool()
        print("✅ Database pool ready.")

    async def close(self):
        await close_pool()
        await super().close()


async def main():
    bot = Victoria()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise ValueError("DISCORD_TOKEN is not set.")
    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
