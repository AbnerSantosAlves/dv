import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import aiohttp
from keep_alive import keep_alive

permissoes = discord.Intents.default()
permissoes.message_content = True
permissoes.members = True

bot = commands.Bot(command_prefix="m!", intents=permissoes)

load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SHAPES_API_KEY = os.getenv("SHAPES_API_KEY")
SHAPES_API_URL = "https://api.shapes.inc/v1/chat/completions"
SHAPES_MODEL = "shapesinc/vados-za3j"

async def carregar_cogs():
     for arquivo in os.listdir('cogs'):
          if arquivo.endswith('.py'):
            await bot.load_extension(f'cogs.{arquivo[:-3]}')

@bot.event
async def on_ready():
    print('Estou pronto')
    await carregar_cogs()
    await bot.change_presence(status=discord.Status.dnd)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    is_vados_in_text = "vados" in message.content.lower()
    is_mentioned = bot.user.mention in message.content
    is_reply_to_bot = (
        message.reference is not None and
        isinstance(message.reference.resolved, discord.Message) and
        message.reference.resolved.author == bot.user
    )

    if is_vados_in_text or is_mentioned or is_reply_to_bot:
        async with message.channel.typing():
            payload = {
                "model": SHAPES_MODEL,
                "messages": [{"role": "user", "content": message.content}]
            }

            headers = {
                "Authorization": f"Bearer {SHAPES_API_KEY}",
                "Content-Type": "application/json"
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(SHAPES_API_URL, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        reply = data["choices"][0]["message"]["content"]
                        await message.reply(reply, mention_author=False)
                    else:
                        await message.channel.send("Eu estou ocupada agora, outra hora te respondo.")

    await bot.process_commands(message)

keep_alive()
bot.run(DISCORD_BOT_TOKEN)