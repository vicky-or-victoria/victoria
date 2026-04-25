"""
Formal Turn Action Panel — AP-gated actions for V.I.C.T.O.R.I.A. v2
"""
import discord
from discord.ui import View, Select, Button
from db.connection import get_pool
from models.actions import ACTIONS, get_available_actions


class ActionMenuView(View):
    def __init__(self, guild_id: int, player_id: int, seat_number: int | None,
                 role_type: str, ap_remaining: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.player_id = player_id
        self.seat_number = seat_number
        self.role_type = role_type
        self.ap_remaining = ap_remaining

        available = get_available_actions(seat_number, role_type)
        options = [
            discord.SelectOption(
                label=action["label"][:100],
                value=key,
                description=f"AP Cost: {action['ap_cost']} · {action['primary_stat'].title()}"[:100],
            )
            for key, action in list(available.items())[:25]
        ]

        select = Select(
            placeholder="Select a formal action to submit…",
            options=options,
            custom_id="formal_action_select",
        )
        select.callback = self.action_selected
        self.add_item(select)

    async def action_selected(self, interaction: discord.Interaction):
        action_key = interaction.data["values"][0]
        action = ACTIONS.get(action_key)
        if not action:
            await interaction.response.send_message("Unknown action.", ephemeral=True)
            return

        if self.ap_remaining < action["ap_cost"]:
            await interaction.response.send_message(
                f"❌ **Insufficient Action Points.**\n"
                f"**{action['label']}** demands **{action['ap_cost']} AP** "
                f"and you command but **{self.ap_remaining} AP** this turn.\n\n"
                f"*Consider using the **🗣️ Political Discourse** for free political actions instead.*",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"📜 {action['label']}",
            description=(
                f"{action['description']}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"**Action Points Required:** {action['ap_cost']}  "
                f"(you have **{self.ap_remaining}** remaining)\n"
                f"**Difficulty:** DC {action['difficulty']}\n"
                f"**Governing Stat:** {action['primary_stat'].title()}\n\n"
                f"*This action is queued and resolves when the turn closes. "
                f"Its outcome will be published in The Imperial Gazette.*"
            ),
            color=0x8B0000,
        )

        # Choose confirm view based on whether target is needed
        needs_target = action_key in (
            "expose_corruption", "gather_intelligence", "call_confidence_vote",
            "call_confidence_vote_opp", "vote_no_confidence", "issue_royal_warrant",
            "arrest_warrant", "manipulate_treasury", "whisper_campaign",
            "deep_intelligence", "bribe_official", "sabotage_legislation",
        )
        needs_nation_target = action_key in (
            "declare_war", "diplomatic_overture", "secret_treaty", "stage_provocation",
        )
        needs_speech = action_key in ("public_speech", "propaganda_campaign")

        if needs_speech:
            view = ConfirmSpeechView(self.guild_id, self.player_id, action_key, action)
        elif needs_target:
            view = ConfirmTargetView(self.guild_id, self.player_id, action_key, action)
        elif needs_nation_target:
            view = ConfirmNationTargetView(self.guild_id, self.player_id, action_key, action)
        else:
            view = ConfirmDirectView(self.guild_id, self.player_id, action_key, action)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @staticmethod
    async def send(interaction: discord.Interaction, conn):
        guild_id = interaction.guild_id
        user_id = interaction.user.id

        player = await conn.fetchrow("""
            SELECT p.id, p.ap_remaining, p.role_type, p.character_name, p.is_silenced,
                   ca.seat_number
            FROM players p
            LEFT JOIN cabinet_assignments ca ON ca.player_id = p.id AND ca.guild_id = p.guild_id
            WHERE p.guild_id = $1 AND p.user_id = $2
        """, guild_id, user_id)

        if not player:
            await interaction.response.send_message(
                "You have not yet entered the arena. "
                "Click **👤 My Character** to create your character first.",
                ephemeral=True
            )
            return

        if player["is_silenced"]:
            await interaction.response.send_message(
                "⚠️ **You have been silenced by Royal Warrant.**\n"
                "You may not submit formal turn actions until your warrant expires.\n\n"
                "*You may still use **🗣️ Political Discourse** for freeform actions.*",
                ephemeral=True
            )
            return

        nation = await conn.fetchrow("SELECT turn_number FROM nation_state WHERE guild_id = $1", guild_id)
        turn_number = nation["turn_number"] if nation else 1

        action_count = await conn.fetchval("""
            SELECT COUNT(*) FROM turn_actions
            WHERE guild_id = $1 AND player_id = $2 AND turn_number = $3
        """, guild_id, player["id"], turn_number)

        ap = player["ap_remaining"]
        seat_number = player["seat_number"]
        role_type = player["role_type"]

        role_labels = {
            "cabinet": f"Cabinet — Seat {seat_number}",
            "parliament": "Member of Parliament",
            "people": "Opposition / The People",
        }
        role_label = role_labels.get(role_type, role_type.title())

        # Unique seat note
        seat_note = ""
        if seat_number:
            seat = await conn.fetchrow("""
                SELECT title FROM cabinet_seats WHERE guild_id = $1 AND seat_number = $2
            """, guild_id, seat_number)
            if seat:
                seat_note = f"\n*As **{seat['title']}**, you have access to unique actions no other minister commands.*"

        embed = discord.Embed(
            title="⚖️ The Formal Dispatch Box",
            description=(
                f"*The dispatch box stands open. The Empire awaits your instruction.*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"**Position:** {role_label}\n"
                f"**Action Points Remaining:** {ap}\n"
                f"**Actions Filed This Turn:** {action_count}\n"
                f"{seat_note}\n\n"
                f"Select an action from the register below to read its full description "
                f"before committing. All formal actions resolve at turn end and are published "
                f"in **The Imperial Gazette**.\n\n"
                + ("⚠️ *You have expended all Action Points for this turn. "
                   "Consider using **🗣️ Political Discourse** for free actions.*"
                   if ap <= 0 else "")
            ),
            color=0x8B0000,
        )
        embed.set_footer(text="Formal actions queue until turn resolution · V.I.C.T.O.R.I.A.")

        view = ActionMenuView(guild_id, player["id"], seat_number, role_type, ap)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ─────────────────────────────────────────
# CONFIRM VIEWS
# ─────────────────────────────────────────

class ConfirmDirectView(View):
    def __init__(self, guild_id, player_id, action_key, action):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.player_id = player_id
        self.action_key = action_key
        self.action = action

    @discord.ui.button(label="✅ Commit to this Action", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        await _submit_action(interaction, self.guild_id, self.player_id, self.action_key, {})

    @discord.ui.button(label="✗ Choose Differently", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(
            content="*Action cancelled. Return to the dispatch box to choose another course.*",
            embed=None, view=None
        )


class ConfirmSpeechView(View):
    def __init__(self, guild_id, player_id, action_key, action):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.player_id = player_id
        self.action_key = action_key
        self.action = action

    @discord.ui.button(label="✅ Draft My Address", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(
            SpeechModal(self.guild_id, self.player_id, self.action_key, self.action)
        )

    @discord.ui.button(label="✗ Choose Differently", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(content="*Cancelled.*", embed=None, view=None)


class ConfirmTargetView(View):
    def __init__(self, guild_id, player_id, action_key, action):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.player_id = player_id
        self.action_key = action_key
        self.action = action

    @discord.ui.button(label="✅ Name My Target", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(
            TargetModal(self.guild_id, self.player_id, self.action_key, self.action)
        )

    @discord.ui.button(label="✗ Choose Differently", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(content="*Cancelled.*", embed=None, view=None)


class ConfirmNationTargetView(View):
    def __init__(self, guild_id, player_id, action_key, action):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.player_id = player_id
        self.action_key = action_key
        self.action = action

    @discord.ui.button(label="✅ Select Target Nation", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(
            NationTargetModal(self.guild_id, self.player_id, self.action_key, self.action)
        )

    @discord.ui.button(label="✗ Choose Differently", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(content="*Cancelled.*", embed=None, view=None)


# ─────────────────────────────────────────
# MODALS
# ─────────────────────────────────────────

class SpeechModal(discord.ui.Modal):
    speech_text = discord.ui.TextInput(
        label="Your Address to the Nation",
        placeholder="Speak your piece to the assembled masses…",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=True,
    )

    def __init__(self, guild_id, player_id, action_key, action):
        super().__init__(title=action["label"][:45])
        self.guild_id = guild_id
        self.player_id = player_id
        self.action_key = action_key

    async def on_submit(self, interaction: discord.Interaction):
        await _submit_action(interaction, self.guild_id, self.player_id, self.action_key,
                             {"speech_text": str(self.speech_text)})


class TargetModal(discord.ui.Modal):
    target_name = discord.ui.TextInput(
        label="Target Character Name",
        placeholder="Enter the precise character name of your quarry…",
        max_length=60,
        required=True,
    )

    def __init__(self, guild_id, player_id, action_key, action):
        super().__init__(title=action["label"][:45])
        self.guild_id = guild_id
        self.player_id = player_id
        self.action_key = action_key

    async def on_submit(self, interaction: discord.Interaction):
        await _submit_action(interaction, self.guild_id, self.player_id, self.action_key,
                             {"target_name": str(self.target_name)})


class NationTargetModal(discord.ui.Modal):
    nation_name = discord.ui.TextInput(
        label="Target Nation Name",
        placeholder="Enter the name of the foreign power…",
        max_length=60,
        required=True,
    )

    def __init__(self, guild_id, player_id, action_key, action):
        super().__init__(title=action["label"][:45])
        self.guild_id = guild_id
        self.player_id = player_id
        self.action_key = action_key

    async def on_submit(self, interaction: discord.Interaction):
        await _submit_action(interaction, self.guild_id, self.player_id, self.action_key,
                             {"target_nation": str(self.nation_name)})


# ─────────────────────────────────────────
# SUBMISSION
# ─────────────────────────────────────────

async def _submit_action(interaction: discord.Interaction, guild_id: int, player_id: int,
                         action_key: str, data: dict):
    action = ACTIONS.get(action_key)
    if not action:
        await interaction.response.send_message("Unknown action.", ephemeral=True)
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        nation = await conn.fetchrow("SELECT turn_number FROM nation_state WHERE guild_id = $1", guild_id)
        turn_number = nation["turn_number"] if nation else 1

        ap = await conn.fetchval("SELECT ap_remaining FROM players WHERE id = $1", player_id)
        if (ap or 0) < action["ap_cost"]:
            await interaction.response.send_message(
                "❌ *Insufficient Action Points to commit to this course.*", ephemeral=True
            )
            return

        await conn.execute("""
            INSERT INTO turn_actions (guild_id, player_id, turn_number, action_key, action_data, ap_cost)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6)
        """, guild_id, player_id, turn_number, action_key,
            str(data).replace("'", '"'), action["ap_cost"])

        await conn.execute("""
            UPDATE players SET ap_remaining = ap_remaining - $1 WHERE id = $2
        """, action["ap_cost"], player_id)

        remaining = (ap or 0) - action["ap_cost"]

    embed = discord.Embed(
        title="✅ Action Duly Recorded in the Register",
        description=(
            f"*The clerk has entered your instruction into the dispatch book for Turn {turn_number}.*\n\n"
            f"**Action Filed:** {action['label']}\n"
            f"**AP Expended:** {action['ap_cost']}\n"
            f"**AP Remaining:** {remaining}\n\n"
            f"*Await the turn resolution. The Gazette shall carry the news of your endeavours.*"
        ),
        color=0x228B22,
    )
    embed.set_footer(text="V.I.C.T.O.R.I.A. · For Crown and Empire")

    try:
        await interaction.response.edit_message(embed=embed, view=None)
    except Exception:
        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception:
            await interaction.followup.send(embed=embed, ephemeral=True)
