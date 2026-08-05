import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


class Teste(discord.ui.View):
    @discord.ui.button(label="Clica em mim")
    async def clica(self, interaction, button):
        await interaction.response.send_message("funcionou!", ephemeral=True)


@bot.event
async def on_ready():
    print("Online:", bot.user)
    print("Application ID:", bot.application_id)


@bot.command()
async def teste(ctx):
    await ctx.send("teste de botão", view=Teste())


bot.run(os.getenv("DISCORD_TOKEN"))