import discord
from discord.ext import commands
from discord import Embed
from Util import logger
import os
import database

try:
    import config
except ImportError:
    print("Couldn't import config.py")
try:
    import monkeyPatch
except ImportError:
    print("DEBUG: No Monkey patch found!")

bot = commands.Bot(command_prefix=os.getenv('prefix'), description='Well boys, we did it. Baddies is no more.')

startup_extensions = ["essentials",
                      "moderation",
                      "info",
                      "listenerCog"]


# Function to fetch bans from the banlistguild and smack them into the database at startup, like if the bot has been
# offline
async def updateDatabase():
    banguild = bot.get_guild(int(os.getenv('banlistguild')))
    ban_list = await banguild.bans()
    for BanEntry in ban_list:
        if not database.isBanned(BanEntry.user.id):
            database.newBan(userid=BanEntry.user.id, discordtag=BanEntry.user.name + BanEntry.user.discriminator,
                            avatarurl=BanEntry.user.avatar_url)


@bot.event
async def on_ready():
    logger.setup_logger()

    # Bot startup is now done...
    logger.logDebug("----------[LOGIN SUCESSFULL]----------", "INFO")
    logger.logDebug("     Username: " + bot.user.name, "INFO")
    logger.logDebug("     UserID:   " + str(bot.user.id), "INFO")
    logger.logDebug("--------------------------------------", "INFO")
    await logger.log("Bot startup done.", bot, "INFO", "Bot startup done.\n")
    await bot.change_presence(activity=discord.Game(name="with the banhammer"))

    if os.getenv('testModeEnabled') == "True":
        await logger.log("TESTMODE IS ENABLED! MODERATION ACTIONS WILL NOT HAVE ANY EFFECT!", bot, "DEBUG")
    else:
        await updateDatabase()
    print("\n")

    # Ban appeal server setup


@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.NoPrivateMessage):
        await ctx.send("This command cannot be used in private messages")
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.send(
            embed=Embed(color=discord.Color.red(), description="I need the permission `Ban Members` to sync the bans!"))
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send(
            embed=Embed(color=discord.Color.red(), description="You are missing the permission `Ban Members`!"))
    elif isinstance(error, commands.CheckFailure):
        return
    elif isinstance(error, commands.CommandOnCooldown):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        return
    elif isinstance(error, commands.BadArgument):
        return
    elif isinstance(error, commands.CommandNotFound):
        return
    else:
        await ctx.send("Something went wrong while executing that command... Sorry!")
        await logger.log("%s" % error, bot, "ERROR")


@bot.event
async def on_guild_join(guild):
    await logger.log("Joined a new guild (`%s` - `%s`)" % (guild.name, guild.id), bot, "INFO")
    banguild = bot.get_guild(int(os.getenv('banlistguild')))
    ban_list = await banguild.bans()
    sucess = "True"
    sucessedbans = 0
    banned = 0
    bans = len(ban_list)
    for BanEntry in ban_list:
        if (banned == 5) and (sucessedbans == 0):
            await logger.log("Could not syncban the first 5 accounts in the guild `%s` (%s). Stopping sync." % (
                guild.name, guild.id), bot, "INFO")
            break
        try:
            await guild.ban(BanEntry.user, reason=f"WatchDog - Global Ban")
            sucess = "True"
            sucessedbans += 1
        except Exception as e:
            logger.logDebug("Could not syncban the user `%s` (%s) in the guild `%s` (%s) - %s" % (
                BanEntry.user.name, str(BanEntry.user.id), guild.name, str(guild.id), e), "INFO")
            sucess = "False"
        banned += 1
        logger.logDebug(
            str(banned) + "/" + str(bans) + " Syncbanned (new guild join) the user `%s` (%s) - Sucess: %s" % (
                BanEntry.user.name, str(BanEntry.user.id), sucess), "DEBUG")
    await logger.log("Synced all bans to the guild `%s` (%s)!" % (guild.name, guild.id), bot, "INFO")
    logger.logDebug("Sucessfully banned " + str(sucessedbans) + "/" + str(bans) + " accounts, in the guild %s (%s)" % (
        guild.name, str(guild.id)), "DEBUG")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    ctx: commands.Context = await bot.get_context(message)
    if message.content.startswith(os.getenv('prefix')):
        if ctx.command is not None:
            await logger.log("`%s` (%s) used the `%s` command in the guild `%s` (%s), in the channel `%s` (%s)" % (
                ctx.author.name, ctx.author.id, ctx.invoked_with, ctx.guild.name, ctx.guild.id, ctx.channel.name,
                ctx.channel.id), bot, "INFO")
            await bot.invoke(ctx)
    else:
        return


if __name__ == '__main__':
    for extension in startup_extensions:
        try:
            bot.load_extension(f"cogs.{extension}")
        except Exception as e:
            logger.logDebug(f"Failed to load extension {extension}. - {e}", "ERROR")

bot.run(os.getenv('token'))
