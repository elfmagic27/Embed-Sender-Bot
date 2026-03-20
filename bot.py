import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os
import json
from typing import Optional

# ── Bot setup ──────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# In-memory store: { user_id: { embed_name: embed_data } }
user_embeds: dict = {}


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def get_embed_data(user_id: int, name: str) -> dict | None:
    return user_embeds.get(user_id, {}).get(name)


def save_embed_data(user_id: int, name: str, data: dict):
    if user_id not in user_embeds:
        user_embeds[user_id] = {}
    user_embeds[user_id][name] = data


def fresh_embed() -> dict:
    return {
        "color": 0x5865F2,
        "title": "",
        "title_url": "",
        "description": "",
        "author_name": "",
        "author_icon": "",
        "author_url": "",
        "thumbnail": "",
        "image": "",
        "footer_text": "",
        "footer_icon": "",
        "timestamp": False,
        "fields": [],
        "webhook_url": "",
    }


def build_discord_embed(data: dict) -> discord.Embed:
    """Convert our stored data dict → a discord.Embed object."""
    embed = discord.Embed(color=data.get("color", 0x5865F2))

    if data.get("title"):
        embed.title = data["title"]
        if data.get("title_url"):
            embed.url = data["title_url"]

    if data.get("description"):
        embed.description = data["description"]

    if data.get("author_name"):
        embed.set_author(
            name=data["author_name"],
            icon_url=data.get("author_icon") or discord.Embed.Empty,
            url=data.get("author_url") or discord.Embed.Empty,
        )

    if data.get("thumbnail"):
        embed.set_thumbnail(url=data["thumbnail"])

    if data.get("image"):
        embed.set_image(url=data["image"])

    if data.get("footer_text"):
        embed.set_footer(
            text=data["footer_text"],
            icon_url=data.get("footer_icon") or discord.Embed.Empty,
        )

    if data.get("timestamp"):
        from datetime import datetime, timezone
        embed.timestamp = datetime.now(timezone.utc)

    for field in data.get("fields", []):
        embed.add_field(
            name=field["name"],
            value=field["value"],
            inline=field.get("inline", False),
        )

    return embed


def preview_embed(data: dict) -> discord.Embed:
    """Same as build_discord_embed but adds a small footer note."""
    e = build_discord_embed(data)
    current_footer = data.get("footer_text", "")
    note = "📋 Preview — click Done to send"
    if current_footer:
        e.set_footer(text=f"{current_footer}  •  {note}")
    else:
        e.set_footer(text=note)
    return e


async def send_to_webhook(webhook_url: str, payload: dict) -> tuple[bool, str]:
    """POST payload to Discord webhook. Returns (success, message)."""
    async with aiohttp.ClientSession() as session:
        async with session.post(webhook_url, json=payload) as resp:
            if resp.status in (200, 204):
                return True, "✅ Message sent successfully!"
            else:
                text = await resp.text()
                return False, f"❌ Discord returned `{resp.status}`: {text[:200]}"


# ══════════════════════════════════════════════════════════════════════════════
#  VIEWS / UI COMPONENTS
# ══════════════════════════════════════════════════════════════════════════════

# ── Edit option select menu ────────────────────────────────────────────────

class EditSelect(discord.ui.Select):
    def __init__(self, embed_name: str):
        self.embed_name = embed_name
        options = [
            discord.SelectOption(label="Basic Info",       description="Edit title, description, and color",          emoji="✏️"),
            discord.SelectOption(label="URL",              description="Edit the embed URL (makes title a link)",      emoji="🔗"),
            discord.SelectOption(label="Thumbnail",        description="Edit the embed thumbnail URL",                 emoji="🖼️"),
            discord.SelectOption(label="Image",            description="Edit the embed image URL",                     emoji="📷"),
            discord.SelectOption(label="Footer",           description="Edit the embed footer text and icon",          emoji="📝"),
            discord.SelectOption(label="Author",           description="Edit the embed author name, icon, and URL",    emoji="👤"),
            discord.SelectOption(label="Toggle Timestamp", description="Add or remove timestamp from embed",           emoji="⏰"),
            discord.SelectOption(label="Add Field",        description="Add a new field (max 25)",                     emoji="➕"),
            discord.SelectOption(label="Edit Field",       description="Edit an existing field",                       emoji="🔧"),
            discord.SelectOption(label="Remove Field",     description="Remove an existing field",                     emoji="🗑️"),
            discord.SelectOption(label="Webhook URL",      description="Change the target webhook URL",                emoji="🌐"),
        ]
        super().__init__(placeholder="Choose an option to edit the Embed", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        data = get_embed_data(interaction.user.id, self.embed_name)
        if data is None:
            await interaction.response.send_message("❌ Embed not found.", ephemeral=True)
            return

        if choice == "Basic Info":
            await interaction.response.send_modal(BasicInfoModal(self.embed_name, data))
        elif choice == "URL":
            await interaction.response.send_modal(SingleFieldModal(self.embed_name, data, "title_url", "Title URL", "https://example.com", "URL"))
        elif choice == "Thumbnail":
            await interaction.response.send_modal(SingleFieldModal(self.embed_name, data, "thumbnail", "Thumbnail URL", "https://...", "Thumbnail"))
        elif choice == "Image":
            await interaction.response.send_modal(SingleFieldModal(self.embed_name, data, "image", "Image URL", "https://...", "Image"))
        elif choice == "Footer":
            await interaction.response.send_modal(FooterModal(self.embed_name, data))
        elif choice == "Author":
            await interaction.response.send_modal(AuthorModal(self.embed_name, data))
        elif choice == "Toggle Timestamp":
            data["timestamp"] = not data["timestamp"]
            save_embed_data(interaction.user.id, self.embed_name, data)
            state = "enabled ✅" if data["timestamp"] else "disabled ❌"
            await interaction.response.edit_message(
                content=f"⏰ Timestamp **{state}**",
                embed=preview_embed(data),
                view=EmbedEditorView(self.embed_name),
            )
        elif choice == "Add Field":
            if len(data.get("fields", [])) >= 25:
                await interaction.response.send_message("❌ Maximum 25 fields reached.", ephemeral=True)
            else:
                await interaction.response.send_modal(AddFieldModal(self.embed_name, data))
        elif choice == "Edit Field":
            if not data.get("fields"):
                await interaction.response.send_message("❌ No fields to edit.", ephemeral=True)
            else:
                await interaction.response.send_modal(EditFieldModal(self.embed_name, data))
        elif choice == "Remove Field":
            if not data.get("fields"):
                await interaction.response.send_message("❌ No fields to remove.", ephemeral=True)
            else:
                view = RemoveFieldView(self.embed_name, data)
                await interaction.response.edit_message(
                    content="🗑️ Select a field to remove:",
                    embed=preview_embed(data),
                    view=view,
                )
        elif choice == "Webhook URL":
            await interaction.response.send_modal(SingleFieldModal(self.embed_name, data, "webhook_url", "Webhook URL", "https://discord.com/api/webhooks/...", "Webhook URL"))


# ── Main editor view (select + buttons) ───────────────────────────────────

class EmbedEditorView(discord.ui.View):
    def __init__(self, embed_name: str):
        super().__init__(timeout=600)
        self.embed_name = embed_name
        self.add_item(EditSelect(embed_name))

    @discord.ui.button(label="Done", style=discord.ButtonStyle.success, emoji="✅", row=1)
    async def done(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = get_embed_data(interaction.user.id, self.embed_name)
        if not data:
            await interaction.response.send_message("❌ Embed not found.", ephemeral=True)
            return
        if not data.get("webhook_url"):
            await interaction.response.send_message(
                "⚠️ No webhook URL set! Use the dropdown → **Webhook URL** to add one.",
                ephemeral=True,
            )
            return
        await interaction.response.defer()
        payload = {"embeds": [build_discord_embed(data).to_dict()]}
        ok, msg = await send_to_webhook(data["webhook_url"], payload)
        await interaction.followup.send(msg, ephemeral=True)
        if ok:
            await interaction.edit_original_response(
                content=f"🚀 **Embed `{self.embed_name}` sent!**",
                embed=build_discord_embed(data),
                view=None,
            )

    @discord.ui.button(label="Variables", style=discord.ButtonStyle.secondary, emoji="📋", row=1)
    async def variables(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "**📋 Available Variables:**\n"
            "`{user}` — Mentions the user\n"
            "`{server}` — Server name\n"
            "`{membercount}` — Total members\n"
            "`{date}` — Current date\n"
            "`{time}` — Current time",
            ephemeral=True,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="✕", row=1)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_embeds.get(interaction.user.id, {}).pop(self.embed_name, None)
        await interaction.response.edit_message(
            content="❌ Embed creation **cancelled**.",
            embed=None,
            view=None,
        )


# ── Remove field select ────────────────────────────────────────────────────

class RemoveFieldView(discord.ui.View):
    def __init__(self, embed_name: str, data: dict):
        super().__init__(timeout=120)
        self.embed_name = embed_name
        self.data = data
        options = [
            discord.SelectOption(label=f["name"][:100], value=str(i))
            for i, f in enumerate(data.get("fields", []))
        ]
        select = discord.ui.Select(placeholder="Select field to remove", options=options)
        select.callback = self.remove_callback
        self.add_item(select)

    async def remove_callback(self, interaction: discord.Interaction):
        idx = int(interaction.data["values"][0])
        self.data["fields"].pop(idx)
        save_embed_data(interaction.user.id, self.embed_name, self.data)
        await interaction.response.edit_message(
            content="🗑️ Field removed!",
            embed=preview_embed(self.data),
            view=EmbedEditorView(self.embed_name),
        )


# ── Message type chooser ───────────────────────────────────────────────────

class MessageTypeView(discord.ui.View):
    def __init__(self, webhook_url: str):
        super().__init__(timeout=120)
        self.webhook_url = webhook_url

    @discord.ui.button(label="Embed", style=discord.ButtonStyle.primary, emoji="📦")
    async def embed_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EmbedNameModal(self.webhook_url))

    @discord.ui.button(label="Normal Message", style=discord.ButtonStyle.secondary, emoji="💬")
    async def message_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(NormalMessageModal(self.webhook_url))


# ══════════════════════════════════════════════════════════════════════════════
#  MODALS
# ══════════════════════════════════════════════════════════════════════════════

class EmbedNameModal(discord.ui.Modal, title="Create Embed"):
    embed_name = discord.ui.TextInput(label="Embed Name", placeholder='e.g. "announcement"', max_length=50)

    def __init__(self, webhook_url: str):
        super().__init__()
        self.webhook_url = webhook_url

    async def on_submit(self, interaction: discord.Interaction):
        name = self.embed_name.value.strip()
        data = fresh_embed()
        data["webhook_url"] = self.webhook_url
        save_embed_data(interaction.user.id, name, data)

        await interaction.response.send_message(
            f"✅ You just created a new Embed with name `{name}`!\n\n**What now?**\n"
            f"• Use the Dropdown to edit the Embed.\n"
            f"• Can use the embed in Supported modules by referring as `{{embed:{name}}}`\n\n"
            f"*Timeout: 10 Minutes*",
            embed=preview_embed(data),
            view=EmbedEditorView(name),
        )


class NormalMessageModal(discord.ui.Modal, title="Send Normal Message"):
    content = discord.ui.TextInput(
        label="Message Content",
        placeholder="Type your message here...",
        style=discord.TextStyle.paragraph,
        max_length=2000,
    )

    def __init__(self, webhook_url: str):
        super().__init__()
        self.webhook_url = webhook_url

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        ok, msg = await send_to_webhook(self.webhook_url, {"content": self.content.value})
        await interaction.followup.send(msg, ephemeral=True)


class BasicInfoModal(discord.ui.Modal, title="Basic Info"):
    embed_title = discord.ui.TextInput(label="Title", placeholder="Embed title...", required=False, max_length=256)
    description = discord.ui.TextInput(label="Description", placeholder="Embed description...", style=discord.TextStyle.paragraph, required=False, max_length=4096)
    color = discord.ui.TextInput(label="Color (hex)", placeholder="#5865F2", required=False, max_length=7)

    def __init__(self, embed_name: str, data: dict):
        super().__init__()
        self.embed_name = embed_name
        self.embed_title.default = data.get("title", "")
        self.description.default = data.get("description", "")
        self.color.default = f"#{data.get('color', 0x5865F2):06X}"

    async def on_submit(self, interaction: discord.Interaction):
        data = get_embed_data(interaction.user.id, self.embed_name)
        data["title"] = self.embed_title.value.strip()
        data["description"] = self.description.value.strip()
        hex_val = self.color.value.strip().lstrip("#")
        try:
            data["color"] = int(hex_val, 16)
        except ValueError:
            pass
        save_embed_data(interaction.user.id, self.embed_name, data)
        await interaction.response.edit_message(
            content="✏️ **Basic Info updated!**",
            embed=preview_embed(data),
            view=EmbedEditorView(self.embed_name),
        )


class SingleFieldModal(discord.ui.Modal):
    def __init__(self, embed_name: str, data: dict, field_key: str, label: str, placeholder: str, modal_title: str):
        super().__init__(title=modal_title)
        self.embed_name = embed_name
        self.field_key = field_key
        self.input = discord.ui.TextInput(
            label=label, placeholder=placeholder,
            default=data.get(field_key, ""), required=False, max_length=500,
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        data = get_embed_data(interaction.user.id, self.embed_name)
        data[self.field_key] = self.input.value.strip()
        save_embed_data(interaction.user.id, self.embed_name, data)
        await interaction.response.edit_message(
            content=f"✅ **{self.title} updated!**",
            embed=preview_embed(data),
            view=EmbedEditorView(self.embed_name),
        )


class FooterModal(discord.ui.Modal, title="Footer"):
    footer_text = discord.ui.TextInput(label="Footer Text", placeholder="Footer text...", required=False, max_length=2048)
    footer_icon = discord.ui.TextInput(label="Footer Icon URL", placeholder="https://...", required=False, max_length=500)

    def __init__(self, embed_name: str, data: dict):
        super().__init__()
        self.embed_name = embed_name
        self.footer_text.default = data.get("footer_text", "")
        self.footer_icon.default = data.get("footer_icon", "")

    async def on_submit(self, interaction: discord.Interaction):
        data = get_embed_data(interaction.user.id, self.embed_name)
        data["footer_text"] = self.footer_text.value.strip()
        data["footer_icon"] = self.footer_icon.value.strip()
        save_embed_data(interaction.user.id, self.embed_name, data)
        await interaction.response.edit_message(
            content="📝 **Footer updated!**",
            embed=preview_embed(data),
            view=EmbedEditorView(self.embed_name),
        )


class AuthorModal(discord.ui.Modal, title="Author"):
    author_name = discord.ui.TextInput(label="Author Name", placeholder="Author name...", required=False, max_length=256)
    author_icon = discord.ui.TextInput(label="Author Icon URL", placeholder="https://...", required=False, max_length=500)
    author_url  = discord.ui.TextInput(label="Author URL", placeholder="https://...", required=False, max_length=500)

    def __init__(self, embed_name: str, data: dict):
        super().__init__()
        self.embed_name = embed_name
        self.author_name.default = data.get("author_name", "")
        self.author_icon.default = data.get("author_icon", "")
        self.author_url.default  = data.get("author_url",  "")

    async def on_submit(self, interaction: discord.Interaction):
        data = get_embed_data(interaction.user.id, self.embed_name)
        data["author_name"] = self.author_name.value.strip()
        data["author_icon"] = self.author_icon.value.strip()
        data["author_url"]  = self.author_url.value.strip()
        save_embed_data(interaction.user.id, self.embed_name, data)
        await interaction.response.edit_message(
            content="👤 **Author updated!**",
            embed=preview_embed(data),
            view=EmbedEditorView(self.embed_name),
        )


class AddFieldModal(discord.ui.Modal, title="Add Field"):
    field_name  = discord.ui.TextInput(label="Field Name",  placeholder="Field name...",  max_length=256)
    field_value = discord.ui.TextInput(label="Field Value", placeholder="Field value...", style=discord.TextStyle.paragraph, max_length=1024)

    def __init__(self, embed_name: str, data: dict):
        super().__init__()
        self.embed_name = embed_name

    async def on_submit(self, interaction: discord.Interaction):
        data = get_embed_data(interaction.user.id, self.embed_name)
        data.setdefault("fields", []).append({
            "name": self.field_name.value.strip(),
            "value": self.field_value.value.strip(),
            "inline": False,
        })
        save_embed_data(interaction.user.id, self.embed_name, data)
        await interaction.response.edit_message(
            content="➕ **Field added!**",
            embed=preview_embed(data),
            view=EmbedEditorView(self.embed_name),
        )


class EditFieldModal(discord.ui.Modal, title="Edit Field"):
    field_index = discord.ui.TextInput(label="Field number (1, 2, 3...)", placeholder="1", max_length=2)
    field_name  = discord.ui.TextInput(label="New Field Name",  placeholder="Field name...",  max_length=256)
    field_value = discord.ui.TextInput(label="New Field Value", placeholder="Field value...", style=discord.TextStyle.paragraph, max_length=1024)

    def __init__(self, embed_name: str, data: dict):
        super().__init__()
        self.embed_name = embed_name
        fields_preview = "\n".join(f"{i+1}. {f['name']}" for i, f in enumerate(data.get("fields", [])))
        self.field_index.placeholder = f"1–{len(data.get('fields', []))} (fields: {fields_preview[:50]})"

    async def on_submit(self, interaction: discord.Interaction):
        data = get_embed_data(interaction.user.id, self.embed_name)
        try:
            idx = int(self.field_index.value.strip()) - 1
            if idx < 0 or idx >= len(data.get("fields", [])):
                raise IndexError
        except (ValueError, IndexError):
            await interaction.response.send_message(
                f"❌ Invalid field number. You have {len(data.get('fields', []))} field(s).",
                ephemeral=True,
            )
            return
        data["fields"][idx]["name"]  = self.field_name.value.strip()
        data["fields"][idx]["value"] = self.field_value.value.strip()
        save_embed_data(interaction.user.id, self.embed_name, data)
        await interaction.response.edit_message(
            content=f"🔧 **Field {idx+1} updated!**",
            embed=preview_embed(data),
            view=EmbedEditorView(self.embed_name),
        )


# ══════════════════════════════════════════════════════════════════════════════
#  SLASH COMMANDS
# ══════════════════════════════════════════════════════════════════════════════

@bot.tree.command(name="webhook", description="Send a message or embed to a webhook URL")
@app_commands.describe(webhook_url="The Discord webhook URL to send to")
async def webhook_cmd(interaction: discord.Interaction, webhook_url: str):
    if "discord.com/api/webhooks" not in webhook_url:
        await interaction.response.send_message(
            "❌ That doesn't look like a valid Discord webhook URL.\n"
            "It should start with `https://discord.com/api/webhooks/`",
            ephemeral=True,
        )
        return

    await interaction.response.send_message(
        "👋 Hey! What would you like to send to the webhook?",
        view=MessageTypeView(webhook_url),
        ephemeral=True,
    )


@bot.tree.command(name="embed_create", description="Create and edit an embed, then send it to a webhook")
@app_commands.describe(
    embed_name  = "A name for this embed (e.g. 'announcement')",
    webhook_url = "The Discord webhook URL to send to",
)
async def embed_create(interaction: discord.Interaction, embed_name: str, webhook_url: str):
    if "discord.com/api/webhooks" not in webhook_url:
        await interaction.response.send_message(
            "❌ Invalid webhook URL. Must start with `https://discord.com/api/webhooks/`",
            ephemeral=True,
        )
        return

    data = fresh_embed()
    data["webhook_url"] = webhook_url
    save_embed_data(interaction.user.id, embed_name, data)

    await interaction.response.send_message(
        f"✅ You just created a new Embed with name `{embed_name}`!\n\n"
        f"**What now?**\n"
        f"• Use the Dropdown to edit the Embed.\n"
        f"• Can use the embed in Supported modules by referring as `{{embed:{embed_name}}}`\n\n"
        f"*Update the Embed using the dropdown below! Timeout: 10 Minutes*",
        embed=preview_embed(data),
        view=EmbedEditorView(embed_name),
    )


@bot.tree.command(name="message_send", description="Send a plain text message to a webhook")
@app_commands.describe(
    webhook_url = "The Discord webhook URL",
    content     = "The message content to send",
)
async def message_send(interaction: discord.Interaction, webhook_url: str, content: str):
    if "discord.com/api/webhooks" not in webhook_url:
        await interaction.response.send_message("❌ Invalid webhook URL.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    ok, msg = await send_to_webhook(webhook_url, {"content": content})
    await interaction.followup.send(msg, ephemeral=True)


# ══════════════════════════════════════════════════════════════════════════════
#  EVENTS
# ══════════════════════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN environment variable not set!")
    bot.run(token)
