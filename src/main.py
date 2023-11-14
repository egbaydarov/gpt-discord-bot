import asyncio
import logging
from typing import Optional, cast

import discord
import tiktoken
from commands import chat, messages
from completion import generate_completion_response, process_response
from constants import (
    BOT_INVITE_URL,
    DISCORD_BOT_TOKEN,
)
from discord import Message as DiscordMessage
from discord.ext import commands
from parse_model import generate_choice_model, get_models_completion
from personas import (
    generate_choice_persona,
    get_all_icons,
    get_persona,
    get_persona_by_emoji,
    update_persona_models,
)
from utils import (
    allowed_thread,
    close_thread,
    count_token_message,
    generate_initial_system,
    logger,
    remove_last_bot_message,
    send_to_log_channel,
    should_block,
)

logging.basicConfig(
    format="[%(asctime)s] [%(filename)s:%(lineno)d] %(message)s", level=logging.INFO
)

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)
bot = commands.Bot(command_prefix="!", intents=intents)
MODEL = tiktoken.encoding_for_model(
    "gpt-4"
)  # need to be upgraded to the new gpt-4 turbo but can do the job for now
personas_choice = generate_choice_persona()
models_choice = generate_choice_model()


class Client(discord.Client):
    def __init__(self, *, intents: discord.Intents) -> None:  # noqa
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)

    async def setup_hook(self) -> None:  # noqa
        logger.info("Setting up slash commands")
        await self.tree.sync()


@client.event
async def on_ready() -> None:
    logger.info(f"We have logged in as {client.user}. Invite URL: {BOT_INVITE_URL}")
    await tree.sync()


# /chat message:
@tree.command(name="chat", description="Create a new thread for conversation")
@discord.app_commands.describe(
    persona="The persona to use with the model, changing this response style"
)
@discord.app_commands.describe(models="The model to use for the response")
@discord.app_commands.choices(persona=personas_choice)
@discord.app_commands.choices(models=models_choice)
@discord.app_commands.checks.has_permissions(send_messages=True)
@discord.app_commands.checks.has_permissions(view_channel=True)
@discord.app_commands.checks.bot_has_permissions(send_messages=True)
@discord.app_commands.checks.bot_has_permissions(view_channel=True)
@discord.app_commands.checks.bot_has_permissions(manage_threads=True)
async def chat_command(
    int: discord.Interaction,
    message: str,
    persona: Optional[discord.app_commands.Choice[str]] = None,
    models: Optional[discord.app_commands.Choice[str]] = None,
) -> None:
    await chat(client, int, message, persona, model=models)


# calls for each message
@client.event
async def on_message(message: DiscordMessage) -> None:  # noqa
    await messages(message, client, MODEL)


@tree.command(name="help", description="Print each persona and their description")
@discord.app_commands.checks.has_permissions(send_messages=True)
@discord.app_commands.checks.has_permissions(view_channel=True)
@discord.app_commands.checks.bot_has_permissions(send_messages=True)
@discord.app_commands.checks.bot_has_permissions(view_channel=True)
@discord.app_commands.describe(
    persona="The persona to use with the model, changing this response style"
)
@discord.app_commands.choices(persona=personas_choice)
async def help_command(
    int: discord.Interaction, persona: Optional[discord.app_commands.Choice[str]] = None
) -> None:
    persona_system = get_persona(persona.value if persona else None)
    embed = discord.Embed(
        title=f"{persona_system.icon} {persona_system.title}",
        description=persona_system.system,
        color=discord.Colour.from_str(persona_system.color),
    )
    embed.add_field(
        name="Model",
        value=f"{persona_system.model}",
        inline=True,
    )
    await int.response.send_message(embed=embed)


@tree.command(name="change", description="Change the persona of the current thread")
@discord.app_commands.describe(persona="The persona to use with the model")
@discord.app_commands.choices(persona=personas_choice)
@discord.app_commands.guild_only()
async def change_persona(
    int: discord.Interaction, persona: Optional[discord.app_commands.Choice[str]] = None
) -> None:
    logger.info(
        f"Changing persona to {persona.value} in Guild: {int.guild}"  # type: ignore
    )
    if not allowed_thread(client, int.channel, int.guild, int.user):
        await int.response.send_message(
            "This command can only be used in a thread created by the bot",
            ephemeral=True,
        )
        return

    thread = cast(discord.Thread, int.channel)
    persona_system = get_persona(persona.value if persona else None)
    thread_name = thread.name.split(" ")
    # replace the 3rd element with the new persona icon
    icon = thread_name[2]
    icon_list = get_all_icons()
    if icon in icon_list:
        thread_name[2] = persona_system.icon
        await thread.edit(name=" ".join(thread_name))
        await send_to_log_channel(
            client,
            int.guild.id,  # type: ignore
            thread.name,
            int.user.global_name,  # type: ignore
            persona_system,
            None,
            "changed",
        )
        await int.response.send_message(
            f"Changed persona to {persona_system.title}", ephemeral=True
        )
    else:
        await int.response.send_message(
            f"Failed to change persona to {persona_system.title}",
            ephemeral=True,
        )


@tree.command(name="close", description="Stop the chat and archive the thread")
async def stop(int: discord.Interaction) -> None:
    logger.info(f"Closing thread in Guild: {int.guild}")
    # followup
    await int.response.defer()
    follow_up = await int.followup.send("Closing thread...", wait=True, ephemeral=True)
    if not allowed_thread(client, int.channel, int.guild, int.user):
        await int.response.send_message(
            "This command can only be used in a thread created by the bot",
            ephemeral=True,
        )
        return
    thread = cast(discord.Thread, int.channel)
    await close_thread(thread)

    await send_to_log_channel(
        client,
        int.guild.id,  # type: ignore
        thread.name,
        user=int.user.global_name,  # type: ignore
        persona=None,
        type="closed",
    )
    await follow_up.delete()


@tree.command(name="rerun", description="Rerun the last message")
async def rerun(int: discord.Interaction) -> None:
    if not allowed_thread(client, int.channel, int.guild, int.user):
        await int.response.send_message(
            "This command can only be used in a thread created by the bot",
            ephemeral=True,
        )
        return
    await int.response.defer()
    follow_up = await int.followup.send("Rerunning...", wait=True, ephemeral=True)
    thread = cast(discord.Thread, int.channel)
    channel_messages = await generate_initial_system(client, thread)
    log_persona = get_persona_by_emoji(thread)
    model_usage = get_models_completion(thread, log_persona)
    log_persona = update_persona_models(log_persona, model_usage)
    nb_tokens = count_token_message(channel_messages, MODEL)

    await send_to_log_channel(
        client,
        int.guild.id,  # type: ignore
        thread.name,
        int.user.global_name,  # type: ignore
        log_persona,
        model_usage,
        "message",
        token=nb_tokens,
    )
    if nb_tokens > model_usage.max_input_token:
        await close_thread(thread)
        return

    try:
        async with thread.typing():
            response_data = await generate_completion_response(
                messages=remove_last_bot_message(channel_messages[:-1]),
                model=model_usage.name,
            )
            await process_response(thread=thread, response_data=response_data)
    except Exception as e:
        logger.exception(e)
        await follow_up.edit(content=f"Failed to rerun: {str(e)}")
        return
    await follow_up.delete()


@tree.command(
    name="chat_multiple",
    description="Start a chat with a long message that need to be split",
)
@discord.app_commands.describe(
    persona="The persona to use with the model, changing this response style"
)
@discord.app_commands.describe(model="The model to use for the response")
@discord.app_commands.choices(persona=personas_choice)
@discord.app_commands.choices(model=models_choice)
@discord.app_commands.checks.has_permissions(send_messages=True)
@discord.app_commands.checks.has_permissions(view_channel=True)
@discord.app_commands.checks.bot_has_permissions(send_messages=True)
@discord.app_commands.checks.bot_has_permissions(view_channel=True)
@discord.app_commands.checks.bot_has_permissions(manage_threads=True)
async def chat_multiple(
    int: discord.Interaction,
    first_message: str,
    persona: Optional[discord.app_commands.Choice[str]] = None,
    model: Optional[discord.app_commands.Choice[str]] = None,
) -> None:
    try:
        # only support creating thread in text channel
        if not isinstance(int.channel, discord.TextChannel) or should_block(int.guild):
            return
        # Before creating the message, wait for the multiple message

        def check(message: discord.Message) -> bool:
            return message.author == int.user and message.channel == int.channel

        messages = []
        channel = cast(discord.TextChannel, int.channel)
        await channel.send(
            "Starting chat, please send your message in the next 60 seconds",
            delete_after=30,
        )

        async def message_wait_for() -> list[str]:
            message = []
            channel = cast(discord.TextChannel, int.channel)
            try:
                while True:
                    msg = await client.wait_for("message", check=check, timeout=60)

                    if msg.content.lower() in ("$end", "$done", "$stop"):
                        await msg.reply("End of message", delete_after=5)
                        return message
                    elif msg.content.lower() in ("$cancel"):
                        await msg.reply("Canceling", delete_after=5)
                        return []
                    else:
                        message.append(msg.content)
                        await msg.reply("Message received", delete_after=5)
                    await msg.delete()
            except asyncio.TimeoutError:
                await channel.send("Timeout, stopping the chat", delete_after=10)
                return []

        messages = await message_wait_for()
        if len(messages) == 0:
            return

        message = first_message + "\n" + "\n".join(messages)
        await chat(client, int, message, persona, follow_up=None, model=model)

    except Exception as e:
        logger.error(e)
        await int.response.send_message(
            f"Failed to start chat {str(e)}", ephemeral=True
        )


client.run(DISCORD_BOT_TOKEN)
