"""
Action definitions for V.I.C.T.O.R.I.A. v2
Three tiers: Cabinet, Parliament, The People
Each cabinet seat has unique actions nobody else can take.
"""

# ─────────────────────────────────────────
# FREEFORM ACTIONS (anytime, no AP, Tier B/C gazette)
# ─────────────────────────────────────────
FREEFORM_ACTIONS = {
    "declaration": {
        "label": "📢 Make a Public Declaration",
        "description": "Issue a statement to the nation. Posted to the Gazette for all to see.",
        "available_to": "all",
        "gazette_tier": "B",
        "gazette_section": "society",
    },
    "accusation": {
        "label": "⚖️ Publicly Accuse a Player",
        "description": (
            "Level a formal accusation against another player. They have until turn end to respond. "
            "If you have intelligence evidence, it lands hard. If you bluffed and they prove it, you take the hit."
        ),
        "available_to": "all",
        "gazette_tier": "B",
        "gazette_section": "politics",
        "requires_target": True,
    },
    "propose_deal": {
        "label": "🤝 Propose a Private Deal",
        "description": (
            "Send a private political offer to another player. "
            "If accepted, you become known allies (public). If rejected, that too becomes public."
        ),
        "available_to": "all",
        "gazette_tier": "C",
        "gazette_section": "society",
        "requires_target": True,
    },
    "pledge_vote": {
        "label": "🗳️ Pledge Your Vote",
        "description": "Publicly or privately commit your parliamentary vote on pending legislation.",
        "available_to": "parliament",
        "gazette_tier": "B",
        "gazette_section": "politics",
    },
    "leak_intelligence": {
        "label": "🔍 Leak Intelligence",
        "description": (
            "If you gathered intelligence on a player this or a prior turn, "
            "release it publicly to the Gazette or sell it privately to another player."
        ),
        "available_to": "all",
        "gazette_tier": "B",
        "gazette_section": "societies",
    },
    "whisper_campaign": {
        "label": "🗣️ Whisper Campaign",
        "description": (
            "Privately contact up to 3 players to sow doubt about a target. "
            "Slow, cumulative opinion damage. Silent — no Gazette post."
        ),
        "available_to": "all",
        "gazette_tier": "C",
        "gazette_section": "society",
        "requires_target": True,
    },
    "organise_protest": {
        "label": "✊ Organise a Protest",
        "description": (
            "Lead a public demonstration in the capital. "
            "Raises public unrest, pressures the ministry, posted to the Gazette."
        ),
        "available_to": "people",
        "gazette_tier": "B",
        "gazette_section": "society",
    },
    "sign_petition": {
        "label": "📜 Start a Petition",
        "description": (
            "Initiate a petition requiring 5+ signatories. "
            "Once threshold is met it is formally submitted to Parliament."
        ),
        "available_to": "people",
        "gazette_tier": "B",
        "gazette_section": "politics",
    },
    "table_bill": {
        "label": "📋 Table a Bill",
        "description": "Formally propose a bill before Parliament for a vote. Parliament members vote on it.",
        "available_to": "parliament",
        "gazette_tier": "B",
        "gazette_section": "politics",
    },
    "call_inquiry": {
        "label": "🔎 Call for Inquiry",
        "description": "Force a Cabinet minister to publicly answer questions before Parliament.",
        "available_to": "parliament",
        "gazette_tier": "B",
        "gazette_section": "politics",
        "requires_target": True,
    },
    "loyalty_pledge": {
        "label": "👑 Pledge Loyalty to the Crown",
        "description": "Publicly declare your loyalty to the Empress. Raises your Loyalty score and Royal Favour slightly.",
        "available_to": "all",
        "gazette_tier": "B",
        "gazette_section": "crown",
    },
}

# ─────────────────────────────────────────
# FORMAL TURN ACTIONS (AP-gated, resolve at turn end)
# ─────────────────────────────────────────
ACTIONS = {

    # ═══════════════════════════════════════
    # SHARED (all roles)
    # ═══════════════════════════════════════
    "public_speech": {
        "label": "Deliver a Public Address",
        "description": (
            "Mount the podium and address the assembled masses. "
            "A rousing oration lifts your standing in the public eye.\n"
            "*Raises your Opinion Rating by 5–15 points. Uses Charisma.*"
        ),
        "ap_cost": 1,
        "primary_stat": "charisma",
        "difficulty": 12,
        "available_to": "both",
        "effects": {"opinion_rating": "+5 to +15"},
    },
    "gather_intelligence": {
        "label": "Gather Intelligence",
        "description": (
            "Set your agents upon a rival's household. What secrets might they unearth?\n"
            "*Reveals a target player's pending actions. Enables future leak or accusation evidence. Uses Cunning.*"
        ),
        "ap_cost": 2,
        "primary_stat": "cunning",
        "difficulty": 14,
        "available_to": "both",
        "effects": {"reveals_actions": True},
    },
    "forge_alliance": {
        "label": "Forge a Personal Alliance",
        "description": (
            "Extend the hand of private fellowship to another player. Share intelligence.\n"
            "*Forms a personal alliance. Uses Charisma.*"
        ),
        "ap_cost": 1,
        "primary_stat": "charisma",
        "difficulty": 10,
        "available_to": "both",
        "effects": {"alliance": True},
    },
    "bribe_official": {
        "label": "Bribe an Official",
        "description": (
            "Press a sovereign into the palm of a minor functionary.\n"
            "*Raises your Opinion Rating modestly, drains 50–100 from the Treasury. Uses Wealth.*"
        ),
        "ap_cost": 2,
        "primary_stat": "wealth",
        "difficulty": 13,
        "available_to": "both",
        "effects": {"opinion_rating": "+3 to +8", "treasury": "-50 to -100"},
    },

    # ═══════════════════════════════════════
    # CABINET — SHARED CABINET ACTIONS
    # ═══════════════════════════════════════
    "pass_legislation": {
        "label": "Pass Legislation",
        "description": (
            "Shepherd a bill through Parliament by force of will and persuasion.\n"
            "*Raises National Stability 5–15 and your Opinion Rating 3–10. Uses Influence.*"
        ),
        "ap_cost": 3,
        "primary_stat": "influence",
        "difficulty": 15,
        "available_to": "cabinet",
        "effects": {"stability": "+5 to +15", "opinion_rating": "+3 to +10"},
    },
    "call_confidence_vote": {
        "label": "Call Confidence Vote",
        "description": (
            "Challenge a Cabinet member's seat with a formal confidence vote.\n"
            "*Triggers a confidence vote against a target minister. Uses Influence.*"
        ),
        "ap_cost": 3,
        "primary_stat": "influence",
        "difficulty": 15,
        "available_to": "cabinet",
        "effects": {"confidence_vote": "triggers"},
    },

    # ═══════════════════════════════════════
    # SEAT-UNIQUE CABINET ACTIONS
    # ═══════════════════════════════════════

    # Seat 1 — Prime Minister
    "dissolve_parliament": {
        "label": "Dissolve Parliament",
        "description": (
            "Exercise the supreme executive prerogative — call a snap election.\n"
            "*Triggers an immediate election. Costs significant AP and stability. PM only.*"
        ),
        "ap_cost": 5,
        "primary_stat": "legitimacy",
        "difficulty": 16,
        "available_to": [1],
        "effects": {"snap_election": True, "stability": "-10"},
    },
    "issue_royal_warrant": {
        "label": "Issue Royal Warrant",
        "description": (
            "Legally silence a player for one turn — they may not submit turn actions.\n"
            "*Removes target's turn action next turn. Requires PM authority. Uses Influence.*"
        ),
        "ap_cost": 4,
        "primary_stat": "influence",
        "difficulty": 16,
        "available_to": [1],
        "effects": {"silence_target": True},
    },
    "annex_hex": {
        "label": "Annex Territory",
        "description": (
            "Formally raise the Imperial standard over a hex won through war.\n"
            "*Expands the nation by 1 hex, reduces Stability by 5. PM & Colonies Secretary only.*"
        ),
        "ap_cost": 3,
        "primary_stat": "legitimacy",
        "difficulty": 14,
        "available_to": [1, 7],
        "effects": {"hex_count": "+1", "stability": "-5"},
    },

    # Seat 2 — Chancellor
    "economic_decree": {
        "label": "Issue Economic Decree",
        "description": (
            "Enact a sweeping fiscal directive from the Treasury.\n"
            "*Adds 100–200 to the Treasury. Chancellor & Trade President only. Uses Wealth.*"
        ),
        "ap_cost": 2,
        "primary_stat": "wealth",
        "difficulty": 13,
        "available_to": [2, 9],
        "effects": {"treasury": "+100 to +200"},
    },
    "manipulate_treasury": {
        "label": "Manipulate the Treasury",
        "description": (
            "Secretly redirect Treasury funds, hurting a rival's wealth stat.\n"
            "*Damages a target's Wealth. Chancellor only. Uses Cunning.*"
        ),
        "ap_cost": 3,
        "primary_stat": "cunning",
        "difficulty": 15,
        "available_to": [2],
        "effects": {"target_wealth": "-2"},
    },

    # Seat 3 — War Secretary
    "declare_war": {
        "label": "Declare War",
        "description": (
            "Lay before Parliament the case for armed conflict.\n"
            "*Starts a war campaign, raises Unrest +10. PM & War Secretary only. Uses Influence.*"
        ),
        "ap_cost": 4,
        "primary_stat": "influence",
        "difficulty": 16,
        "available_to": [1, 3],
        "effects": {"war_campaign": "starts", "unrest": "+10"},
    },
    "fund_campaign": {
        "label": "Fund Military Campaign",
        "description": (
            "Direct Treasury funds to the front.\n"
            "*Raises active war campaign strength 10–25. War Secretary & Admiral only. Uses Wealth.*"
        ),
        "ap_cost": 2,
        "primary_stat": "wealth",
        "difficulty": 12,
        "available_to": [3, 6],
        "effects": {"campaign_strength": "+10 to +25"},
    },
    "secret_armistice": {
        "label": "Negotiate Secret Armistice",
        "description": (
            "End a war quietly, without a parliamentary vote.\n"
            "*Ends active war campaign. War Secretary only. Uses Charisma.*"
        ),
        "ap_cost": 3,
        "primary_stat": "charisma",
        "difficulty": 15,
        "available_to": [3],
        "effects": {"end_war": True},
    },

    # Seat 4 — Home Secretary
    "suppress_unrest": {
        "label": "Suppress Civil Unrest",
        "description": (
            "Deploy the constabulary to restore order in restless districts.\n"
            "*Reduces Public Unrest 10–20. Home Secretary only. Uses Resolve.*"
        ),
        "ap_cost": 2,
        "primary_stat": "resolve",
        "difficulty": 13,
        "available_to": [4],
        "effects": {"unrest": "-10 to -20"},
    },
    "arrest_warrant": {
        "label": "Issue Arrest Warrant",
        "description": (
            "Have a player briefly detained, removing their next turn action.\n"
            "*Silences target for 1 turn. Home Secretary only. Uses Legitimacy.*"
        ),
        "ap_cost": 3,
        "primary_stat": "legitimacy",
        "difficulty": 15,
        "available_to": [4],
        "effects": {"silence_target": True},
    },

    # Seat 5 — Foreign Secretary
    "diplomatic_overture": {
        "label": "Diplomatic Overture",
        "description": (
            "Dispatch an envoy bearing olive branches to a foreign court.\n"
            "*Improves an NPC nation's disposition by one step. Foreign Secretary only. Uses Charisma.*"
        ),
        "ap_cost": 2,
        "primary_stat": "charisma",
        "difficulty": 13,
        "available_to": [5],
        "effects": {"npc_disposition": "hostile→neutral or neutral→friendly"},
    },
    "secret_treaty": {
        "label": "Negotiate a Secret Treaty",
        "description": (
            "Form a hidden alliance with an NPC nation — unknown to Parliament.\n"
            "*Creates secret NPC alliance. Foreign Secretary only. Uses Cunning.*"
        ),
        "ap_cost": 3,
        "primary_stat": "cunning",
        "difficulty": 15,
        "available_to": [5],
        "effects": {"secret_alliance": True},
    },

    # Seat 7 — Colonies Secretary
    "stage_provocation": {
        "label": "Stage a Border Provocation",
        "description": (
            "Manufacture an incident on the border to justify military action.\n"
            "*Lowers NPC disposition to hostile, creates a casus belli. Colonies Secretary only. Uses Cunning.*"
        ),
        "ap_cost": 3,
        "primary_stat": "cunning",
        "difficulty": 14,
        "available_to": [7],
        "effects": {"npc_disposition": "→hostile", "casus_belli": True},
    },

    # Seat 8 — Lord Privy Seal
    "deep_intelligence": {
        "label": "Deep Intelligence Operation",
        "description": (
            "Run a full intelligence operation against a target — reveal stats AND pending actions.\n"
            "*Full dossier on target. Lord Privy Seal only. Uses Cunning.*"
        ),
        "ap_cost": 3,
        "primary_stat": "cunning",
        "difficulty": 14,
        "available_to": [8],
        "effects": {"reveals_stats": True, "reveals_actions": True},
    },
    "plant_spy": {
        "label": "Plant a Permanent Spy",
        "description": (
            "Embed an agent in an NPC nation's court for ongoing intelligence.\n"
            "*Permanent intel on NPC nation. Lord Privy Seal only. Uses Cunning.*"
        ),
        "ap_cost": 3,
        "primary_stat": "cunning",
        "difficulty": 15,
        "available_to": [8],
        "effects": {"npc_spy": True},
    },

    # Seat 10 — Postmaster General
    "propaganda_campaign": {
        "label": "Launch Propaganda Campaign",
        "description": (
            "Flood the broadsheets with favourable copy for all Cabinet members.\n"
            "*Raises all Cabinet members' Opinion Ratings 3–8. Postmaster General only. Uses Charisma.*"
        ),
        "ap_cost": 2,
        "primary_stat": "charisma",
        "difficulty": 13,
        "available_to": [10],
        "effects": {"all_cabinet_opinion": "+3 to +8"},
    },
    "suppress_gazette": {
        "label": "Suppress a Gazette Story",
        "description": (
            "Use your authority over the press to bury a damaging story.\n"
            "*Removes one negative gazette entry. Postmaster General only. Uses Influence.*"
        ),
        "ap_cost": 2,
        "primary_stat": "influence",
        "difficulty": 13,
        "available_to": [10],
        "effects": {"suppress_story": True},
    },

    # ═══════════════════════════════════════
    # PARLIAMENT ACTIONS
    # ═══════════════════════════════════════
    "vote_no_confidence": {
        "label": "Move Vote of No Confidence",
        "description": (
            "Lead a parliamentary motion to oust a minister with low approval.\n"
            "*Triggers a confidence vote from Parliament. Uses Influence.*"
        ),
        "ap_cost": 2,
        "primary_stat": "influence",
        "difficulty": 15,
        "available_to": "parliament",
        "effects": {"confidence_vote": "triggers"},
    },
    "campaign_for_election": {
        "label": "Campaign for Office",
        "description": (
            "Take your message to the hustings ahead of the next election.\n"
            "*Raises Opinion Rating 5–10 and Legitimacy 1–2. Uses Charisma.*"
        ),
        "ap_cost": 2,
        "primary_stat": "charisma",
        "difficulty": 12,
        "available_to": "parliament",
        "effects": {"legitimacy": "+1 to +2", "opinion_rating": "+5 to +10"},
    },

    # ═══════════════════════════════════════
    # OPPOSITION / PEOPLE ACTIONS
    # ═══════════════════════════════════════
    "expose_corruption": {
        "label": "Expose Corruption",
        "description": (
            "Publish a scandal. Damage a Cabinet member's opinion rating.\n"
            "*Reduces a target Cabinet member's Opinion Rating 10–25. Uses Cunning.*"
        ),
        "ap_cost": 2,
        "primary_stat": "cunning",
        "difficulty": 14,
        "available_to": "opposition",
        "effects": {"target_opinion": "-10 to -25"},
    },
    "foment_unrest": {
        "label": "Foment Civil Unrest",
        "description": (
            "Stir the simmering grievances of the working classes.\n"
            "*Raises Public Unrest 10–20 and lowers Stability by 5. Uses Charisma.*"
        ),
        "ap_cost": 2,
        "primary_stat": "charisma",
        "difficulty": 13,
        "available_to": "opposition",
        "effects": {"unrest": "+10 to +20", "stability": "-5"},
    },
    "sabotage_legislation": {
        "label": "Sabotage Legislation",
        "description": (
            "Work through back channels to bury a minister's bill.\n"
            "*Counters a pending Pass Legislation action. Uses Cunning.*"
        ),
        "ap_cost": 2,
        "primary_stat": "cunning",
        "difficulty": 15,
        "available_to": "opposition",
        "effects": {"counter_pass_legislation": True},
    },
    "undermine_war_effort": {
        "label": "Undermine War Effort",
        "description": (
            "Spread anti-war sentiment through pamphlets and public meetings.\n"
            "*Reduces active campaign strength 5–15 and raises Unrest by 5. Uses Cunning.*"
        ),
        "ap_cost": 2,
        "primary_stat": "cunning",
        "difficulty": 14,
        "available_to": "opposition",
        "effects": {"campaign_strength": "-5 to -15", "unrest": "+5"},
    },
    "riot": {
        "label": "Incite a Riot",
        "description": (
            "Push public anger to the breaking point. Extreme action — costly to your reputation.\n"
            "*Raises Unrest +25, Stability -15, your Opinion Rating -10. Forces a crisis event. Uses Charisma.*"
        ),
        "ap_cost": 3,
        "primary_stat": "charisma",
        "difficulty": 13,
        "available_to": "people",
        "effects": {"unrest": "+25", "stability": "-15", "opinion_rating": "-10", "crisis": True},
    },
    "call_confidence_vote_opp": {
        "label": "Demand Confidence Vote",
        "description": (
            "Lead a public campaign to oust a minister with shamefully low approval.\n"
            "*Triggers a confidence vote from the opposition benches. Uses Influence.*"
        ),
        "ap_cost": 3,
        "primary_stat": "influence",
        "difficulty": 16,
        "available_to": "opposition",
        "effects": {"confidence_vote": "triggers"},
    },
}


def get_available_actions(seat_number: int | None, role_type: str = "people") -> dict:
    """
    Returns formal turn actions available to a player.
    seat_number: None = not in cabinet
    role_type: 'cabinet', 'parliament', 'people'
    """
    available = {}
    for key, action in ACTIONS.items():
        avail = action["available_to"]
        if avail == "both":
            available[key] = action
        elif avail == "cabinet" and role_type == "cabinet":
            available[key] = action
        elif avail == "parliament" and role_type in ("parliament", "cabinet"):
            available[key] = action
        elif avail == "opposition" and role_type in ("opposition", "people", "parliament"):
            available[key] = action
        elif avail == "people":
            available[key] = action
        elif isinstance(avail, list) and seat_number in avail:
            available[key] = action
    return available


def get_available_freeform(role_type: str = "people") -> dict:
    """Returns freeform actions available to a player by role."""
    available = {}
    for key, action in FREEFORM_ACTIONS.items():
        avail = action["available_to"]
        if avail == "all":
            available[key] = action
        elif avail == "parliament" and role_type in ("parliament", "cabinet"):
            available[key] = action
        elif avail == "people" and role_type in ("people", "parliament"):
            available[key] = action
    return available
