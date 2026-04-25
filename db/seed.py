"""
Seeds default data for a guild on first setup.
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

DEFAULT_SEATS = [
    (1,  "Prime Minister",                  "Leads the nation. Sets the national agenda and may dissolve Parliament.",                    '{"influence": 2, "legitimacy": 1}'),
    (2,  "Chancellor of the Exchequer",     "Controls the treasury. Funds actions and may manipulate the economy.",                       '{"wealth": 2, "influence": 1}'),
    (3,  "Secretary of State for War",      "Commands the military. Directs campaigns and may declare war.",                              '{"influence": 2, "resolve": 1}'),
    (4,  "Home Secretary",                  "Maintains internal order. Suppresses unrest and may issue arrest warrants.",                 '{"resolve": 2, "legitimacy": 1}'),
    (5,  "Foreign Secretary",               "Manages diplomacy. Forges alliances and negotiates treaties.",                               '{"charisma": 2, "cunning": 1}'),
    (6,  "Lord High Admiral",               "Commands the naval fleet. Controls coastal hexes and sea lanes.",                            '{"influence": 1, "resolve": 1}'),
    (7,  "Secretary for the Colonies",      "Oversees expansion and occupied territories. May formally annex hexes.",                     '{"cunning": 1, "wealth": 1}'),
    (8,  "Lord Privy Seal",                 "Master of intelligence and espionage. Runs spies and uncovers plots.",                       '{"cunning": 2}'),
    (9,  "President of the Board of Trade", "Manages trade routes and economic policy. Boosts treasury income.",                          '{"wealth": 2}'),
    (10, "Postmaster General",              "Controls information, propaganda, and the press. Shapes public opinion.",                    '{"charisma": 2}'),
]

DEFAULT_SOCIETIES = [
    (
        "reformists",
        "The Reform League",
        "A clandestine fellowship of parliamentarians and radicals who believe the Crown's power must be curtailed for the good of the nation.",
        "Reduce Empress displeasure triggers. Pass three Reform Acts to win the faction's agenda.",
    ),
    (
        "imperialists",
        "The Imperial Brotherhood",
        "A secret society of expansionists who believe the Empire's destiny is to paint the map in its colours. War, annexation, and glory.",
        "Expand the nation by 10 hexes. Win three war campaigns to complete the agenda.",
    ),
    (
        "loyalists",
        "The Order of the Crown",
        "A shadowy fellowship dedicated to the Empress above all. They work in darkness to keep Her Majesty upon the throne.",
        "Maintain Royal Favour above 70 for five consecutive turns. Prevent Crown Rule.",
    ),
]


async def seed_guild(guild_id: int, conn):
    # Cabinet seats
    for seat_num, title, desc, stat_bonus in DEFAULT_SEATS:
        await conn.execute("""
            INSERT INTO cabinet_seats (guild_id, seat_number, title, description, stat_bonus)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (guild_id, seat_number) DO NOTHING
        """, guild_id, seat_num, title, desc, stat_bonus)

    await conn.execute("""
        INSERT INTO cabinet_assignments (guild_id, seat_number)
        SELECT $1, generate_series(1, 10)
        ON CONFLICT (guild_id, seat_number) DO NOTHING
    """, guild_id)

    # Secret Societies
    for key, name, desc, agenda in DEFAULT_SOCIETIES:
        await conn.execute("""
            INSERT INTO secret_societies (guild_id, society_key, name, description, agenda)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (guild_id, society_key) DO NOTHING
        """, guild_id, key, name, desc, agenda)

    print(f"✅ Seeded guild {guild_id}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python seed.py <guild_id>")
        sys.exit(1)

    async def main():
        conn = await asyncpg.connect(dsn=os.getenv("DATABASE_URL"))
        try:
            await seed_guild(int(sys.argv[1]), conn)
        finally:
            await conn.close()

    asyncio.run(main())
