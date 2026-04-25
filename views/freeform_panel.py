"""
Freeform Actions — anytime political actions for V.I.C.T.O.R.I.A. v2
No AP cost. Instant gazette posts (Tier B or C).
"""
import discord
from discord.ui import View, Select, Button
from db.connection import get_pool
from models.actions import FREEFORM_ACTIONS, get_available_freeform


class FreeformMenuView(View):
    def __init__(self, guild_id: int, player_id: int, role_type: str):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.player_id = player_id
        self.role_type = role_type

        available = get_available_freeform(role_type)
        options = [
            discord.SelectOption(
                label=action["label"][:100],
                value=key,
                description=action["description"][:100],
            )
            for key, action in list(available.items())[:25]
        ]

        select = Select(
            placeholder="Choose a political action…",
            options=options,
            custom_id="freeform_select",
        )
        select.callback = self.action_selected
        self.add_item(select)

    async def action_selected(self, interaction: discord.Interaction):
        action_key = interaction.data["values"][0]
        action = FREEFORM_ACTIONS.get(action_key)
        if not action:
            await interaction.response.send_message("Unknown action.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"{action['label']}",
            description=(
                f"{action['description']}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"*This action is free and may be taken at any time. "
                f"{'It will be posted to the Imperial Gazette.' if action['gazette_tier'] == 'B' else 'It will be recorded privately.'}"
                f"*\n\nDo you wish to proceed?"
            ),
            color=0x8B0000,
        )

        requires_target = action.get("requires_target", False)

        if action_key == "declaration":
            await interaction.response.send_modal(
                FreeformSpeechModal(self.guild_id, self.player_id, action_key, action)
            )
        elif action_key == "accusation":
            await interaction.response.send_modal(
                FreeformTargetModal(self.guild_id, self.player_id, action_key, action,
                                    label="Your Accusation", placeholder="State the charge you lay against them…")
            )
        elif action_key == "propose_deal":
            await interaction.response.send_modal(
                FreeformTargetModal(self.guild_id, self.player_id, action_key, action,
                                    label="Your Proposal", placeholder="State the terms of your offer…")
            )
        elif action_key == "pledge_vote":
            await interaction.response.send_modal(
                FreeformSpeechModal(self.guild_id, self.player_id, action_key, action,
                                    label="Bill Name & Your Pledge", placeholder="State the bill and how you will vote…")
            )
        elif action_key == "organise_protest":
            await interaction.response.send_modal(
                FreeformSpeechModal(self.guild_id, self.player_id, action_key, action,
                                    label="Protest Slogan / Grievance", placeholder="What does the crowd demand?")
            )
        elif action_key == "sign_petition":
            await interaction.response.send_modal(
                FreeformSpeechModal(self.guild_id, self.player_id, action_key, action,
                                    label="Petition Demand", placeholder="What does the petition call for?")
            )
        elif action_key == "whisper_campaign":
            await interaction.response.send_modal(
                FreeformTargetModal(self.guild_id, self.player_id, action_key, action,
                                    label="Your Whisper", placeholder="What rumour do you spread about this person?")
            )
        elif action_key == "table_bill":
            await interaction.response.send_modal(
                FreeformSpeechModal(self.guild_id, self.player_id, action_key, action,
                                    label="Bill Title", placeholder="e.g. The Reform Act of 1879…")
            )
        elif action_key == "call_inquiry":
            await interaction.response.send_modal(
                FreeformTargetModal(self.guild_id, self.player_id, action_key, action,
                                    label="Question for the Minister", placeholder="What must they answer?")
            )
        elif action_key == "loyalty_pledge":
            await _submit_freeform(interaction, self.guild_id, self.player_id, action_key, action,
                                   content="hereby pledges their loyalty to Empress Victoria I and the Crown.", target_id=None)
        elif action_key == "leak_intelligence":
            await interaction.response.send_modal(
                FreeformSpeechModal(self.guild_id, self.player_id, action_key, action,
                                    label="Intelligence to Leak", placeholder="What intelligence have you uncovered?")
            )
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @staticmethod
    async def send(interaction: discord.Interaction, conn):
        guild_id = interaction.guild_id
        player = await conn.fetchrow("""
            SELECT id, role_type, character_name FROM players
            WHERE guild_id = $1 AND user_id = $2
        """, guild_id, interaction.user.id)

        if not player:
            await interaction.response.send_message(
                "You have not yet entered the arena. Use **👤 My Character** to create your character first.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🗣️ Political Discourse — Freeform Actions",
            description=(
                "*Beyond the formal dispatch box, the game of politics is played in corridors, "
                "salons, and the columns of the broadsheets.*\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "These actions cost no Action Points and may be taken **at any time**, "
                "without waiting for the turn to resolve.\n\n"
                "Significant actions are published in **The Imperial Gazette**. "
                "Private actions are delivered directly to their targets.\n\n"
                "*Choose your course of action below.*"
            ),
            color=0x4B3010,
        )
        embed.set_footer(text="V.I.C.T.O.R.I.A. · The political game never sleeps")

        view = FreeformMenuView(guild_id, player["id"], player["role_type"])
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ─────────────────────────────────────────
# MODALS
# ─────────────────────────────────────────

class FreeformSpeechModal(discord.ui.Modal):
    def __init__(self, guild_id: int, player_id: int, action_key: str, action: dict,
                 label: str = "Your Statement", placeholder: str = "Speak your piece…"):
        super().__init__(title=action["label"][:45])
        self.guild_id = guild_id
        self.player_id = player_id
        self.action_key = action_key
        self.action = action

        self.content_field = discord.ui.TextInput(
            label=label,
            placeholder=placeholder,
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=True,
        )
        self.add_item(self.content_field)

    async def on_submit(self, interaction: discord.Interaction):
        await _submit_freeform(
            interaction, self.guild_id, self.player_id,
            self.action_key, self.action,
            content=str(self.content_field),
            target_id=None,
        )


class FreeformTargetModal(discord.ui.Modal):
    def __init__(self, guild_id: int, player_id: int, action_key: str, action: dict,
                 label: str = "Your Message", placeholder: str = ""):
        super().__init__(title=action["label"][:45])
        self.guild_id = guild_id
        self.player_id = player_id
        self.action_key = action_key
        self.action = action

        self.target_field = discord.ui.TextInput(
            label="Target Character Name",
            placeholder="Enter the character name of your target…",
            max_length=50,
            required=True,
        )
        self.content_field = discord.ui.TextInput(
            label=label,
            placeholder=placeholder,
            style=discord.TextStyle.paragraph,
            max_length=400,
            required=True,
        )
        self.add_item(self.target_field)
        self.add_item(self.content_field)

    async def on_submit(self, interaction: discord.Interaction):
        pool = await get_pool()
        async with pool.acquire() as conn:
            target = await conn.fetchrow("""
                SELECT id, user_id, character_name FROM players
                WHERE guild_id = $1 AND character_name ILIKE $2
            """, self.guild_id, f"%{str(self.target_field)}%")

        await _submit_freeform(
            interaction, self.guild_id, self.player_id,
            self.action_key, self.action,
            content=str(self.content_field),
            target_id=target["id"] if target else None,
            target_user_id=target["user_id"] if target else None,
            target_name=target["character_name"] if target else str(self.target_field),
        )


# ─────────────────────────────────────────
# SUBMISSION
# ─────────────────────────────────────────

async def _submit_freeform(
    interaction: discord.Interaction,
    guild_id: int,
    player_id: int,
    action_key: str,
    action: dict,
    content: str,
    target_id: int | None,
    target_user_id: int | None = None,
    target_name: str | None = None,
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        player = await conn.fetchrow("""
            SELECT character_name, user_id FROM players WHERE id = $1
        """, player_id)

        nation = await conn.fetchrow("SELECT turn_number FROM nation_state WHERE guild_id = $1", guild_id)
        turn_number = nation["turn_number"] if nation else 1

        config = await conn.fetchrow(
            "SELECT vic_year, vic_month, vic_day FROM guild_config WHERE guild_id = $1", guild_id
        )
        from utils.gazette import format_vic_date
        vic_date = format_vic_date(
            config["vic_year"] if config else 1878,
            config["vic_month"] if config else 1,
            config["vic_day"] if config else 1,
        )

        # Log freeform action
        await conn.execute("""
            INSERT INTO freeform_actions
                (guild_id, player_id, action_type, target_id, content, is_public, gazette_tier, turn_number, vic_date)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """, guild_id, player_id, action_key, target_id, content,
            action["gazette_tier"] != "C", action["gazette_tier"], turn_number, vic_date)

        user_mention = f"<@{player['user_id']}>"
        character = player["character_name"]

        # ── HANDLE EACH ACTION TYPE ──

        if action_key == "declaration":
            from utils.gazette import post_tier_b
            await post_tier_b(
                interaction.client, guild_id, conn,
                section="society",
                template_key="declaration",
                character=character,
                user_mention=user_mention,
                content=content,
            )
            await interaction.response.send_message(
                "📰 *Your declaration has been dispatched to The Imperial Gazette.*", ephemeral=True
            )

        elif action_key == "accusation":
            t_mention = f"<@{target_user_id}>" if target_user_id else target_name or "Unknown"
            from utils.gazette import post_tier_b
            await post_tier_b(
                interaction.client, guild_id, conn,
                section="politics",
                template_key="accusation",
                character=character,
                user_mention=user_mention,
                target=target_name or "Unknown",
                target_mention=t_mention,
                content=content,
            )
            # DM the target
            if target_user_id:
                try:
                    target_user = interaction.client.get_user(target_user_id)
                    if target_user:
                        dm_embed = discord.Embed(
                            title="⚖️ You Have Been Publicly Accused",
                            description=(
                                f"**{character}** has levelled the following charge against you:\n\n"
                                f"*\"{content}\"*\n\n"
                                f"You have until the close of the current turn to respond publicly. "
                                f"Use the **🗣️ Political Discourse** button and select **Publicly Accuse** "
                                f"to file your rebuttal."
                            ),
                            color=0x8B0000,
                        )
                        await target_user.send(embed=dm_embed)
                except Exception:
                    pass
            await interaction.response.send_message(
                f"⚖️ *Your accusation against **{target_name}** has been published in The Imperial Gazette.*",
                ephemeral=True
            )

        elif action_key == "propose_deal":
            # Private — DM the target, Tier C
            if target_user_id:
                try:
                    target_user = interaction.client.get_user(target_user_id)
                    if target_user:
                        dm_embed = discord.Embed(
                            title="🤝 A Political Offer Has Been Extended to You",
                            description=(
                                f"**{character}** has privately extended the following offer:\n\n"
                                f"*\"{content}\"*\n\n"
                                f"You may accept or decline using the buttons below. "
                                f"Your decision will become a matter of **public record** in The Imperial Gazette."
                            ),
                            color=0x4B3010,
                        )
                        view = DealResponseView(
                            guild_id=guild_id,
                            proposer_id=player_id,
                            proposer_name=character,
                            proposer_user_id=player["user_id"],
                            target_id=target_id,
                            target_name=target_name,
                            target_user_id=target_user_id,
                        )
                        await target_user.send(embed=dm_embed, view=view)
                except Exception:
                    pass
            await interaction.response.send_message(
                f"🤝 *Your proposal has been dispatched privately to **{target_name}**. "
                f"Their response will be published in the Gazette.*",
                ephemeral=True
            )

        elif action_key == "whisper_campaign":
            # Silent — DM the target
            if target_user_id:
                try:
                    target_user = interaction.client.get_user(target_user_id)
                    if target_user:
                        dm_embed = discord.Embed(
                            title="🗣️ Rumours Reach Your Ears",
                            description=(
                                f"*Someone in the capital's political salons has been spreading whispers about you…*\n\n"
                                f"The rumour: *\"{content}\"*\n\n"
                                f"Your Opinion Rating will be affected at the next turn resolution."
                            ),
                            color=0x2a0a0a,
                        )
                        await target_user.send(embed=dm_embed)
                except Exception:
                    pass
            # Apply opinion damage
            if target_id:
                async with pool.acquire() as conn2:
                    await conn2.execute("""
                        UPDATE players SET opinion_rating = GREATEST(0, opinion_rating - 3) WHERE id = $1
                    """, target_id)
            await interaction.response.send_message(
                f"🗣️ *Your whisper campaign against **{target_name}** has been set in motion. "
                f"No public record shall be kept.*",
                ephemeral=True
            )

        elif action_key == "pledge_vote":
            from utils.gazette import post_tier_b
            await post_tier_b(
                interaction.client, guild_id, conn,
                section="politics",
                template_key="vote_pledge",
                character=character,
                user_mention=user_mention,
                content=content,
            )
            await interaction.response.send_message(
                "🗳️ *Your vote pledge has been entered into the record of the House.*", ephemeral=True
            )

        elif action_key == "organise_protest":
            # Raises unrest slightly
            await conn.execute("""
                UPDATE nation_state SET public_unrest = LEAST(100, public_unrest + 5) WHERE guild_id = $1
            """, guild_id)
            from utils.gazette import post_tier_b
            await post_tier_b(
                interaction.client, guild_id, conn,
                section="society",
                template_key="protest",
                character=character,
                user_mention=user_mention,
                content=content,
            )
            await interaction.response.send_message(
                "✊ *The protest has been organised. Public unrest rises. The Gazette takes note.*", ephemeral=True
            )

        elif action_key == "sign_petition":
            from utils.gazette import post_tier_b
            await post_tier_b(
                interaction.client, guild_id, conn,
                section="politics",
                template_key="petition",
                character=character,
                user_mention=user_mention,
                content=content,
                count="1",
            )
            await interaction.response.send_message(
                "📜 *Your petition has been submitted to the House. Others may add their signatures.*",
                ephemeral=True
            )

        elif action_key == "table_bill":
            from utils.gazette import post_tier_b
            await post_tier_b(
                interaction.client, guild_id, conn,
                section="politics",
                template_key="legislation_tabled",
                character=character,
                user_mention=user_mention,
                content=content,
            )
            await interaction.response.send_message(
                f"📋 ***{content}*** has been tabled before Parliament. Members may now pledge their votes.",
                ephemeral=True
            )

        elif action_key == "call_inquiry":
            t_mention = f"<@{target_user_id}>" if target_user_id else target_name or "Unknown"
            embed = discord.Embed(
                title=f"🔎 Parliamentary Inquiry — {target_name}",
                description=(
                    f"**{character}** ({user_mention}) has called upon **{target_name}** ({t_mention}) "
                    f"to answer before Parliament:\n\n"
                    f"*\"{content}\"*\n\n"
                    f"The minister is expected to respond in this channel."
                ),
                color=0x1a2744,
            )
            # Post to events channel
            events_config = await conn.fetchrow(
                "SELECT channel_events FROM guild_config WHERE guild_id = $1", guild_id
            )
            if events_config and events_config["channel_events"]:
                ch = interaction.client.get_channel(events_config["channel_events"])
                if ch:
                    await ch.send(embed=embed)
            await interaction.response.send_message(
                f"🔎 *Your call for inquiry against **{target_name}** has been filed.*", ephemeral=True
            )

        elif action_key == "loyalty_pledge":
            # Raise loyalty, adjust displeasure
            await conn.execute("""
                UPDATE players SET loyalty = LEAST(100, loyalty + 10) WHERE id = $1
            """, player_id)
            from utils.empress import adjust_displeasure
            await adjust_displeasure(guild_id, -3, conn)
            from utils.gazette import post_tier_b
            await post_tier_b(
                interaction.client, guild_id, conn,
                section="crown",
                template_key="declaration",
                character=character,
                user_mention=user_mention,
                content=f"hereby pledges their undying loyalty to Empress Victoria I and the Imperial Crown.",
            )
            await interaction.response.send_message(
                "👑 *Your loyalty to the Crown has been publicly declared. "
                "Her Majesty takes note of your devotion.*",
                ephemeral=True
            )

        elif action_key == "leak_intelligence":
            from utils.gazette import post_tier_b
            await post_tier_b(
                interaction.client, guild_id, conn,
                section="societies",
                template_key="declaration",
                character="A Confidential Source",
                user_mention="*(identity withheld)*",
                content=content,
            )
            await interaction.response.send_message(
                "🔍 *Your intelligence has been leaked to the Gazette under a confidential byline.*",
                ephemeral=True
            )

        else:
            await interaction.response.send_message(
                f"✅ *Your action has been recorded.*", ephemeral=True
            )


# ─────────────────────────────────────────
# DEAL RESPONSE VIEW (sent via DM)
# ─────────────────────────────────────────

class DealResponseView(View):
    def __init__(self, *, guild_id, proposer_id, proposer_name, proposer_user_id,
                 target_id, target_name, target_user_id):
        super().__init__(timeout=3600)  # 1 hour
        self.guild_id = guild_id
        self.proposer_id = proposer_id
        self.proposer_name = proposer_name
        self.proposer_user_id = proposer_user_id
        self.target_id = target_id
        self.target_name = target_name
        self.target_user_id = target_user_id

    @discord.ui.button(label="✅ Accept the Offer", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: Button):
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Form alliance in DB
            a, b = sorted([self.proposer_id, self.target_id])
            await conn.execute("""
                INSERT INTO alliances (guild_id, player_a, player_b, status)
                VALUES ($1, $2, $3, 'active')
                ON CONFLICT (guild_id, player_a, player_b) DO UPDATE SET status = 'active', broken_at = NULL
            """, self.guild_id, a, b)

            from utils.gazette import post_tier_b
            await post_tier_b(
                interaction.client, self.guild_id, conn,
                section="society",
                template_key="deal_accepted",
                character=self.proposer_name,
                user_mention=f"<@{self.proposer_user_id}>",
                target=self.target_name,
                target_mention=f"<@{self.target_user_id}>",
            )

        await interaction.response.edit_message(
            content="✅ *You have accepted the offer. Your alliance is now a matter of public record.*",
            embed=None, view=None
        )

    @discord.ui.button(label="❌ Decline the Offer", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: Button):
        pool = await get_pool()
        async with pool.acquire() as conn:
            from utils.gazette import post_tier_b
            await post_tier_b(
                interaction.client, self.guild_id, conn,
                section="society",
                template_key="deal_rejected",
                character=self.proposer_name,
                user_mention=f"<@{self.proposer_user_id}>",
                target=self.target_name,
                target_mention=f"<@{self.target_user_id}>",
            )

        await interaction.response.edit_message(
            content="❌ *You have declined the offer. Your refusal is now a matter of public record.*",
            embed=None, view=None
        )
