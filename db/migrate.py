"""
V.I.C.T.O.R.I.A. — Full database migration v2
All tables use IF NOT EXISTS — safe to run on every startup.
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

MIGRATION_SQL = """
-- ─────────────────────────────────────────
-- GUILD CONFIGURATION
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS guild_config (
    guild_id                BIGINT PRIMARY KEY,
    nation_name             TEXT NOT NULL DEFAULT 'The Empire',
    turn_hours              INT NOT NULL DEFAULT 12,
    election_days           INT NOT NULL DEFAULT 5,
    confidence_threshold    INT NOT NULL DEFAULT 30,
    ap_cabinet_senior       INT NOT NULL DEFAULT 5,
    ap_cabinet_junior       INT NOT NULL DEFAULT 4,
    ap_opposition           INT NOT NULL DEFAULT 3,
    ap_parliament           INT NOT NULL DEFAULT 2,
    ultimate_goal           TEXT NOT NULL DEFAULT 'Achieve Imperial dominance over the known world.',
    -- Channel IDs
    channel_menu            BIGINT,
    channel_map             BIGINT,
    channel_events          BIGINT,
    channel_cabinet         BIGINT,
    channel_leaderboard     BIGINT,
    channel_parliament      BIGINT,
    channel_societies       BIGINT,
    -- Role IDs
    role_admin              BIGINT,
    role_prime_minister     BIGINT,
    role_parliament         BIGINT,
    -- Turn tracking
    last_turn_at            TIMESTAMPTZ,
    next_turn_at            TIMESTAMPTZ,
    last_election_at        TIMESTAMPTZ,
    next_election_at        TIMESTAMPTZ,
    -- Fake Victorian calendar (starts 1878-01-01, advances 7 days per turn)
    vic_year                INT NOT NULL DEFAULT 1878,
    vic_month               INT NOT NULL DEFAULT 1,
    vic_day                 INT NOT NULL DEFAULT 1,
    -- Custom branding
    header_image_url        TEXT,
    -- Message IDs for live embeds
    menu_message_id         BIGINT,
    empress_message_id      BIGINT,
    map_message_id          BIGINT,
    cabinet_message_id      BIGINT,
    leaderboard_message_id  BIGINT,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- CABINET SEATS
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cabinet_seats (
    id              SERIAL PRIMARY KEY,
    guild_id        BIGINT NOT NULL REFERENCES guild_config(guild_id) ON DELETE CASCADE,
    seat_number     INT NOT NULL CHECK (seat_number BETWEEN 1 AND 10),
    title           TEXT NOT NULL,
    description     TEXT NOT NULL,
    stat_bonus      TEXT NOT NULL DEFAULT '{}',
    ap_override     INT,
    UNIQUE (guild_id, seat_number)
);

-- ─────────────────────────────────────────
-- PLAYERS
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS players (
    id              SERIAL PRIMARY KEY,
    guild_id        BIGINT NOT NULL,
    user_id         BIGINT NOT NULL,
    character_name  TEXT NOT NULL,
    -- Core stats (1–10)
    influence       INT NOT NULL DEFAULT 3,
    charisma        INT NOT NULL DEFAULT 3,
    cunning         INT NOT NULL DEFAULT 3,
    resolve         INT NOT NULL DEFAULT 3,
    wealth          INT NOT NULL DEFAULT 3,
    legitimacy      INT NOT NULL DEFAULT 3,
    -- Status
    ap_remaining    INT NOT NULL DEFAULT 3,
    opinion_rating  INT NOT NULL DEFAULT 50,
    loyalty         INT NOT NULL DEFAULT 50,   -- loyalty to the Crown (0-100)
    legacy_points   INT NOT NULL DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    is_silenced     BOOLEAN NOT NULL DEFAULT FALSE,  -- Empress warrant
    silenced_until_turn INT,
    role_type       TEXT NOT NULL DEFAULT 'people',  -- 'cabinet', 'parliament', 'people'
    joined_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (guild_id, user_id)
);

-- ─────────────────────────────────────────
-- CABINET ASSIGNMENTS
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cabinet_assignments (
    id              SERIAL PRIMARY KEY,
    guild_id        BIGINT NOT NULL,
    seat_number     INT NOT NULL,
    player_id       INT REFERENCES players(id) ON DELETE SET NULL,
    assigned_at     TIMESTAMPTZ DEFAULT NOW(),
    turns_held      INT NOT NULL DEFAULT 0,
    UNIQUE (guild_id, seat_number)
);

-- ─────────────────────────────────────────
-- PARLIAMENT MEMBERS
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS parliament_members (
    id          SERIAL PRIMARY KEY,
    guild_id    BIGINT NOT NULL,
    player_id   INT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    joined_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (guild_id, player_id)
);

-- ─────────────────────────────────────────
-- SECRET SOCIETIES
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS secret_societies (
    id              SERIAL PRIMARY KEY,
    guild_id        BIGINT NOT NULL,
    society_key     TEXT NOT NULL,   -- 'reformists', 'imperialists', 'loyalists'
    name            TEXT NOT NULL,
    description     TEXT NOT NULL,
    agenda          TEXT NOT NULL,
    member_count    INT NOT NULL DEFAULT 0,
    agenda_progress INT NOT NULL DEFAULT 0,  -- 0-100
    UNIQUE (guild_id, society_key)
);

CREATE TABLE IF NOT EXISTS society_members (
    id          SERIAL PRIMARY KEY,
    guild_id    BIGINT NOT NULL,
    player_id   INT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    society_key TEXT NOT NULL,
    joined_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (guild_id, player_id)  -- one society per player
);

-- ─────────────────────────────────────────
-- PLAYER DOSSIERS
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dossiers (
    id              SERIAL PRIMARY KEY,
    guild_id        BIGINT NOT NULL,
    player_id       INT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    event_type      TEXT NOT NULL,   -- 'action', 'alliance', 'betrayal', 'vote', 'accusation', 'title'
    description     TEXT NOT NULL,
    turn_number     INT NOT NULL,
    vic_date        TEXT NOT NULL,   -- e.g. "14th November 1878"
    occurred_at     TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- PLAYER TITLES
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS player_titles (
    id          SERIAL PRIMARY KEY,
    guild_id    BIGINT NOT NULL,
    player_id   INT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    title_key   TEXT NOT NULL,
    title_name  TEXT NOT NULL,
    awarded_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (guild_id, player_id, title_key)
);

-- ─────────────────────────────────────────
-- PLAYER ALLIANCES
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alliances (
    id          SERIAL PRIMARY KEY,
    guild_id    BIGINT NOT NULL,
    player_a    INT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    player_b    INT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    status      TEXT NOT NULL DEFAULT 'active',  -- active, broken
    formed_at   TIMESTAMPTZ DEFAULT NOW(),
    broken_at   TIMESTAMPTZ,
    UNIQUE (guild_id, player_a, player_b)
);

-- ─────────────────────────────────────────
-- FREEFORM ACTIONS LOG
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS freeform_actions (
    id              SERIAL PRIMARY KEY,
    guild_id        BIGINT NOT NULL,
    player_id       INT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    action_type     TEXT NOT NULL,   -- 'declaration', 'accusation', 'deal_offer', 'leak', 'whisper', 'pledge', 'protest', 'petition'
    target_id       INT REFERENCES players(id) ON DELETE SET NULL,
    content         TEXT NOT NULL,
    is_public       BOOLEAN NOT NULL DEFAULT TRUE,
    gazette_tier    TEXT NOT NULL DEFAULT 'B',  -- 'A', 'B', 'C'
    turn_number     INT NOT NULL,
    vic_date        TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- GAZETTE ENTRIES
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gazette_entries (
    id              SERIAL PRIMARY KEY,
    guild_id        BIGINT NOT NULL,
    tier            TEXT NOT NULL,     -- 'A', 'B', 'C'
    section         TEXT NOT NULL,     -- 'politics', 'crown', 'war', 'election', 'crisis', 'society'
    headline        TEXT NOT NULL,
    body            TEXT NOT NULL,
    turn_number     INT NOT NULL,
    vic_date        TEXT NOT NULL,
    message_id      BIGINT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- EMPRESS DISPLEASURE
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS empress (
    guild_id            BIGINT PRIMARY KEY REFERENCES guild_config(guild_id) ON DELETE CASCADE,
    name                TEXT NOT NULL DEFAULT 'Empress Victoria I',
    portrait_url        TEXT,
    current_ambition    TEXT NOT NULL DEFAULT 'Expand the territorial holdings of the Empire.',
    ambition_type       TEXT NOT NULL DEFAULT 'expansion',
    royal_favour        INT NOT NULL DEFAULT 70,
    displeasure         INT NOT NULL DEFAULT 0,   -- 0-100 NEW: drives intervention escalation
    stage               INT NOT NULL DEFAULT 0,   -- 0-5 escalation stage
    is_crown_rule       BOOLEAN NOT NULL DEFAULT FALSE,
    crown_rule_since    TIMESTAMPTZ,
    ambition_set_at     TIMESTAMPTZ DEFAULT NOW(),
    last_decree         TEXT,
    decree_at           TIMESTAMPTZ,
    last_intervention   TEXT,
    intervention_at     TIMESTAMPTZ
);

-- ─────────────────────────────────────────
-- TURN ACTIONS (formal AP-gated)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS turn_actions (
    id              SERIAL PRIMARY KEY,
    guild_id        BIGINT NOT NULL,
    player_id       INT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    turn_number     INT NOT NULL,
    action_key      TEXT NOT NULL,
    action_data     JSONB DEFAULT '{}',
    ap_cost         INT NOT NULL,
    resolved        BOOLEAN NOT NULL DEFAULT FALSE,
    outcome         TEXT,
    roll_result     INT,
    submitted_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- TURN HISTORY
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS turn_history (
    id              SERIAL PRIMARY KEY,
    guild_id        BIGINT NOT NULL,
    turn_number     INT NOT NULL,
    narrative       TEXT NOT NULL,
    raw_events      JSONB DEFAULT '[]',
    vic_date        TEXT NOT NULL DEFAULT '',
    occurred_at     TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- CONFIDENCE VOTES
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS confidence_votes (
    id                  SERIAL PRIMARY KEY,
    guild_id            BIGINT NOT NULL,
    seat_number         INT NOT NULL,
    triggered_by        INT REFERENCES players(id) ON DELETE SET NULL,
    trigger_reason      TEXT NOT NULL DEFAULT 'low_opinion',
    votes_confidence    INT NOT NULL DEFAULT 0,
    votes_no_confidence INT NOT NULL DEFAULT 0,
    voters              BIGINT[] DEFAULT '{}',
    resolved            BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    resolved_at         TIMESTAMPTZ
);

-- ─────────────────────────────────────────
-- NATION STATE
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS nation_state (
    guild_id        BIGINT PRIMARY KEY REFERENCES guild_config(guild_id) ON DELETE CASCADE,
    stability       INT NOT NULL DEFAULT 70,
    treasury        INT NOT NULL DEFAULT 1000,
    military        INT NOT NULL DEFAULT 5,
    public_unrest   INT NOT NULL DEFAULT 20,
    hex_count       INT NOT NULL DEFAULT 4,
    at_war_with     TEXT[] DEFAULT '{}',
    turn_number     INT NOT NULL DEFAULT 1
);

-- ─────────────────────────────────────────
-- HEX MAP
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS hex_map (
    id              SERIAL PRIMARY KEY,
    guild_id        BIGINT NOT NULL,
    q               INT NOT NULL,
    r               INT NOT NULL,
    terrain         TEXT NOT NULL DEFAULT 'plains',
    controlled_by   TEXT,
    is_player_nation BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (guild_id, q, r)
);

-- ─────────────────────────────────────────
-- NPC NATIONS
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS npc_nations (
    id              SERIAL PRIMARY KEY,
    guild_id        BIGINT NOT NULL,
    name            TEXT NOT NULL,
    government_type TEXT NOT NULL DEFAULT 'monarchy',
    military        INT NOT NULL DEFAULT 5,
    economy         INT NOT NULL DEFAULT 5,
    stability       INT NOT NULL DEFAULT 5,
    disposition     TEXT NOT NULL DEFAULT 'neutral',
    capital_q       INT,
    capital_r       INT,
    is_defeated     BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (guild_id, name)
);

-- ─────────────────────────────────────────
-- WAR CAMPAIGNS
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS war_campaigns (
    id                  SERIAL PRIMARY KEY,
    guild_id            BIGINT NOT NULL,
    target_nation       TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'active',
    started_turn        INT NOT NULL,
    ended_turn          INT,
    attacker_strength   INT NOT NULL DEFAULT 0,
    defender_strength   INT NOT NULL DEFAULT 0,
    hexes_contested     TEXT[] DEFAULT '{}',
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- NATIONAL ACTS
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS national_acts (
    id                  SERIAL PRIMARY KEY,
    guild_id            BIGINT NOT NULL,
    proposed_by         INT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    act_key             TEXT NOT NULL,
    act_title           TEXT NOT NULL,
    act_description     TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'proposed',
    votes_for           INT NOT NULL DEFAULT 0,
    votes_against       INT NOT NULL DEFAULT 0,
    voters              BIGINT[] DEFAULT '{}',
    proposed_turn       INT NOT NULL,
    expires_turn        INT NOT NULL DEFAULT 0,
    resolved_turn       INT,
    effects_applied     JSONB DEFAULT '{}',
    channel_message_id  BIGINT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS national_act_votes (
    id          SERIAL PRIMARY KEY,
    act_id      INT NOT NULL REFERENCES national_acts(id) ON DELETE CASCADE,
    guild_id    BIGINT NOT NULL,
    user_id     BIGINT NOT NULL,
    is_aye      BOOLEAN NOT NULL,
    voted_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (act_id, user_id)
);

-- ─────────────────────────────────────────
-- LEADERBOARD
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS leaderboard (
    id          SERIAL PRIMARY KEY,
    guild_id    BIGINT NOT NULL,
    player_id   INT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    seat_number INT NOT NULL,
    seat_title  TEXT NOT NULL,
    turns_served INT NOT NULL DEFAULT 0,
    started_at  TIMESTAMPTZ NOT NULL,
    ended_at    TIMESTAMPTZ
);

-- ─────────────────────────────────────────
-- RANDOM EVENTS LOG
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS national_events (
    id              SERIAL PRIMARY KEY,
    guild_id        BIGINT NOT NULL,
    turn_number     INT NOT NULL,
    event_key       TEXT NOT NULL,
    event_title     TEXT NOT NULL,
    event_description TEXT NOT NULL,
    severity        TEXT NOT NULL DEFAULT 'minor',
    effects         JSONB DEFAULT '{}',
    resolved        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- INDEXES
-- ─────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_players_guild ON players(guild_id);
CREATE INDEX IF NOT EXISTS idx_turn_actions_guild_turn ON turn_actions(guild_id, turn_number);
CREATE INDEX IF NOT EXISTS idx_hex_map_guild ON hex_map(guild_id);
CREATE INDEX IF NOT EXISTS idx_turn_history_guild ON turn_history(guild_id, turn_number DESC);
CREATE INDEX IF NOT EXISTS idx_cabinet_guild ON cabinet_assignments(guild_id);
CREATE INDEX IF NOT EXISTS idx_leaderboard_guild ON leaderboard(guild_id, turns_served DESC);
CREATE INDEX IF NOT EXISTS idx_gazette_guild ON gazette_entries(guild_id, turn_number DESC);
CREATE INDEX IF NOT EXISTS idx_dossiers_player ON dossiers(guild_id, player_id);
CREATE INDEX IF NOT EXISTS idx_freeform_guild ON freeform_actions(guild_id, turn_number);
CREATE INDEX IF NOT EXISTS idx_alliances_guild ON alliances(guild_id);
CREATE INDEX IF NOT EXISTS idx_society_members ON society_members(guild_id, society_key);
"""


async def migrate():
    conn = await asyncpg.connect(dsn=os.getenv("DATABASE_URL"))
    try:
        await conn.execute(MIGRATION_SQL)
        print("✅ Migration complete.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())
