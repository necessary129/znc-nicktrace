#  znc-nicktrace: A ZNC module to track users
#  Copyright (C) 2016 Evan Magaliff
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License along
#  with this program; if not, write to the Free Software Foundation, Inc.,
#  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#  Authors: Evan, Aww (AwwCookies)                                        #
#  Contributors: See CHANGELOG for specific contributions by users        #
#  Desc: A ZNC module to track users                                      #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

version = '1.10.1'
updated = "Feb 15, 2016"

import znc
import os
import socket
import itertools
import datetime
import urllib.request
import shutil
import re
import sqlite3
import json
import collections

import requests

DEFAULT_CONFIG = {
    "DEBUG_MODE": False,
    "NOTIFY_ON_JOIN": False,
    "NOTIFY_ON_JOIN_TIMEOUT": 300, # Seconds
    "NOTIFY_DEFAULT_MODE": "host", # host/nick
    "NOTIFY_ON_MODE": False,
    "NOTIFY_ON_MODERATED": False,
    "PROCESS_CHANNEL_ON_JOIN": False,
    "PROCESS_CHANNELS_ON_LOAD": False,
    "TRACK_SEEN": True
}

class aka(znc.Module):
    module_types = [znc.CModInfo.NetworkModule]
    description = "Tracks users, allowing tracing and history viewing of nicks, hosts, and channels"
    wiki_page = "aka"

    ''' OK '''
    def OnLoad(self, args, message):

        self.TIMEOUTS = {}

        self.USER = self.GetUser().GetUserName()
        self.NETWORK = self.GetNetwork().GetName()

        self.configure()

        self.chan_reg = re.compile('(#\S+)')
        self.who_ignores = []

        if self.nv['PROCESS_CHANNELS_ON_LOAD'] == "FALSE":
            for channel in self.GetNetwork().GetChans():
                self.who_ignores.append(channel)

        self.process_channels()

        return True

    ''' TEST '''
    def OnIRCConnected(self):
        self.process_channels()

    ''' TEST '''
    def OnIRCDisconnected(self):
        for channel in self.GetNetwork().GetChans():
            self.who_ignores.append(channel)

    ''' OK '''
    def process_user(self, host, nick, identity, name, channel, message, joined, quit_msg, quit_type, away_change, away_msg, addedWithoutMsg, raw):
        if self.nv['DEBUG_MODE'] == "TRUE":
            self.PutModule("DEBUG: Adding %s => %s" % (nick, host))

        message = str(message).replace("'","''")

        if channel != None:
            query = "SELECT * FROM users WHERE LOWER(nick) = '%s' AND LOWER(host) = '%s' AND LOWER(channel) = '%s';" % (nick.lower(), host.lower(), channel.lower())
        else:
            query = "SELECT * FROM users WHERE LOWER(nick) = '%s' AND LOWER(host) = '%s';" % (nick.lower(), host.lower())

        self.c.execute(query)
        data = self.c.fetchall()

        query = ''
        if len(data) == 0:
            if addedWithoutMsg:
                if raw:
                    self.c.execute("INSERT INTO users (host, nick, name, channel, identity, processed_time, added) VALUES (?, ?, ?, ?, ?, ?, ?);", (host, nick, name, channel, identity, datetime.datetime.now(), datetime.datetime.now()))
                else:
                    if quit_msg != None:
                        self.c.execute("INSERT INTO users (host, nick, channel, identity, processed_time, quit_msg, quit_time, quit_type, added) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);", (host, nick, channel, identity, datetime.datetime.now(), quit_msg, datetime.datetime.now(), quit_type, datetime.datetime.now()))
                    else:
                        if joined:
                            self.c.execute("INSERT INTO users (host, nick, channel, identity, processed_time, added, join_time) VALUES (?, ?, ?, ?, ?, ?, ?);", (host, nick, channel, identity, datetime.datetime.now(), datetime.datetime.now(), datetime.datetime.now()))
                        else:
                            self.c.execute("INSERT INTO users (host, nick, channel, identity, processed_time, added) VALUES (?, ?, ?, ?, ?, ?);", (host, nick, channel, identity, datetime.datetime.now(), datetime.datetime.now()))
            else:
                self.c.execute("INSERT INTO users (host, nick, channel, seen, message, identity, processed_time) VALUES (?, ?, ?, ?, ?, ?, ?);", (host, nick, channel, datetime.datetime.now(), message, identity, datetime.datetime.now()))

            self.conn.commit()
            self.send_who(nick)
        else:
            if addedWithoutMsg:
                if raw:
                    if not away_change:
                        self.c.execute("UPDATE users SET identity = ?, name = ?, processed_time = ? WHERE LOWER(nick) = ? AND LOWER(host) = ? AND LOWER(channel) = ?;", (identity, name, datetime.datetime.now(), nick.lower(), host.lower(), channel.lower()))
                    else:
                        if away_msg != None:
                            self.c.execute("UPDATE users SET processed_time = ?, away_msg = ?, away_time = ? WHERE LOWER(nick) = ? AND LOWER(host) = ?", (datetime.datetime.now(), away_msg, datetime.datetime.now(), nick.lower(), host.lower()))
                        else:
                            self.c.execute("UPDATE users SET processed_time = ?, back_time = ? WHERE LOWER(nick) = ? AND LOWER(host) = ?", (datetime.datetime.now(), datetime.datetime.now(), nick.lower(), host.lower()))
                else:
                    if quit_msg != None:
                        self.c.execute("UPDATE users SET identity = ?, processed_time = ?, quit_msg = ?, quit_time = ?, quit_type = ? WHERE LOWER(nick) = ? AND LOWER(host) = ? AND LOWER(channel) = ?;", (identity, datetime.datetime.now(), quit_msg, datetime.datetime.now(), quit_type, nick.lower(), host.lower(), channel.lower()))
                    else:
                        if joined:
                            self.c.execute("UPDATE users SET identity = ?, processed_time = ?, join_time = ? WHERE LOWER(nick) = ? AND LOWER(host) = ? AND LOWER(channel) = ?;", (identity, datetime.datetime.now(), datetime.datetime.now(), nick.lower(), host.lower(), channel.lower()))
                        else:
                            self.c.execute("UPDATE users SET identity = ?, processed_time = ? WHERE LOWER(nick) = ? AND LOWER(host) = ? AND LOWER(channel) = ?;", (identity, datetime.datetime.now(), nick.lower(), host.lower(), channel.lower()))
            else:
                self.c.execute("UPDATE users SET seen = ?, message = ?, processed_time = ? WHERE LOWER(nick) = ? AND LOWER(host) = ? AND LOWER(channel) = ?;", (datetime.datetime.now(), message, datetime.datetime.now(), nick.lower(), host.lower(), channel.lower()))

            self.conn.commit()

    ''' OK '''
    def process_moderated(self, op_nick, op_host, op_ident, channel, action, message, offender_nick, offender_host, offender_ident, added):
        if self.nv['DEBUG_MODE'] == True:
            self.PutModule("DEBUG: Adding %s => %s" % (nick, host))

        message = str(message).replace("'","''")

        query = "INSERT INTO moderated VALUES('%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s');" % (op_nick, op_host, channel, action, message, offender_nick, offender_host, added, datetime.datetime.now(), offender_ident, op_ident)
        self.c.execute(query)
        self.conn.commit()

    ''' OK '''
    def process_channels(self):
        chans = self.GetNetwork().GetChans()
        for chan in chans:
            self.send_who(chan)

    ''' OK '''
    def process_server(self, host, nick, server):

        query = "SELECT * FROM servers WHERE LOWER(nick) = '%s' AND LOWER(host) = '%s';" % (nick.lower(), host.lower())

        self.c.execute(query)
        data = self.c.fetchall()

        query = ''
        if len(data) == 0:
            query = "INSERT INTO servers VALUES('%s', '%s', '%s');" % (host, nick, server)
        else:
            query = "UPDATE servers SET server = '%s' WHERE LOWER(nick) = '%s' AND LOWER(host) = '%s';" % (server, nick.lower(), host.lower())

        self.c.execute(query)
        self.conn.commit()

    ''' OK '''
    def send_who(self, proc):
        self.PutIRC("WHO %s" % proc)

    ''' OK '''
    def OnUserRaw(self, line):
        if str(line.s).split()[0] == "WHO":
            if self.chan_reg.match(str(line.s).split()[1]):
                channel = str(line.s).split()[1]
                if channel not in self.who_ignores:
                    self.who_ignores.append(channel)

    ''' OK '''
    def OnRaw(self, message):
        if str(message.s).split()[1] == "352": # on WHO
            channel = str(message.s).split()[3]
            if channel not in self.who_ignores:
                nick = str(message.s).split()[7]
                host = str(message.s).split()[5]
                ident = str(message.s).split()[4]
                server = str(message.s).split()[6]
                name = ' '.join(str(message.s).split()[10:])
                self.process_user(host, nick, ident, name, channel, None, False, None, None, False, None, True, True)
                self.process_server(host, nick, server)
                self.process_who = False
        elif str(message.s).split()[1] == "315": # on End of WHO
            nick = str(message.s).split()[2]
            channel = str(message.s).split()[3]
            if channel in self.who_ignores:
                self.who_ignores.remove(channel)
            if nick in self.who_ignores:
                self.who_ignores.remove(nick)
        elif str(message.s).split()[1] == "311": # on WHOIS
            host = str(message.s).split()[5]
            nick = str(message.s).split()[3]
            ident = str(message.s).split()[4]
            channel = str(message.s).split()[6]
            server = re.sub(':', '', str(message.s).split()[0])
            name = re.sub(':', '', ' '.join(str(message.s).split()[7:]))
            self.process_user(host, nick, ident, name, channel, None, False, None, None, False, None, True, True)
            self.process_server(host, nick, server)
        elif str(message.s).split()[1] == "314": # on WHOWAS
            host = str(message.s).split()[5]
            nick = str(message.s).split()[3]
            server = re.sub(':', '', str(message.s).split()[0])
            name = re.sub(':', '', ' '.join(str(message.s).split()[7:]))
            self.process_user(host, nick, ident, name, channel, None, False, None, None, False, None, True, True)
            self.process_server(host, nick, server)
        elif str(message.s).split()[1] == "JOIN": # on self join
            if self.nv['PROCESS_CHANNEL_ON_JOIN'] == "TRUE":
                join_nick = (str(message).split('!')[0])[1:]
                curr_nick = self.GetNetwork().GetIRCNick().GetNick()
                if join_nick == curr_nick:
                    self.send_who(str(message.s).split()[2])
        elif str(message.s).split()[1] == "AWAY": # on user AWAY
            user = ((message.s).split()[0]).split(":")[1]
            nick = str(user).split("!")[0]
            ident = str((user.split("!")[1])).split("@")[0]
            host = str(user).split("@")[1]
            if len((message.s).split()) < 3:
                self.process_user(host, nick, ident, None, None, None, False, None, None, True, None, True, True)
            else:
                msg = str(message.s).split(":")[2]
                self.process_user(host, nick, ident, None, None, None, False, None, None, True, msg, True, True)

    ''' OK '''
    def OnJoin(self, user, channel):
        self.process_user(user.GetHost(), user.GetNick(), user.GetIdent(), None, channel.GetName(), None, True, None, None, False, None, True, False)

        if self.nv['NOTIFY_ON_JOIN'] == "TRUE" and user.GetNick() != self.GetUser().GetNick():
            if user.GetNick() in self.TIMEOUTS:
                diff = datetime.datetime.now() - self.TIMEOUTS[user.GetNick()]
                if diff.total_seconds() > self.nv['NOTIFY_ON_JOIN_TIMEOUT']:
                    self.PutModule("%s (%s) has joined %s" % (user.GetNick(), user.GetHost(), channel.GetName()))
                    self.cmd_all(user.GetNick(), self.nv['NOTIFY_DEFAULT_MODE'].lower())
                    self.TIMEOUTS[user.GetNick()] = datetime.datetime.now()
            else:
                self.PutModule("%s (%s) has joined %s" % (user.GetNick(), user.GetHost(), channel.GetName()))
                self.cmd_all(user.GetNick(), self.nv['NOTIFY_DEFAULT_MODE'].lower())
                self.TIMEOUTS[user.GetNick()] = datetime.datetime.now()

        self.send_who(user.GetNick())

    ''' OK '''
    def OnNick(self, user, new_nick, channels):
        for chan in channels:
            self.process_user(user.GetHost(), new_nick, user.GetIdent(), None, chan.GetName(), None, False, None, None, False, None, True, False)

    ''' OK '''
    def OnPrivMsg(self, user, message):
        if self.nv["TRACK_SEEN"] == "TRUE":
            self.process_user(user.GetHost(), user.GetNick(), user.GetIdent(), None, 'PRIVMSG', message, False, None, None, False, None, False, False)

    ''' OK '''
    def OnChanMsg(self, user, channel, message):
        if self.nv["TRACK_SEEN"] == "TRUE":
            self.process_user(user.GetHost(), user.GetNick(), user.GetIdent(), None, channel.GetName(), message, False, None, None, False, None, False, False)

    ''' OK '''
    def OnChanAction(self, user, channel, message):
        if self.nv["TRACK_SEEN"] == "TRUE":
            message = "* " + str(message).replace("'","''")
            self.process_user(user.GetHost(), user.GetNick(), user.GetIdent(), None, channel.GetName(), message, False, None, None, False, None, False, False)

    ''' OK '''
    def OnPart(self, user, channel, message):
        if message.startswith("requested by") or message.startswith("Removed by"):
            op_nick = re.sub(":", "", message.split()[2])
            reason = re.sub('\',\s\'', " ", ((re.search('[a-zA-Z]+.*[a-zA-Z](?![^{]*\})', str(message.split()[3:]))).group(0)))
            self.process_moderated(op_nick, None, None, channel, 'rm', reason, user.GetNick(), user.GetHost(), user.GetIdent(), None)
            self.process_user(user.GetHost(), user.GetNick(), user.GetIdent(), None, channel.GetName(), None, False, message, "rm", False, None, True, False)
        else:
            self.process_user(user.GetHost(), user.GetNick(), user.GetIdent(), None, channel.GetName(), None, False, message, "pt", False, None, True, False)

    ''' OK '''
    def OnQuit(self, user, message, channels):

        # (.)(?=Line)

        if re.compile("G(.)(?=Line)").match(message):
            type = "gl"
            self.process_moderated(None, None, None, None, type, message, user.GetNick(), user.GetHost(), user.GetIdent(), None)
        elif re.compile("K(.)(?=Line)").match(message):
            type = "kl"
            self.process_moderated(None, None, None, None, type, message, user.GetNick(), user.GetHost(), user.GetIdent(), None)
        elif re.compile("Z(.)(?=Line)").match(message):
            type = "zl"
            self.process_moderated(None, None, None, None, type, message, user.GetNick(), user.GetHost(), user.GetIdent(), None)
        elif re.compile("Q(.)(?=Line)").match(message):
            type = "ql"
            self.process_moderated(None, None, None, None, type, message, user.GetNick(), user.GetHost(), user.GetIdent(), None)
        elif "Killed" in message:
            type = "kd"
            self.process_moderated(None, None, None, None, type, message, user.GetNick(), user.GetHost(), user.GetIdent(), None)
        else:
            type = "qt"

        for chan in channels:
            self.process_user(user.GetHost(), user.GetNick(), user.GetIdent(), None, chan.GetName(), None, False, message, type, False, None, True, False)

    ''' OK '''
    def OnKick(self, op, offender_nick, channel, message):
        query = "SELECT host, identity, MAX(seen) FROM users WHERE nick = '%s'" % offender_nick
        self.c.execute(query)
        for row in self.c:
            self.on_kick_process(op.GetNick(), op.GetHost(), op.GetIdent(), channel.GetName(), offender_nick, row[0], row[1], message)

    ''' OK '''
    def on_kick_process(self, op_nick, op_host, op_ident, channel, offender_nick, offender_host, offender_ident, message):
        self.process_moderated(op_nick, op_host, op_ident, channel, 'k', message, offender_nick, offender_host, offender_ident, None)
        self.process_user(offender_host, offender_nick, offender_ident, None, channel, None, False, message, "kk", False, None, True, False)
        if self.nv['NOTIFY_ON_MODERATED'] ==  "True":
            self.PutModule("%s (%s) has been kicked from %s by %s (%s). Reason: %s" % (offender_nick, offender_host, channel, op_nick, op_host, message))

    ''' OK '''
    def OnMode(self, op, channel, mode, arg, added, nochange):
        mode = chr(mode)
        if added:
            char = '+'
        else:
            char = '-'

        if mode == "b" or mode == "q":
            self.process_moderated(op.GetNick(), op.GetHost(), op.GetIdent(), channel, mode, None, str(arg).split('!')[0], str(arg).split('@')[1], str((arg).split('@')[0]).split('!')[1], added)

        if (self.nv['NOTIFY_ON_MODE'] == "TRUE" and self.nv['NOTIFY_ON_MODERATED'] == "FALSE") or (self.nv['NOTIFY_ON_MODE'] == "TRUE" and self.nv['NOTIFY_ON_MODERATED'] == "TRUE" and mode != 'b' and mode != 'q'):
            self.PutModule("%s has set mode %s%s %sin %s" % (op, char, mode, arg, channel))
        elif self.nv['NOTIFY_ON_MODERATED'] == "TRUE" and (mode == 'b' or mode == 'q'):
            if added:
                if mode == 'b':
                    mode = 'banned'
                elif mode =='q':
                    mode = 'quieted'
                self.PutModule("%s (%s) has been %s in %s by %s. Reason: %s" % (arg.split('@')[0], arg.split('@')[1], mode, channel, op, arg))
            else:
                if mode == 'b':
                    mode = 'banned'
                elif mode =='q':
                    mode = 'quieted'
                self.PutModule("%s (%s) has been un%s in %s by %s." % (arg.split('@')[0], arg.split('@')[1], mode, channel, op))

    ''' OK '''
    def cmd_all(self, user, type):
        self.cmd_trace(user, type)
        self.cmd_channels(type, user)
        self.cmd_offenses("user", type, user, None)
        self.cmd_geoip(type, user)
        self.cmd_seen(type, type, None, user)
        self.cmd_userinfo(user, type)
        self.PutModule("History for %s %s complete." % (type, user))

    ''' OK '''
    def cmd_trace(self, user, type):
        if type == "nick":
            othertype = "host"
        elif type == "host":
            othertype = "nick"
        elif type == "lasthost":
            type = "host"
            othertype = "nick"
            query = "SELECT host, MAX(processed_time) FROM users WHERE LOWER(nick) = '%s'" % user.lower()
            self.c.execute(query)
            for row in self.c:
                user = row[0]
        query = "SELECT host, nick FROM users WHERE LOWER(%s) = '%s' GROUP BY %s ORDER BY %s;" % (type, user.lower(), othertype, othertype)
        self.c.execute(query)
        data = self.c.fetchall()
        if len(data) > 0:
            if type == "nick":
                total = 0
                host_count = 0
                c2 = self.conn.cursor()
                for row in data:
                    count = 0
                    out = "%s %s was also known as: " % (type.title(), user)
                    query = "SELECT host, nick FROM users WHERE LOWER(host) = '%s' GROUP BY nick ORDER BY nick COLLATE NOCASE;" % row[0].lower()
                    c2.execute(query)
                    for row2 in c2:
                        out += "%s, " % row2[1]
                        count += 1
                    total += count
                    out = out[:-2]
                    out += " (%s)" % row[0]
                    self.PutModule("%s (%s nicks)" % (out, count))
                    host_count += 1
                if host_count > 1:
                    self.PutModule("%s: %s total nick/host combinations" % (user, total))
            elif type == "host":
                count = 0
                out = ''
                for row in data:
                    out += "%s, " % row[1]
                    count += 1
                out = out[:-2]
                self.PutModule("Host %s was also known as: %s (%s nicks)" % (user, out, count))
        else:
            self.PutModule("No history found for %s: %s" % (type, user))

    ''' OK '''
    def cmd_userinfo(self, user, type):
        query = "SELECT host, nick, identity, name, MAX(processed_time), added FROM users WHERE LOWER(%s) = '%s';" % (type, user.lower())

        query = "SELECT host, nick, identity, (SELECT name FROM users WHERE LOWER(%s) = '%s' and name != 'None' and name IS NOT NULL and processed_time = (SELECT MAX(processed_time) FROM users WHERE LOWER(%s) = '%s' and name != 'None' and name IS NOT NULL)) AS name, MAX(processed_time), added from users where LOWER(%s) = '%s' order by processed_time ASC;" % (type, user.lower(), type, user.lower(), type, user.lower())
        self.c.execute(query)
        data = self.c.fetchall()
        if len(data) > 0:
            for row in data:
                if row[0] != None:
                    if row[5] != None:
                        added = row[5].partition('.')[0]
                    else:
                        added = "Unknown"
                    out = "Last known information for %s %s: %s!%s@%s (%s) as of %s (added %s)" % (type, user, row[1], row[2], row[0], row[3], row[4].partition('.')[0], added)

                    c2 = self.c
                    query2 = "SELECT server FROM servers WHERE LOWER(nick) = '%s' AND host ='%s'" % (row[1].lower(), row[0])
                    c2.execute(query2)
                    data2 = self.c.fetchall()
                    for row2 in data2:
                        server = row2[0]
                        ip = socket.gethostbyname(row2[0])

                    geourl = 'http://ip-api.com/json/' + ip + '?fields=country,regionName'
                    loc = requests.get(geourl)
                    loc_json = loc.json()

                    self.PutModule('%s on server %s (%s, %s)' % (out, server, loc_json["regionName"], loc_json["country"]))
                else:
                    self.PutModule("No info found for %s: %s" % (type, user))
        else:
            self.PutModule('%s %s not found.' % (type.title(), user))

    ''' OK '''
    def cmd_channels(self, user_type, user):
        query = "SELECT DISTINCT channel FROM users WHERE LOWER(%s)  = '%s' AND channel IS NOT NULL ORDER BY channel;" % (user_type, user.lower())
        self.c.execute(query)
        data = self.c.fetchall()
        if len(data) > 0:
            count = 0
            out = "%s was found in:" % user
            for chan in data:
                out += " %s" % chan[0]
                count += 1
            self.PutModule("%s (%s channels)" % (out, count))
        else:
            self.PutModule("No channels found for %s: %s" % (user_type, user))

    ''' OK '''
    def cmd_sharedchans(self, user_type, users):
        user_list = ''
        query = "SELECT DISTINCT channel FROM users WHERE ("
        for user in users:
            query += "LOWER(%s) = '%s' OR " % (user_type, user.lower())
            user_list += " %s" % user
        query = query[:-5]
        query += "') AND channel IS NOT NULL GROUP BY channel HAVING COUNT(DISTINCT %s) = %s ORDER BY channel COLLATE NOCASE;" % (user_type, len(users))

        self.c.execute(query)
        data = self.c.fetchall()
        if len(data) > 0:
            count = 0
            out = "Common channels between%s: " % user_list
            for chan in data:
                out += "%s " % chan[0]
                count += 1
            self.PutModule("%s(%s channels)" % (out, count))
        else:
            self.PutModule("No shared channels found for %ss:%s" % (user_type, user_list))

    ''' OK '''
    def cmd_intersect(self, user_type, chans):
        chan_list = ''
        query = "SELECT DISTINCT %s FROM users WHERE " % user_type
        for chan in chans:
            query += "LOWER(channel) = '%s' OR " % chan.lower()
            chan_list += " %s" % chan
        query = query[:-5]
        query += "' GROUP BY nick HAVING COUNT(DISTINCT channel) = %s ORDER BY nick COLLATE NOCASE;" % len(chans)

        self.c.execute(query)
        data = self.c.fetchall()
        if len(data) > 0:
            count = 0
            out = "Shared users between%s: " % chan_list
            for nick in data:
                out += "%s " % nick[0]
                count += 1
            self.PutModule("%s(%s %ss)" % (out, count, user_type))
        else:
            self.PutModule("No common %ss found in channels:%s" % (user_type, chan_list))

    ''' OK '''
    def cmd_seen(self, method, user_type, channel, user):

        server = ''
        ip = ''

        c2 = self.c

        if method == "in":
            if channel == 'PRIVMSG':
                chan = 'Private Message'
            else:
                chan = channel
            query = "SELECT seen, message, host, nick, identity, name, quit_time, quit_msg, away_msg, away_time, back_time FROM users WHERE seen = (SELECT MAX(seen) FROM users WHERE LOWER(%s) = '%s' AND LOWER(channel) = '%s') AND LOWER(%s) = '%s' AND LOWER(channel) = '%s';" % (user_type, user.lower(), channel.lower(), user_type, user.lower(), channel.lower())
            self.c.execute(query)
            data = self.c.fetchall()
            if len(data) > 0:
                for row in data:
                    days, hours, minutes, seconds = self.dt_diff(row[0])
                    out = '%s %s (%s, %s!%s@%s) was last seen in %s ' % (user_type.title(), user, row[5], row[3], row[4], row[2], chan)
                    if days: out += "%s days, " % days
                    if hours: out += "%s hours, " % hours
                    if minutes: out += "%s minutes, " % minutes

                    away_status = ""

                    # seen = 0 , quit_time = 6, quit_msg = 7, away_msg = 8, away_time = 9, back_time = 10
                    if row[6] != None and row[9] != None and row[10] != None:
                        if row[0] > row[6] and row[0] > row[9] and row[0] > row[10]:
                            away_status = "and has not since quit, been away, or returned."
                        elif row[6] > row[0] and row[6] > row[9] and row[6] > row[10]:
                            away_status = "and last quit at %s with message: \"%s\"" % (row[6].partition('.')[0], row[7])
                        elif row[9] > row[0] and row[9] > row[6] and row[9] > row[10]:
                            away_status = "and last went away at %s with message: \"%s\"" % (row[9].partition('.')[0], row[8])
                        elif row[10] > row[0] and row[10] > row[6] and row[10] > row[9]:
                            away_status = "and last returned from away at %s" % row[10].partition('.')[0]
                    elif row[6] != None and row[9] != None and row[10] == None:
                        if row[0] > row[6] and row[0] > row[9]:
                            away_status = "and has not since quit, been away, or returned."
                        elif row[6] > row[0] and row[6] > row[9]:
                            away_status = "and last quit at %s with message: \"%s\"" % (row[6].partition('.')[0], row[7])
                        elif row[9]> row[0] and row[9] > row[6]:
                            away_status = "and last went away at %s with message: \"%s\"" % (row[9].partition('.')[0], row[8])
                    elif row[6] != None and row[9] == None and row[10] != None:
                        if row[0] > row[6] and row[0] > row[10]:
                            away_status = "and has not since quit, been away, or returned."
                        elif row[6] > row[0] and row[6] > row[10]:
                            away_status = "and last quit at %s with message: \"%s\"" % (row[6].partition('.')[0], row[7])
                        elif row[10]> row[0] and row[10] > row[6]:
                            away_status = "and last returned from away at %s" % row[10].partition('.')[0]
                    elif row[6] != None and row[9] == None and row[10] == None:
                        if row[0] > row[6]:
                            away_status = "and has not since quit, been away, or returned."
                        elif row[6] > row[0]:
                            away_status = "and last quit at %s with message: \"%s\"" % (row[6].partition('.')[0], row[7])
                    elif row[6] == None and row[9] != None and row[10] == None:
                        if row[0] > row[9]:
                            away_status = "and has not since quit, been away, or returned."
                        elif row[9] > row[0]:
                            away_status = "and last went away at %s with message: \"%s\"" % (row[9].partition('.')[0], row[8])
                    elif row[6] == None and row[9] == None and row[10] != None:
                        if row[0] > row[10]:
                            away_status = "and has not since quit, been away, or returned."
                        elif row[10] > row[0]:
                            away_status = "and last returned from away at %s" % row[10].partition('.')[0]

                    self.PutModule("%s%s seconds ago saying \"%s\" (%s) %s" % (out, seconds, row[1], row[0].partition('.')[0], away_status))
            else:
                self.PutModule("%s %s has not been seen talking in %s" % (user_type.title(), user, chan))
        elif method == "nick" or method == "host":
            query = "SELECT channel, seen, message, host, nick, identity, name, quit_time, quit_msg, away_msg, away_time, back_time FROM users WHERE seen = (SELECT MAX(seen) FROM users WHERE LOWER(%s) = '%s') AND LOWER(%s) = '%s';" % (method, user.lower(), method, user.lower())
            self.c.execute(query)
            data = self.c.fetchall()
            if len(data) > 0:
                if data[0][0] != None:
                    for row in data:
                        if row[0] == 'PRIVMSG':
                            chan = 'Private Message'
                        else:
                            chan = row[0]
                        days, hours, minutes, seconds = self.dt_diff(row[1])
                        out = '%s %s (%s, %s!%s@%s) was last seen in %s ' % (user_type.title(), user, row[6], row[4], row[5], row[3], chan)
                        if days: out += "%s days, " % days
                        if hours: out += "%s hours, " % hours
                        if minutes: out += "%s minutes, " % minutes

                        away_status = ""

                        # seen = 1 , quit_time = 7, quit_msg = 8, away_msg = 9, away_time = 10, back_time = 11
                        if row[7] != None and row[10] != None and row[11] != None:
                            if row[1] > row[7] and row[1] > row[10] and row[1] > row[11]:
                                away_status = "and has not since quit, been away, or returned."
                            elif row[7] > row[1] and row[7] > row[10] and row[7] > row[11]:
                                away_status = "and last quit at %s with message: \"%s\"" % (row[7].partition('.')[0], row[8])
                            elif row[10] > row[1] and row[10] > row[7] and row[10] > row[11]:
                                away_status = "and last went away at %s with message: \"%s\"" % (row[10].partition('.')[0], row[9])
                            elif row[11] > row[1] and row[11] > row[7] and row[11] > row[10]:
                                away_status = "and last returned from away at %s" % row[11].partition('.')[0]
                        elif row[7] != None and row[10] != None and row[11] == None:
                            if row[1] > row[7] and row[1] > row[10]:
                                away_status = "and has not since quit, been away, or returned."
                            elif row[7] > row[1] and row[7] > row[10]:
                                away_status = "and last quit at %s with message: \"%s\"" % (row[7].partition('.')[0], row[8])
                            elif row[10]> row[1] and row[10] > row[7]:
                                away_status = "and last went away at %s with message: \"%s\"" % (row[10].partition('.')[0], row[9])
                        elif row[7] != None and row[10] == None and row[11] != None:
                            if row[1] > row[7] and row[1] > row[11]:
                                away_status = "and has not since quit, been away, or returned."
                            elif row[7] > row[1] and row[7] > row[11]:
                                away_status = "and last quit at %s with message: \"%s\"" % (row[7].partition('.')[0], row[8])
                            elif row[11]> row[1] and row[11] > row[7]:
                                away_status = "and last returned from away at %s" % row[11].partition('.')[0]
                        elif row[7] != None and row[10] == None and row[11] == None:
                            if row[1] > row[7]:
                                away_status = "and has not since quit, been away, or returned."
                            elif row[7] > row[1]:
                                away_status = "and last quit at %s with message: \"%s\"" % (row[7].partition('.')[0], row[8])
                        elif row[7] == None and row[10] != None and row[11] == None:
                            if row[1] > row[10]:
                                away_status = "and has not since quit, been away, or returned."
                            elif row[10] > row[1]:
                                away_status = "and last went away at %s with message: \"%s\"" % (row[10].partition('.')[0], row[9])
                        elif row[7] == None and row[10] == None and row[11] != None:
                            if row[1] > row[11]:
                                away_status = "and has not since quit, been away, or returned."
                            elif row[11] > row[1]:
                                away_status = "and last returned from away at %s" % row[11].partition('.')[0]

                        self.PutModule("%s%s seconds ago saying \"%s\" (%s) %s" % (out, seconds, row[2], row[1].partition('.')[0], away_status))
            else:
                self.PutModule("%s %s has not been seen talking." % (user_type.title(), user))

    ''' OK '''
    def cmd_offenses(self, method, user_type, user, channel):
        query = ''
        cols = "op_nick, op_host, channel, action, message, offender_nick, offender_host, offender_ident, added, time"
        if method == "user":
            if user_type == "nick":
                query = "SELECT host, nick FROM users WHERE LOWER(nick) = '%s' GROUP BY host ORDER BY host;" % user.lower()
                self.c.execute(query)
                query = "SELECT %s FROM moderated WHERE LOWER(offender_nick) = '%s' OR LOWER(offender_nick) LIKE '%s!%%' OR LOWER(offender_nick) LIKE '%s*%%'" % (cols, user.lower(), user.lower(), user.lower())
                for row in self.c:
                    query +=  " OR LOWER(offender_host) = '%s'" % row[0].lower()
                query += " ORDER BY time;"
            elif user_type == "host":
                query = "SELECT %s FROM moderated WHERE LOWER(offender_host) = '%s' ORDER BY time;" % (cols, user.lower())
        elif method == "channel":
            if user_type == "nick":
                query = "SELECT host, nick FROM users WHERE LOWER(nick) = '%s' GROUP BY host ORDER BY host;" % user.lower()
                self.c.execute(query)
                query = "SELECT %s FROM moderated WHERE channel = '%s' AND (LOWER(offender_nick) = '%s' OR LOWER(offender_nick) LIKE '%s!%%' OR LOWER(offender_nick) LIKE '%s*%%'" % (cols, channel, user.lower(), user.lower(), user.lower())
                for row in self.c:
                    query +=  " OR LOWER(offender_host) = '%s'" % row[0].lower()
                query += ") ORDER BY time;"
            elif user_type == "host":
                query = "SELECT %s FROM moderated WHERE channel = '%s' and LOWER(offender_host) = '%s' ORDER BY time;" % (cols, channel, user.lower())
        self.c.execute(query)
        data = self.c.fetchall()
        if len(data) > 0:
            count = 0
            for op_nick, op_host, channel, action, message, offender_nick, offender_host, offender_ident, added, time in data:
                count += 1
                if user_type == "nick":
                    offender = offender_host
                elif user_type == "host":
                    offender = offender_nick
                if action == 'b' or action == 'q':
                    if action == 'b':
                        action = 'banned'
                    elif action =='q':
                        action = 'quieted'
                    if added == '0':
                        action = "un%s" % action
                    self.PutModule("%s %s (%s!%s@%s) was %s from %s by %s on %s." % (user_type.title(), user, offender_nick, offender_ident, offender_host, action, channel, op_nick, time.partition('.')[0]))
                elif action == "k" or action == "rm":
                    if action == "k":
                        action = "kicked"
                    elif action =="rm":
                        action = "removed"
                    self.PutModule("%s %s (%s!%s@%s) was %s from %s by %s on %s. Reason: %s" % (user_type.title(), user, offender_nick, offender_ident, offender_host, action, channel, op_nick, time.partition('.')[0], message))
                elif action == "gl" or action == "kl" or action == "zl" or action == "ql" or action == "kd":
                    if action == "gl":
                        action = "G-Lined"
                    elif action == "kl":
                        action = "K-Lined"
                    elif action == "zl":
                        action = "Z-Lined"
                    elif action == "ql":
                        action = "Q-Lined"
                    elif action == "kd":
                        action = "killed"

                    self.PutModule("%s %s (%s) was %s on %s. Reason: %s" % (user_type.title(), user, offender_host, action, time.partition('.')[0], message))

            if method == "user":
                self.PutModule("%s %s: %s total offenses." % (user_type.title(), user, count))
            elif method == "channel":
                self.PutModule("%s %s: %s total offenses in %s." % (user_type.title(), user, count, channel))
        else:
            if method == "channel":
                self.PutModule("No offenses found for %s: %s in %s" % (user_type, user, channel))
            else:
                self.PutModule("No offenses found for %s: %s" % (user_type, user))

    ''' OK '''
    def cmd_geoip(self, method, user):
        if method == "host":
            self.geoip_process(user, user, "host")
        elif method == "nick":
            query = "SELECT host, MAX(processed_time) FROM users WHERE nick = '%s'" % user
            self.c.execute(query)
            for row in self.c:
                self.geoip_process(row[0], user, "nick")

    ''' OK '''
    def geoip_process(self, host, nick, method):
        ipv4 = '(?:[0-9]{1,3}(\.|\-)){3}[0-9]{1,3}'
        ipv6 = '^((?:[0-9A-Fa-f]{1,4}))((?::[0-9A-Fa-f]{1,4}))*::((?:[0-9A-Fa-f]{1,4}))((?::[0-9A-Fa-f]{1,4}))*|((?:[0-9A-Fa-f]{1,4}))((?::[0-9A-Fa-f]{1,4})){7}$'
        rdns = '^(([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9])\.)*([A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9\-]*[A-Za-z0-9])$'

        if host == None:
            self.PutModule("%s %s not found." % (method.title(), nick))
        elif (re.search(ipv6, str(host)) or re.search(ipv4, str(host)) or (re.search(rdns, str(host)) and '.' in str(host))):
            if re.search(ipv4, str(host)):
                ip = re.sub('[^\w.]',".",((re.search(ipv4, str(host))).group(0)))
            elif re.search(ipv6, str(host)) or re.search(rdns, str(host)):
                ip = str(host)
            url = 'http://ip-api.com/json/' + ip + '?fields=country,regionName,city,lat,lon,timezone,mobile,proxy,query,reverse,status,message'
            loc = requests.get(url)
            loc_json = loc.json()

            if method == "nick":
                other = ' (%s)' % host
            else:
                other = ''

            if loc_json["status"] != "fail":
                self.PutModule("%s %s%s is located in %s, %s, %s (%s, %s) / Timezone: %s / Proxy: %s / Mobile: %s / IP: %s %s" % (method.title(), nick, other, loc_json["city"], loc_json["regionName"], loc_json["country"], loc_json["lat"], loc_json["lon"], loc_json["timezone"], loc_json["proxy"], loc_json["mobile"], loc_json["query"], loc_json["reverse"]))
            else:
                self.PutModule("Unable to geolocate %s %s. (Reason: %s)" % (method, nick, loc_json["message"]))
        else:
            self.PutModule("Invalid host for geolocation (%s)" % host)

    ''' OK '''
    def cmd_add(self, nick, host, ident, channel):
        self.process_user(host, nick, ident, channel, None, False, False, None, False, False)
        self.PutModule("%s => %s" % (nick, host, channel))

    ''' OK '''
    def cmd_rawquery(self, query):
        try:
            query = ' '.join(query)
            count = 0
            for row in self.c.execute(query):
                self.PutModule(str(row))
                count += 1
            self.conn.commit()
            if self.c.rowcount >= 0:
                self.PutModule('Query successful: %s rows affected' % self.c.rowcount)
            else:
                if count == 0:
                    self.PutModule('No records found')
                else:
                    self.PutModule('%s records retrieved' % count)
        except sqlite3.Error as e:
            self.PutModule('Error: %s' % e)

    ''' OK '''
    def cmd_about(self):
        self.PutModule("aka nick tracking module by Evan (Evan) and AwwCookies (Aww) - http://wiki.znc.in/Aka")

    ''' OK '''
    def cmd_version(self):
        self.PutModule("Version: %s (%s)" % (version, updated))

    ''' OK '''
    def cmd_stats(self):
        self.c.execute('SELECT COUNT(DISTINCT nick), COUNT(DISTINCT host), COUNT(DISTINCT channel) FROM users;')
        for row in self.c:
            self.PutModule("Nicks: %s" % row[0])
            self.PutModule("Hosts: %s" % row[1])
            self.PutModule("Channels: %s" % row[2])

    ''' OK '''
    def OnModCommand(self, command):
        # Valid Commands
        type = None
        cmds = ["all", "trace", "userinfo", "sharedchans", "channels", "intersect", "seen", "offenses", "geoip", "process", "help", "config", "getconfig", "about", "add", "dbimport", "import", "export", "rawquery", "version", "stats", "update"]
        if command.split()[0] in cmds:
            if command.split()[0] == "all":
                options = ["nick", "host"]
                if command.split()[1] in options:
                    self.cmd_all(command.split()[2], command.split()[1])
                else:
                    self.PutModule("Invalid command. Valid options for ALL: nick, host")
            elif command.split()[0] == "trace":
                options = ["nick", "host","lasthost"]
                if command.split()[1] in options:
                    if command.split()[1] == "nick": # nick $nick
                        self.cmd_trace(command.split()[2], "nick")
                    elif command.split()[1] == "host": # host $host
                        self.cmd_trace(command.split()[2], "host")
                    elif command.split()[1] == "lasthost":
                        self.cmd_trace(command.split()[2], "lasthost")
                    else:
                        self.PutModule("Invalid command. Valid options for TRACE: nick, host, lasthost")
            elif command.split()[0] == "userinfo": # userinfo
                options = ["nick", "host"]
                if command.split()[1] in options:
                    self.cmd_userinfo(command.split()[2], command.split()[1])
                else:
                    self.PutModule("Invalid command. Valid options for USERINFO: nick, host")
            elif command.split()[0] == "sharedchans":
                options = ["nicks", "hosts"]
                if command.split()[1] in options:
                    if command.split()[1] == "nicks":
                        type = "nick"
                    elif command.split()[1] == "hosts":
                        type = "host"
                    self.cmd_sharedchans(type, list(command.split()[2:]))
                else:
                    self.PutModule("Invalid command. Valid options for SHAREDCHANS: nicks, hosts")
            elif command.split()[0] == "intersect":
                options = ["nicks", "hosts"]
                if command.split()[1] in options:
                    if command.split()[1] == "nicks":
                        type = "nick"
                    elif command.split()[1] == "hosts":
                        type = "host"
                    self.cmd_intersect(type, command.split()[2:])
                else:
                    self.PutModule("Invalid command. Valid options for INTERSECT: nicks, hosts")
            elif command.split()[0] == "channels":
                options = ["nick", "host"]
                if command.split()[1] in options:
                    self.cmd_channels(command.split()[1], command.split()[2])
                else:
                    self.PutModule("Invalid command. Valid options for CHANNELS: nick, host")
            elif command.split()[0] == "seen":
                options = ["in", "nick", "host"]
                if command.split()[1] in options:
                    if command.split()[1] == "nick" or command.split()[1] == "host":
                        self.cmd_seen(command.split()[1], command.split()[1], None, command.split()[2])
                    elif command.split()[1] == "in":
                        options = ["nick", "host"]
                        if command.split()[2] in options:
                            self.cmd_seen(command.split()[1], command.split()[2], command.split()[3], command.split()[4])
                        else:
                            self.PutModule("Invalid command. Valid options for SEEN IN: nick, host")
                    else:
                        self.PutModule("Invalid command. Valid options for SEEN: in, nick, host")
                else:
                    self.PutModule(command.split()[0] + " " + command.split()[1] + " is not a valid command.")
            elif command.split()[0] == "offenses":
                options = ["in", "nick", "host"]
                if command.split()[1] in options:
                    if command.split()[1] == "nick":
                        self.cmd_offenses("user", "nick", command.split()[2], None)
                    elif command.split()[1] == "host":
                        self.cmd_offenses("user", "host", command.split()[2], None)
                    elif command.split()[1] == "in":
                        if command.split()[2] == "nick":
                            self.cmd_offenses("channel", "nick", command.split()[4], command.split()[3])
                        elif command.split()[2] == "host":
                            self.cmd_offenses("channel", "host", command.split()[4], command.split()[3])
                        else:
                            self.PutModule("Invalid command. Valid options for OFFENSES IN: nick, host")
                else:
                    self.PutModule("Invalid command. Valid options for OFFENSES: in, nick, host")
            elif command.split()[0] == "geoip":
                options = ["nick", "host"]
                if command.split()[1] in options:
                    self.cmd_geoip(command.split()[1], command.split()[2])
                else:
                    self.PutModule("Invalid command. Valid options for GEOIP: nick, host")
            elif command.split()[0] == "process":
                options = ["all", "channel", "nick"]
                if command.split()[1] in options:
                    if command.split()[1] == "all":
                        self.process_channels()
                        self.PutModule("Processing all channels on network.")
                    else:
                        self.send_who(command.split()[2])
                        self.PutModule("%s %s processed." % (command.split()[1].title(), command.split()[2]))
                else:
                    self.PutModule("Invalid command. Valid options for PROCESS: all, channel, nick")
            elif command.split()[0] == "about":
                self.cmd_about()
            elif command.split()[0] == "config":
                self.cmd_config(command.split()[1], command.split()[2])
            elif command.split()[0] == "getconfig":
                self.cmd_getconfig()
            elif command.split()[0] == "add":
                self.cmd_add(command.split()[1], command.split()[2], command.split()[3], command.split()[4])
            elif command.split()[0] == "help":
                self.cmd_help()
            elif command.split()[0] == "dbimport":
                self.cmd_import_db(command.split()[1])
            elif command.split()[0] == "import":
                self.cmd_import_json(command.split()[1])
            elif command.split()[0] == "export":
                options = ["nick", "host"]
                if command.split()[1] in options:
                    self.cmd_export_json(command.split()[2], command.split()[1])
                else:
                    self.PutModule("Invalid command. Valid options for EXPORT: nick, host")
            elif command.split()[0] == "rawquery":
                self.cmd_rawquery(command.split()[1:])
            elif command.split()[0] == "version":
                self.cmd_version()
            elif command.split()[0] == "stats":
                self.cmd_stats()
            elif command.split()[0] == "update":
                self.cmd_update()
        else:
            self.PutModule("Invalid command. See HELP for details.")

    ''' OK '''
    def dt_diff(self, td):
        time = td.split('.', 1)[0]
        then = datetime.datetime.strptime(time, "%Y-%m-%d %H:%M:%S")
        now = datetime.datetime.now()
        diff = now - then
        days = diff.days
        hours = diff.seconds//3600
        minutes = (diff.seconds//60)%60
        seconds = diff.seconds % 60
        return days, hours, minutes, seconds

    ''' OK'''
    def cmd_getconfig(self):
        for key, value in self.nv.items():
            self.PutModule("%s = %s" % (key, value))

    ''' OK '''
    def cmd_config(self, var_name, value):
        valid = True
        bools = ["DEBUG_MODE", "TRACK_SEEN", "NOTIFY_ON_JOIN", "NOTIFY_ON_MODE", "NOTIFY_ON_MODERATED", "PROCESS_CHANNEL_ON_JOIN", "PROCESS_CHANNELS_ON_LOAD"]
        if var_name.upper() in bools:
            if not str(value).upper() == "TRUE" and not str(value).upper() == "FALSE":
                valid = False
                self.PutModule("%s must be either True or False" % var_name)
        elif var_name == "NOTIFY_ON_JOIN_TIMEOUT":
            if not int(value) >= 1:
                valid = False
                self.PutModule("You must use an integer value larger than 0")
        elif var_name == "NOTIFY_DEFAULT_MODE":
            if not str(value) in ["nick", "host"]:
                valid = False
                self.PutModule("Valid mode options are 'nick' and 'host'")
        else:
            valid = False
            self.PutModule("%s is not a valid setting." % var_name)

        if valid:
            self.SetNV(str(var_name).upper(), str(value).upper(), True)
            self.PutModule("%s => %s" % (var_name.upper(), value.upper()))

    ''' OK '''
    def cmd_update(self):
        if self.GetUser().IsAdmin():
            new_version = urllib.request.urlopen("https://raw.githubusercontent.com/emagaliff/znc-nicktrace/master/aka.py")
            with open(self.GetModPath(), 'w') as f:
                f.write(new_version.read().decode('utf-8'))
                self.PutModule('aka successfully updated. Please use "/msg *status updatemod aka" to reload aka for all users and networks')
        else:
            self.PutModule("You must be an administrator to update this module.")

    ''' OK '''
    def configure(self):

        if os.path.exists(znc.CUser(self.USER).GetUserPath() + "/networks/" + self.NETWORK + "/moddata/Aka"):
            os.rename(znc.CUser(self.USER).GetUserPath() + "/networks/" + self.NETWORK + "/moddata/Aka", self.GetSavePath())

        self.db_setup()

        self.old_MODFOLDER = znc.CUser(self.USER).GetUserPath() + "/moddata/Aka/"

        if os.path.exists(self.old_MODFOLDER + "config.json") and not os.path.exists(self.GetSavePath() + "/hosts.json"):
            shutil.move(self.old_MODFOLDER + "config.json", self.GetSavePath() + "/config.json")
        if os.path.exists(self.old_MODFOLDER + self.NETWORK + "_hosts.json"):
            shutil.move(self.old_MODFOLDER + self.NETWORK + "_hosts.json", self.GetSavePath() + "/hosts.json")
        if os.path.exists(self.old_MODFOLDER + self.NETWORK + "_chans.json"):
            shutil.move(self.old_MODFOLDER + self.NETWORK + "_chans.json", self.GetSavePath() + "/chans.json")
        if os.path.exists(self.GetSavePath() + "/config.json"):
            CONFIG = json.loads(open(self.GetSavePath() + "/config.json").read())
            for default in DEFAULT_CONFIG:
                if default not in CONFIG:
                    CONFIG[default] = DEFAULT_CONFIG[default]
            new_config = {}
            for setting in CONFIG:
                if setting in DEFAULT_CONFIG:
                    new_config[setting] = CONFIG[setting]
            CONFIG = new_config
            with open(self.GetSavePath() + "/config.json", 'w') as f:
                f.write(json.dumps(new_config, sort_keys=True, indent=4))

            for setting in CONFIG:
                if CONFIG.get(setting) == 1:
                    self.SetNV(setting, "TRUE", True)
                elif CONFIG.get(setting) == 0:
                    self.SetNV(setting, "FALSE", True)
                else:
                    self.SetNV(setting.upper(), str(CONFIG[setting]).upper(), True)

            os.remove(self.GetSavePath() + "/config.json")

        elif not os.path.exists(self.GetSavePath() + "/.registry"):
            for setting in DEFAULT_CONFIG:
                self.SetNV(setting.upper(), str(DEFAULT_CONFIG[setting]).upper(), True)

        elif os.path.exists(self.GetSavePath() + "/.registry"):
            for setting in DEFAULT_CONFIG:
                if setting not in self.nv:
                    self.SetNV(setting.upper(), str(DEFAULT_CONFIG[setting]).upper(), True)
            for setting in self.nv:
                if self.nv[setting] != self.nv[setting].upper():
                    self.SetNV(setting.upper(), self.nv[setting].upper(), True)


        if os.path.exists(self.GetSavePath() + "/hosts.json") and os.path.exists (self.GetSavePath() + "/hosts.json"):

            self.PutModule("aka needs to migrate your data to the new database format. Your data has been backed up. This may take a few minutes and will only happen once.")

            chans = {}
            chans = json.loads(open(self.GetSavePath() + "/chans.json", 'r').read())

            for chan in chans:
                for user in chans[chan]:
                    query = "INSERT OR IGNORE INTO users (host, nick, channel) VALUES ('%s', '%s', '%s');" % (user[1], user[0], chan)
                    self.c.execute(query)
                del user
            del chans[chan]
            self.conn.commit()

            hosts = {}
            hosts = json.loads(open(self.GetSavePath() + "/hosts.json", 'r').read())
            for host in hosts:
                for nick in hosts[host]:
                        query = "INSERT OR IGNORE INTO users (host, nick) VALUES ('%s', '%s');" % (host, nick)
                        self.c.execute(query)
                del nick
            del hosts[host]
            self.conn.commit()

            self.c.execute("VACUUM")

            shutil.move(self.GetSavePath() + "/hosts.json", self.GetSavePath() + "/hosts_processed.json")
            shutil.move(self.GetSavePath() + "/chans.json", self.GetSavePath() + "/chans_processed.json")

            self.PutModule("Data migration complete.")

    ''' OK '''
    def db_setup(self):
        self.conn = sqlite3.connect(self.GetSavePath() + "/aka." + self.NETWORK + ".db")
        self.c = self.conn.cursor()
        self.c.execute("create table if not exists users (host, nick, channel, seen, message, identity, processed_time, name, quit_msg, quit_time, quit_type, added, away_msg, away_time, back_time, join_time, UNIQUE(host COLLATE NOCASE, nick COLLATE NOCASE, channel COLLATE NOCASE));")
        self.c.execute("create table if not exists moderated (op_nick, op_host, channel, action, message, offender_nick, offender_host, added, time, offender_ident, op_ident)")
        self.c.execute("create table if not exists servers (host, nick, server, UNIQUE(host COLLATE NOCASE, nick COLLATE NOCASE));")

        ''' ADDITIONAL TABLES '''
        self.c.execute("PRAGMA table_info(users);")
        exists = False
        for table in self.c:
            if str(table[1]) == 'message':
                exists = True
        if exists == False:
            self.c.execute("ALTER TABLE users ADD COLUMN message;")

        self.c.execute("PRAGMA table_info(users);")
        exists = False
        for table in self.c:
            if str(table[1]) == 'identity':
                exists = True
        if exists == False:
            self.c.execute("ALTER TABLE users ADD COLUMN identity;")

        self.c.execute("PRAGMA table_info(users);")
        exists = False
        for table in self.c:
            if str(table[1]) == 'name':
                exists = True
        if exists == False:
            self.c.execute("ALTER TABLE users ADD COLUMN name;")

        self.c.execute("PRAGMA table_info(users);")
        exists = False
        for table in self.c:
            if str(table[1]) == 'processed_time':
                exists = True
        if exists == False:
            self.c.execute("ALTER TABLE users ADD COLUMN processed_time;")

        self.c.execute("PRAGMA table_info(users);")
        exists = False
        for table in self.c:
            if str(table[1]) == 'quit_msg':
                exists = True
        if exists == False:
            self.c.execute("ALTER TABLE users ADD COLUMN quit_msg;")
            self.c.execute("ALTER TABLE users ADD COLUMN quit_time;")
            self.c.execute("ALTER TABLE users ADD COLUMN quit_type;")

        self.c.execute("PRAGMA table_info(users);")
        exists = False
        for table in self.c:
            if str(table[1]) == 'added':
                exists = True
        if exists == False:
            self.c.execute("ALTER TABLE users ADD COLUMN added;")

        self.c.execute("PRAGMA table_info(users);")
        exists = False
        for table in self.c:
            if str(table[1]) == 'away_msg':
                exists = True
        if exists == False:
            self.c.execute("ALTER TABLE users ADD COLUMN away_msg;")
            self.c.execute("ALTER TABLE users ADD COLUMN away_time;")
            self.c.execute("ALTER TABLE users ADD COLUMN back_time;")

        self.c.execute("PRAGMA table_info(users);")
        exists = False
        for table in self.c:
            if str(table[1]) == 'join_time':
                exists = True
        if exists == False:
            self.c.execute("ALTER TABLE users ADD COLUMN join_time;")

        self.c.execute("PRAGMA table_info(moderated);")
        exists = False
        for table in self.c:
            if str(table[1]) == 'offender_ident':
                exists = True
        if exists == False:
            self.c.execute("ALTER TABLE moderated ADD COLUMN offender_ident;")

        self.c.execute("PRAGMA table_info(moderated);")
        exists = False
        for table in self.c:
            if str(table[1]) == 'op_ident':
                exists = True
        if exists == False:
            self.c.execute("ALTER TABLE moderated ADD COLUMN op_ident;")

        self.c.execute("PRAGMA table_info(moderated);")
        exists = False
        for table in self.c:
            if str(table[1]) == 'identity':
                exists = True
        if exists == True:
            self.c.execute("BEGIN TRANSACTION")
            self.c.execute("CREATE TEMPORARY TABLE mod_backup(op_nick, op_host, channel, action, message, offender_nick, offender_host, added, time, offender_ident, op_ident)")
            self.c.execute("INSERT INTO mod_backup SELECT op_nick, op_host, channel, action, message, offender_nick, offender_host, added, time, offender_ident, op_ident FROM moderated")
            self.c.execute("DROP TABLE moderated")
            self.c.execute("CREATE TABLE moderated(op_nick, op_host, channel, action, message, offender_nick, offender_host, added, time, offender_ident, op_ident)")
            self.c.execute("INSERT INTO moderated SELECT op_nick, op_host, channel, action, message, offender_nick, offender_host, added, time, offender_ident, op_ident FROM mod_backup")
            self.c.execute("DROP TABLE mod_backup")
            self.c.execute("COMMIT")
            self.conn.commit()

    ''' TO TEST '''
    def cmd_import_db(self, file):

        self.PutModule("Importing %s..." % file)

        imp_conn = sqlite3.connect(self.GetSavePath() + "/" + file)
        imp_c = imp_conn.cursor()

        imp_query = "SELECT host, nick, channel, seen, message, identity, processed_time FROM users"
        imp_c.execute(imp_query)

        self.PutModule("Importing users...")
        for row in imp_c:
            self.c.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?, ?, ?, ?);", (row[0], row[1], row[2], row[3], row[4], row[5], row[6]))
        self.PutModule("Users imported.")

        imp_query = "SELECT op_nick, op_host, channel, action, message, offender_nick, offender_host, added, time, offender_ident, op_ident FROM moderated"
        imp_c.execute(imp_query)

        self.PutModule("Importing moderated...")
        for row in imp_c:
            self.c.execute("INSERT OR IGNORE INTO moderated VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);", (row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9], row[10]))
        self.PutModule("Moderated imported.")

        imp_query = "SELECT host, nick, server FROM servers"
        imp_c.execute(imp_query)

        self.PutModule("Importing servers.")
        for row in imp_c:
            self.c.execute("INSERT OR IGNORE INTO servers VALUES (?, ?, ?);", (row[0], row[1], row[2]))
        self.PutModule("Servers imported...")

        self.conn.commit()

        self.PutModule("%s imported successfully." % file)

    ''' OK '''
    def cmd_import_json(self, url):
        count = 0
        json_object = json.loads(requests.get(url).text)
        for user in json_object:
            query = "INSERT OR IGNORE INTO users (host, nick) VALUES ('%s', '%s');" % (user["host"], user["nick"])
            self.c.execute(query)
            count += 1
        self.conn.commit()
        self.PutModule("%s users imported successfully." % count)

    ''' OK '''
    def cmd_export_json(self, user, type):
        if type == "host":
            subtype = "nick"
        elif type == "nick":
            subtype = "host"
        result_array = []
        query = "SELECT nick, host FROM users WHERE LOWER(%s) = '%s' GROUP BY %s" % (type, user.lower(), subtype)
        self.c.execute(query)
        if type == "nick":
            for row in self.c:
                c2 = self.conn.cursor()
                query2 = "SELECT nick, host FROM users WHERE LOWER(%s) = '%s' GROUP BY %s" % (subtype, row[1].lower(), type)
                c2.execute(query2)
                for row2 in c2:
                    d = collections.OrderedDict()
                    d["nick"] = row2[0]
                    d["host"] = row2[1]
                    result_array.append(d)
        elif type == "host":
            for row in self.c:
                d = collections.OrderedDict()
                d["nick"] = row[0]
                d["host"] = row[1]
                result_array.append(d)

        user = str(user).replace("/",".")

        with open(self.GetSavePath() + "/" + user + ".json", 'w') as f:
            f.write(json.dumps(result_array, sort_keys = True, indent = 4))

        self.PutModule("Exported file saved to: " + self.GetSavePath() + "/" + user + ".json")

    ''' OK '''
    def cmd_help(self):
        help = znc.CTable(250)
        help.AddColumn("Command")
        help.AddColumn("Arguments")
        help.AddColumn("Description")
        help.AddRow()
        help.SetCell("Command", "all nick")
        help.SetCell("Arguments", "<nick>")
        help.SetCell("Description", "Perform complete lookup on nick")
        help.AddRow()
        help.SetCell("Command", "all host")
        help.SetCell("Arguments", "<host>")
        help.SetCell("Description", "Perform complete lookup on host")
        help.AddRow()
        help.SetCell("Command", "trace nick")
        help.SetCell("Arguments", "<nick>")
        help.SetCell("Description", "Show nick change and host history for given nick")
        help.AddRow()
        help.SetCell("Command", "trace host")
        help.SetCell("Arguments", "<host>")
        help.SetCell("Description", "Show nick history for given host")
        help.AddRow()
        help.SetCell("Command", "trace lasthost")
        help.SetCell("Arguments", "<nick>")
        help.SetCell("Description", "Show host history for last known host of given nick")
        help.AddRow()
        help.SetCell("Command", "userinfo nick")
        help.SetCell("Arguments", "<nick>")
        help.SetCell("Description", "Show last known information for given nick")
        help.AddRow()
        help.SetCell("Command", "userinfo host")
        help.SetCell("Arguments", "<host>")
        help.SetCell("Description", "Show last known information for given host")
        help.AddRow()
        help.SetCell("Command", "sharedchans nicks")
        help.SetCell("Arguments", "<nick1> <nick2> ... <nick#>")
        help.SetCell("Description", "Show common channels between a list of nicks")
        help.AddRow()
        help.SetCell("Command", "sharedchans hosts")
        help.SetCell("Arguments", "<host1> <host2> ... <host#>")
        help.SetCell("Description", "Show common channels between a list of hosts")
        help.AddRow()
        help.SetCell("Command", "intersect nicks")
        help.SetCell("Arguments", "<#channel1> <#channel2> ... <#channel#>")
        help.SetCell("Description", "Display nicks common to a list of channels")
        help.AddRow()
        help.SetCell("Command", "intersect hosts")
        help.SetCell("Arguments", "<#channel1> <#channel2> ... <#channel#>")
        help.SetCell("Description", "Display hosts common to a list of channels")
        help.AddRow()
        help.SetCell("Command", "channels nick")
        help.SetCell("Arguments", "<nick>")
        help.SetCell("Description", "Get all channels a nick has been seen in")
        help.AddRow()
        help.SetCell("Command", "channels host")
        help.SetCell("Arguments", "<host>")
        help.SetCell("Description", "Get all channels a host has been seen in")
        help.AddRow()
        help.SetCell("Command", "offenses nick")
        help.SetCell("Arguments", "<nick>")
        help.SetCell("Description", "Display moderation history for nick")
        help.AddRow()
        help.SetCell("Command", "offenses host")
        help.SetCell("Arguments", "<host>")
        help.SetCell("Description", "Display moderation history for host")
        help.AddRow()
        help.SetCell("Command", "offenses in nick")
        help.SetCell("Arguments", "<#channel> <nick>")
        help.SetCell("Description", "Display moderation history for nick in channel")
        help.AddRow()
        help.SetCell("Command", "offenses in channel")
        help.SetCell("Arguments", "<#channel> <host>")
        help.SetCell("Description", "Display moderation history for host in channel")
        help.AddRow()
        help.SetCell("Command", "seen nick")
        help.SetCell("Arguments", "<nick>")
        help.SetCell("Description", "Display last time nick was seen speaking")
        help.AddRow()
        help.SetCell("Command", "seen host")
        help.SetCell("Arguments", "<host>")
        help.SetCell("Description", "Display last time host was seen speaking")
        help.AddRow()
        help.SetCell("Command", "seen in nick")
        help.SetCell("Arguments", "<#channel> <nick>")
        help.SetCell("Description", "Display last time nick was seen speaking in channel")
        help.AddRow()
        help.SetCell("Command", "seen in host")
        help.SetCell("Arguments", "<#channel> <host>")
        help.SetCell("Description", "Display last time host was seen speaking in channel")
        help.AddRow()
        help.SetCell("Command", "geoip nick")
        help.SetCell("Arguments", "<nick>")
        help.SetCell("Description", "Geolocates nick")
        help.AddRow()
        help.SetCell("Command", "geoip host")
        help.SetCell("Arguments", "<host>")
        help.SetCell("Description", "Geolocates host")
        help.AddRow()
        help.SetCell("Command", "process all")
        help.SetCell("Arguments", "")
        help.SetCell("Description", "Processes all channels")
        help.AddRow()
        help.SetCell("Command", "process channel")
        help.SetCell("Arguments", "<#channel>")
        help.SetCell("Description", "Processes a given channel")
        help.AddRow()
        help.SetCell("Command", "process nick")
        help.SetCell("Arguments", "<nick>")
        help.SetCell("Description", "Processes a given nick")
        help.AddRow()
        help.SetCell("Command", "add")
        help.SetCell("Arguments", "<nick> <host> <#channel>")
        help.SetCell("Description", "Manually add a nick/host entry to the database")
        help.AddRow()
        help.SetCell("Command", "rawquery")
        help.SetCell("Arguments", "<query>")
        help.SetCell("Description", "Run raw sqlite3 query")
        help.AddRow()
        help.SetCell("Command", "dbimport")
        help.SetCell("Arguments", "<filename.db>")
        help.SetCell("Description", "Imports entire aka db from another user")
        help.AddRow()
        help.SetCell("Command", "import")
        help.SetCell("Arguments", "<url>")
        help.SetCell("Description", "Imports user data to DB from valid JSON file URL")
        help.AddRow()
        help.SetCell("Command", "export nick")
        help.SetCell("Arguments", "<nick>")
        help.SetCell("Description", "Exports nick data to JSON file")
        help.AddRow()
        help.SetCell("Command", "export host")
        help.SetCell("Arguments", "<host>")
        help.SetCell("Description", "Exports host data to JSON file")
        help.AddRow()
        help.SetCell("Command", "config")
        help.SetCell("Arguments", "<variable> <value>")
        help.SetCell("Description", "Set configuration variables per network (See README)")
        help.AddRow()
        help.SetCell("Command", "getconfig")
        help.SetCell("Description", "Print the current network configuration")
        help.AddRow()
        help.SetCell("Command", "about")
        help.SetCell("Description", "Display information about aka")
        help.AddRow()
        help.SetCell("Command", "stats")
        help.SetCell("Description", "Print nick and host stats for the network")
        help.AddRow()
        help.SetCell("Command", "update")
        help.SetCell("Description", "updates aka to latest version")
        help.AddRow()
        help.SetCell("Command", "help")
        help.SetCell("Description", "Print help from the module")

        self.PutModule(help)
