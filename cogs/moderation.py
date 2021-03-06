import asyncio
import discord
from discord import Embed
from discord.ext import commands
from Util import logger
from database import isModerator
import database
import os


class Moderation(commands.Cog, name="Moderation"):
    def __init__(self, bot):
        self.bot = bot

    # Helping Functions #

    # Function to have the moderator confirm their action, on stuff like revsync
    @classmethod
    async def confirmAction(self, ctx, action):
        await ctx.send("Are you sure you want to do a revsync, and sync all the bans from this guild too all other "
                       "guilds? Confirm with a `Revsync the " + ctx.guild.name + " guild`...\nSleeping for 30 "
                                                                                 "seconds!")
        await asyncio.sleep(30)
        history = await ctx.channel.history(limit=100).flatten()
        for message in history:
            if (message.author.id == ctx.author.id) & (
                    message.content == ("Revsync the " + ctx.guild.name + " guild")):
                return True
        return False

    # Function to send message about the ban
    @classmethod
    async def logBan(cls, ctx, user, unban=False, reason=None):
        bot = ctx.bot
        # Sends a message in the botlog
        if unban:
            color = discord.Color.green()
            text = "unbanned"
        else:
            color = discord.Color.red()
            text = "banned"
        await logger.logEmbed(color,
                              "Moderator `%s` %s `%s` - (%s)" % (ctx.author.name, text, user.name, user.id),
                              bot)
        # Send private ban notif in private moderator ban list
        prvchannel = bot.get_channel(int(os.getenv('prvbanlist')))
        prvembed = discord.Embed(title="Account " + text, color=color,
                                 description="`%s` has been globally %s" % (user.id, text))
        prvembed.add_field(name="Moderator", value="%s (`%s`)" % (ctx.author.name, ctx.author.id),
                           inline=True)
        prvembed.add_field(name="Name when " + text, value="%s" % user, inline=True)
        prvembed.add_field(name="In server", value="%s (`%s`)" % (ctx.guild.name, ctx.guild.id),
                           inline=True)
        prvembed.add_field(name="In channel", value="%s (`%s`)" % (ctx.channel.name, ctx.channel.id),
                           inline=True)
        if (reason is not None) and (reason != ""):
            prvembed.add_field(name="Reason", value="%s" % reason,
                               inline=True)
        prvembed.set_footer(text="%s has been globally %s" % (user, text),
                            icon_url="https://cdn.discordapp.com/attachments/456229881064325131/489102109363666954/366902409508814848.png")
        prvembed.set_thumbnail(url=user.avatar_url)
        await prvchannel.send(embed=prvembed)
        # Update the database
        if unban:
            database.invalidateBan(user.id)
        else:
            database.newBan(userid=user.id, discordtag=user.name + "#" + user.discriminator, moderator=ctx.author.id,
                            reason=reason, guild=ctx.guild.id, avatarurl=user.avatar_url)

    # Function to ban
    @classmethod
    async def performBan(cls, ctx, users, reason):
        bot = ctx.bot
        if isinstance(users, tuple):
            users = list(users)
        elif not isinstance(users, list):
            users = [users]

        # Check all users if they are already banned and stuff
        usersToBan = []
        for user in users:
            if user == ctx.bot.user:
                error = "Banning a user failed - given user is the bot"
                await logger.log(error, bot, "INFO")
            elif isModerator(user.id):
                error = "Banning a user failed - given user is a Global Moderator"
                await logger.log(error, bot, "INFO")
            elif database.isBanned(user.id):
                error = "Banning a user failed - given user is already banned"
                await logger.log(error, bot, "INFO")
            else:
                usersToBan.append(user)

        # If the list is empty, then there are no users to ban. As such, let's return the most recent error, I guess
        if not usersToBan:
            return error

        # Ban on current guild
        for user in usersToBan:
            # Bans on current guild first
            try:
                await ctx.guild.ban(user, reason="WatchDog - Global Ban")
            except Exception as e:
                await logger.log("Could not ban the user `%s` (%s) in the guild `%s` (%s)" % (
                    user.name, user.id, ctx.guild.name, ctx.guild.id), bot, "INFO")
                logger.logDebug(e)

        # Ban on other guilds
        for user in usersToBan:
            guilds = [guild for guild in bot.guilds if guild.get_member(user.id)]
            guilds.append(bot.get_guild(int(os.getenv('banlistguild'))))

            for guild in guilds:
                try:
                    await guild.ban(user, reason="WatchDog - Global Ban")
                except Exception as e:
                    await logger.log("Could not ban the user `%s` (%s) in the guild `%s` (%s)" % (
                        user.name, user.id, guild.name, guild.id), bot, "INFO")
                    logger.logDebug(e)
            # Send private ban notif in private moderator ban list as well as message in botlog
            await cls.logBan(ctx, user, reason=reason)

    # Function used to try and get users from arguments
    @classmethod
    async def getUser(cls, ctx, arg):
        if arg.startswith("<@") and arg.endswith(">"):
            userid = arg.replace("<@", "").replace(">", "").replace("!", "")  # fuck you nicknames
        else:
            userid = arg

        user = None
        try:
            user = await ctx.bot.fetch_user(userid)
        except Exception as e:
            logger.logDebug("User not found! ID method - %s" % e)
            try:
                user = discord.utils.get(ctx.message.guild.members, name=arg)
            except Exception as e:
                logger.logDebug("User not found! Name method - %s" % e)
        if user is not None:
            logger.logDebug("User found! - %s" % user.name)
            return user
        else:
            raise Exception("User not found!")

    # Funtion to try and get a reason from multiple arguments
    @classmethod
    async def sortArgs(cls, ctx, args):
        userlist = []
        reasonlist = []
        logger.logDebug("Userlist: " + str(userlist))
        logger.logDebug("Reason: " + str(reasonlist))

        i = 0
        user_max = 0
        for arg in args:
            try:
                founduser = await cls.getUser(ctx, arg)
                logger.logDebug("User found: " + str(founduser))
                userlist.append(founduser)

                user_max = i
            except Exception:
                print("no user lol")
            i += 1
        logger.logDebug("Usermax: " + str(user_max))

        i = 0
        for arg in args:
            if i > user_max:
                reasonlist.append(arg)
            i += 1

        logger.logDebug("Userlist 2: " + str(userlist))
        logger.logDebug("Reason 2: " + str(reasonlist))

        users = tuple(userlist)
        reason = ' '.join(reasonlist)
        return users, reason

    # Commands #

    @commands.command(name="revsync", aliases=["reversesync"])
    @commands.guild_only()
    @commands.bot_has_permissions(ban_members=True)
    async def _revsync(self, ctx):
        """Sync bans from server to central, and other guilds - GM only."""
        ban_list = await ctx.guild.bans()
        if isModerator(ctx.author.id):
            if not await self.confirmAction(ctx, "revsync"):
                await ctx.send("You took too long to respond, or didn't respond with the correct message...\n" +
                               "Try again?")
                return
            banCountAll = len(ban_list)
            if banCountAll == 0:
                await ctx.send("Sorry, but the guild doesn't have any bans!")
                return

            users = []
            for BanEntry in ban_list:
                users.append(BanEntry.user)

            embed = discord.Embed(title="Revsync in progress...", color=discord.Color.green(),
                                  description="Whoo! Here we goo! Don't worry, the bans are working very hard to "
                                              "reversibly synchronize! 👌")
            embed.set_footer(text="%s - Global WatchDog Moderator" % ctx.author.name,
                             icon_url=ctx.author.avatar_url)
            embed_message = await ctx.send(embed=embed)

            # Perform the bans
            await self.performBan(ctx, users, "Revsync from " + ctx.guild.name + " (" + str(ctx.guild.id) + ")")

            # send final embed, telling the ban was sucessful
            if len(ban_list) == 1:
                desc_string = "Reverse synchronisation complete! %s account has been globally banned 👌" % len(
                    ban_list)
            else:
                desc_string = "Reverse synchronisation complete! %s accounts have been globally banned 👌" % len(
                    ban_list)

            embed = discord.Embed(title="Revsync complete", color=discord.Color.green(),
                                  description=desc_string)
            embed.set_footer(text="%s - Global WatchDog Moderator" % ctx.author.name,
                             icon_url=ctx.author.avatar_url)
            embed.set_image(
                url="https://cdn.discordapp.com/attachments/485619099481800714/485917795679338496/1521567278_980x.gif")
            await embed_message.edit(embed=embed)
        else:
            await ctx.send(
                embed=Embed(color=discord.Color.red(), description="You are not a Global Moderator! Shame!"))

    @commands.command(name="ban")
    async def _ban(self, ctx, arg1, *args):
        """Bans a user globally - GM only."""
        bot = ctx.bot
        if isModerator(ctx.author.id):
            try:
                user = await self.getUser(ctx, arg1)
            except Exception as e:
                await ctx.send(embed=Embed(color=discord.Color.red(), description="Specified user not found!"))
                await logger.log("Could not get a specified user - Specified arg: %s - Error: %s" % (arg1, e), bot,
                                 "ERROR")
                return

            # Get the ban reason, if there is any
            reason = None
            if len(args) > 1:
                logger.logDebug("More than 1 argument given on ban command, getting banreason")
                reason = ' '.join(args)
                logger.logDebug("Banreason: " + reason)

            # Sends main embed
            embed = discord.Embed(title="Account is being banned...", color=discord.Color.green(),
                                  description="The ban is happening! Woah there! 👌")
            embed.set_footer(text="%s - Global WatchDog Moderator" % ctx.author.name,
                             icon_url=ctx.author.avatar_url)
            embed_message = await ctx.send(embed=embed)

            # Perform the ban
            error = await self.performBan(ctx, user, reason)

            # Do this when done
            # send final embed, telling the ban was sucessful
            if not error:
                embed = discord.Embed(title="Account banned", color=discord.Color.green(),
                                      description="`%s` has been globally banned 👌" % user)
                embed.set_image(
                    url="https://cdn.discordapp.com/attachments/456229881064325131/475498849696219141/ban.gif")
            else:
                embed = discord.Embed(title="Banning failed", color=discord.Color.red(),
                                      description="Error: %s" % error)
                embed.set_image(
                    url="https://cdn.discordapp.com/attachments/474313313598046238/689828429318848517/failed.gif")
            embed.set_footer(text="%s - Global WatchDog Moderator" % ctx.author.name,
                             icon_url=ctx.author.avatar_url)
            await embed_message.edit(embed=embed)
        else:
            await ctx.send(
                embed=Embed(color=discord.Color.red(), description="You are not a Global Moderator! Shame!"))

    @commands.command(name="unban")
    async def _unban(self, ctx, arg1):
        """Unbans a user globally - GM only."""
        bot = ctx.bot
        if isModerator(ctx.author.id):
            try:
                user = await self.getUser(ctx, arg1)
            except Exception as e:
                await ctx.send(embed=Embed(color=discord.Color.red(), description="Specified user not found!"))
                await logger.log("Could not get a specified user - Specified arg: %s - Error: %s" % (arg1, e), bot,
                                 "ERROR")
                return

            if not database.isBanned(user.id):
                return

            guilds = bot.guilds
            if len(guilds) >= 1:
                embed = discord.Embed(title="Account is being unbanned...", color=discord.Color.green(),
                                      description="The bans are happening! Woah there! 👌")
                embed.set_footer(text="%s - Global WatchDog Moderator" % ctx.author.name,
                                 icon_url=ctx.author.avatar_url)
                embed_message = await ctx.send(embed=embed)
                for guild in guilds:
                    if guild is None:  # Check if guild is none
                        await logger.log("Guild is none... GuildID: " + guild.id, bot, "ERROR")
                        continue
                    try:
                        await guild.unban(user, reason="WatchDog - Global Unban")
                    except Exception as e:
                        logger.logDebug("Could not unban the user `%s` (%s) in the guild `%s` (%s)" % (
                            user.name, user.id, guild.name, guild.id), "DEBUG")
                        logger.logDebug(e)
                # do this when done
                # Send private ban notif in private moderator ban list as well as message in botlog
                await self.logBan(ctx, user, unban=True)
                # edits final embed
                embed = discord.Embed(title="Account unbanned", color=discord.Color.green(),
                                      description="`%s` has been globally unbanned 👌" % user)
                embed.set_footer(text="%s - Global WatchDog Moderator" % ctx.author.name,
                                 icon_url=ctx.author.avatar_url)
                embed.set_image(
                    url="https://cdn.discordapp.com/attachments/456229881064325131/475498943178866689/unban.gif")
                await embed_message.edit(embed=embed)
        else:
            await ctx.send(
                embed=Embed(color=discord.Color.red(), description="You are not a Global Moderator! Shame!"))

    @commands.command(name="mban", aliases=["multipleban"])
    async def _mban(self, ctx, *args):
        """Bans multiple users globally - GM only."""
        if isModerator(ctx.author.id):
            # remove dupes
            args = list(dict.fromkeys(args))
            # sort the args into users and reason
            sortedargs = await self.sortArgs(ctx, args)
            print(sortedargs)
            users = sortedargs[0]
            print(users)
            reason = sortedargs[1]
            print(reason)

            # Sends main embed
            embed = discord.Embed(title="Accounts are being banned...", color=discord.Color.green(),
                                  description="The bans are happening! Woah there! 👌")
            embed.set_footer(text="%s - Global WatchDog Moderator" % ctx.author.name,
                             icon_url=ctx.author.avatar_url)
            embed_message = await ctx.send(embed=embed)

            # Perform the bans
            error = await self.performBan(ctx, users, reason)

            # Do this when done
            # send final embed, telling the ban was sucessful
            if not error:
                embed = discord.Embed(title="Accounts banned", color=discord.Color.green(),
                                      description="All the accounts have been globally banned 👌")
                embed.set_image(
                    url="https://cdn.discordapp.com/attachments/456229881064325131/475498849696219141/ban.gif")
            else:
                embed = discord.Embed(title="Banning failed", color=discord.Color.red(),
                                      description="Error: %s" % error)
                embed.set_image(
                    url="https://cdn.discordapp.com/attachments/474313313598046238/689828429318848517/failed.gif")
            embed.set_footer(text="%s - Global WatchDog Moderator" % ctx.author.name,
                             icon_url=ctx.author.avatar_url)
            await embed_message.edit(embed=embed)
        else:
            await ctx.send(
                embed=Embed(color=discord.Color.red(), description="You are not a Global Moderator! Shame!"))


def setup(bot):
    bot.add_cog(Moderation(bot))
