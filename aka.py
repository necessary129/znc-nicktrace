#    znc-nicktrace: A ZNC module to track users
#    Copyright (C) 2015 Evan Magaliff
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License along
#    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#   Authors: MuffinMedic (Evan), Aww (AwwCookies)                 #
#   Last Update: Nov 18, 2015                                     #
#   Version: 1.0.9                                                #
#   Desc: A ZNC module to track users                             #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

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

version = '1.0.9'
updated = "Nov 18, 2015"

DEFAULT_CONFIG = {
    "DEBUG_MODE": False,
    "NOTIFY_ON_JOIN": False,
    "NOTIFY_ON_JOIN_TIMEOUT": 300, # Seconds
    "NOTIFY_DEFAULT_MODE": "host", # host/nick
    "NOTIFY_ON_MODE": False,
    "NOTIFY_ON_MODERATED": False,
    "PROCESS_CHANNEL_ON_JOIN": False,
    "PROCESS_CHANNELS_ON_LOAD": False
}

class aka(znc.Module):
    module_types = [znc.CModInfo.NetworkModule]
    description = "Tracks users, allowing tracing and history viewing of nicks, hosts, and channels"
    wiki_page = "aka"

    ''' OK '''
    def OnLoad(self, args, message):

        self.raw_hold = {}
        self.TIMEOUTS = {}

        self.USER = self.GetUser().GetUserName()
        self.NETWORK = self.GetNetwork().GetName()

        self.configure()

        if self.nv['PROCESS_CHANNELS_ON_LOAD'] == "TRUE":
            self.process_channels()

        return True

    ''' OK '''
    def process_user(self, host, nick, identity, channel, message, addedWithoutMsg):
        if self.nv['DEBUG_MODE'] == "TRUE":
            self.PutModule("DEBUG: Adding %s => %s" % (nick, host))

        message = str(message).replace("'","''")

        query = "SELECT * FROM users WHERE LOWER(nick) = '%s' AND LOWER(host) = '%s' AND LOWER(channel) = '%s';" % (nick.lower(), host.lower(), channel.lower())

        self.c.execute(query)
        data = self.c.fetchall()
        if len(data) == 0:
            if addedWithoutMsg == True:
                query = "INSERT INTO users (host, nick, channel, identity) VALUES ('%s','%s','%s','%s');" % (host, nick, channel, identity)
            else:
                query = "INSERT INTO users VALUES ('%s','%s','%s','%s','%s','%s');" % (host, nick, channel, datetime.datetime.now(), message, identity)
            self.c.execute(query)
        else:
            if addedWithoutMsg == False:
                query = "UPDATE users SET seen = '%s', message = '%s' WHERE LOWER(nick) = '%s' AND LOWER(host) = '%s' AND LOWER(channel) = '%s';" % (datetime.datetime.now(), message, nick.lower(), host.lower(), channel.lower())
            self.c.execute(query)
        self.conn.commit()

    ''' OK '''
    def process_moderated(self, op_nick, op_host, op_ident, channel, action, message, offender_nick, offender_host, offender_ident, added):
        if self.nv['DEBUG_MODE'] == True:
            self.PutModule("DEBUG: Adding %s => %s" % (nick, host))

        message = str(message).replace("'","''")

        query = "INSERT INTO moderated VALUES('%s','%s','%s','%s','%s','%s','%s','%s','%s','%s','%s');" % (op_nick, op_host, channel, action, message, offender_nick, offender_host, added, datetime.datetime.now(), offender_ident, op_ident)
        self.c.execute(query)
        self.conn.commit()

    ''' OK '''
    def process_channels(self):
        chans = self.GetNetwork().GetChans()
        for chan in chans:
            self.PutIRC("WHO %s" % chan)

    ''' OK '''
    def OnRaw(self, message):
        if str(message.s).split()[1] == "352": # on WHO
            host = str(message.s).split()[5]
            nick = str(message.s).split()[7]
            ident = str(message.s).split()[4]
            channel = str(message.s).split()[3]
            self.process_user(host, nick, ident, channel, None, True)
        elif str(message.s).split()[1] == "311": # on WHOIS
            host = str(message.s).split()[5]
            nick = str(message.s).split()[3]
            ident = str(message.s).split()[4]
            channel = str(message.s).split()[6]
            self.process_user(host, nick, ident, channel, None, True)
        elif str(message.s).split()[1] == "314": # on WHOWAS
            host = str(message.s).split()[5]
            nick = str(message.s).split()[3]
            self.process_user(host, nick, ident, channel, None, True)
        elif str(message.s).split()[1] == "JOIN":
            if self.nv['PROCESS_CHANNEL_ON_JOIN'] == "TRUE":
                join_nick = (str(message).split('!')[0])[1:]
                curr_nick = self.GetNetwork().GetIRCNick().GetNick()
                if join_nick == curr_nick:
                    self.PutIRC("WHO " + str(message.s).split()[2])

        self.raw_hold = {}

    ''' OK '''
    def OnJoin(self, user, channel):
        self.process_user(user.GetHost(), user.GetNick(), user.GetIdent(), channel.GetName(), None, True)

        if self.nv['NOTIFY_ON_JOIN'] == "TRUE" and user.GetNick() != self.GetUser().GetNick():
            if user.GetNick() in self.TIMEOUTS:
                diff = datetime.datetime.now() - self.TIMEOUTS[user.GetNick()]
                if diff.total_seconds() > self.nv['NOTIFY_ON_JOIN_TIMEOUT']:
                    self.PutModule("%s (%s) has joined %s" % (user.GetNick(), user.GetHost(), channel.GetName()))
                    if self.nv['NOTIFY_DEFAULT_MODE'] == "nick":
                        self.cmd_trace_nick(user.GetNick())
                    elif self.nv['NOTIFY_DEFAULT_MODE'] == "host":
                        self.cmd_trace_host(user.GetHost())
                    self.TIMEOUTS[user.GetNick()] = datetime.datetime.now()
            else:
                self.PutModule("%s (%s) has joined %s" % (user.GetNick(), user.GetHost(), channel.GetName()))
                if self.nv['NOTIFY_DEFAULT_MODE'] == "nick":
                    self.cmd_trace_nick(user.GetNick())
                elif self.nv['NOTIFY_DEFAULT_MODE'] == "host":
                    self.cmd_trace_host(user.GetHost())
                self.TIMEOUTS[user.GetNick()] = datetime.datetime.now()

    ''' OK '''
    def OnNick(self, user, new_nick, channels):
        for chan in channels:
            self.process_user(user.GetHost(), new_nick, user.GetIdent(), chan.GetName(), None, True)

    ''' OK '''
    def OnPrivMsg(self, user, message):
        self.process_user(user.GetHost(), user.GetNick(), user.GetIdent(), 'PRIVMSG', message, False)

    ''' OK '''
    def OnChanMsg(self, user, channel, message):
        self.process_user(user.GetHost(), user.GetNick(), user.GetIdent(), channel.GetName(), message, False)

    ''' OK '''
    def OnChanAction(self, user, channel, message):
        message = "* " + str(message).replace("'","''")
        self.process_user(user.GetHost(), user.GetNick(), user.GetIdent(), channel.GetName(), message, False)

    ''' OK '''
    def OnPart(self, user, channel, message):
        self.process_user(user.GetHost(), user.GetNick(), user.GetIdent(), channel.GetName(), None, True)

    ''' OK '''
    def OnQuit(self, user, message, channels):
        for chan in channels:
            self.process_user(user.GetHost(), user.GetNick(), user.GetIdent(), chan.GetName(), None, True)

        if "G-Lined" in message:
            self.process_moderated(None, None, None, None, "gl", message, user.GetNick(), user.GetHost(), user.GetIdent(), None)
        elif "K-Lined" in message:
            self.process_moderated(None, None, None, None, "kl", message, user.GetNick(), user.GetHost(), user.GetIdent(), None)
        elif "Z-Lined" in message:
            self.process_moderated(None, None, None, None, "zl", message, user.GetNick(), user.GetHost(), user.GetIdent(), None)
        elif "Q-Lined" in message:
            self.process_moderated(None, None, None, None, "ql", message, user.GetNick(), user.GetHost(), user.GetIdent(), None)
        elif "Killed" in message:
            self.process_moderated(None, None, None, None, "kd", message, user.GetNick(), user.GetHost(), user.GetIdent(), None)

    ''' OK '''
    def OnKick(self, op, offender_nick, channel, message):
        query = "SELECT host, identity, MAX(seen) FROM users WHERE nick = '%s'" % offender_nick
        self.c.execute(query)
        for row in self.c:
            self.on_kick_process(op.GetNick(), op.GetHost(), op.GetIdent(), channel.GetName(), offender_nick, row[0], row[1], message)

    ''' OK '''
    def on_kick_process(self, op_nick, op_host, op_ident, channel, offender_nick, offender_host, offender_ident, message):
        self.process_moderated(op_nick, op_host, op_ident, channel, 'k', message, offender_nick, offender_host, offender_ident, None)
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
        if type == "nick":
            self.cmd_trace_nick(user)
            self.cmd_trace_nickchans(user)
        elif type == "host":
            self.cmd_trace_host(user)
            self.cmd_trace_hostchans(user)
        self.cmd_offenses(type, type, user, None)
        self.cmd_geoip(type, user)
        self.cmd_seen(type, type, None, user)
        self.PutModule("Trace on %s %s complete." % (type, user))

    ''' OK '''
    def cmd_trace_nick(self, nick):
        query = "SELECT host, nick FROM users WHERE LOWER(nick) = '%s' GROUP BY host ORDER BY host;" % nick.lower()
        self.c.execute(query)
        data = self.c.fetchall()
        if len(data) > 0:
            total = 0
            host_count = 0
            c2 = self.conn.cursor()
            for row in data:
                count = 0
                out = "%s was also known as: " % nick
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
                self.PutModule("%s: %s total nicks" % (nick, total))
        else:
            self.PutModule("No history found for nick: %s" % nick)

    ''' OK '''
    def cmd_trace_host(self, host):
        query = "SELECT nick, host FROM users WHERE LOWER(host) = '%s' GROUP BY nick ORDER BY nick COLLATE NOCASE;" % host.lower()
        self.c.execute(query)
        data = self.c.fetchall()
        if len(data) > 0:
            count = 0
            out = "%s was known as: " % host
            for row in data:
                out += "%s, " % row[0]
                count += 1
            out = out[:-2]
            self.PutModule("Host %s (%s nicks)" % (out, count))
        else:
            self.PutModule("No history found for host: %s" % host)

    ''' OK '''
    def cmd_trace_channels(self, user_type, user):
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
    def cmd_trace_sharedchans(self, user_type, users):
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
    def cmd_trace_intersect(self, user_type, chans):
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
        if method == "in":
            if channel == 'PRIVMSG':
                chan = 'Private Message'
            else:
                chan = channel
            query = "SELECT seen, message FROM users WHERE seen = (SELECT MAX(seen) FROM users WHERE LOWER(%s) = '%s' AND LOWER(channel) = '%s') AND LOWER(%s) = '%s' AND LOWER(channel) = '%s';" % (user_type, user.lower(), channel.lower(), user_type, user.lower(), channel.lower())
            self.c.execute(query)
            data = self.c.fetchall()
            if len(data) > 0:
                for row in data:
                    days, hours, minutes = self.dt_diff(row[0])
                    self.PutModule("%s %s was last seen in %s %s days, %s hours, %s minutes ago saying \"%s\" (%s)" % (user_type.title(), user, chan, days, hours, minutes, row[1], row[0]))
            else:
                self.PutModule("%s %s has not been seen talking in %s" % (user_type.title(), user, chan))
        elif method == "nick" or method == "host":
            query = "SELECT channel, MAX(seen), message FROM users WHERE seen = (SELECT MAX(seen) FROM users WHERE LOWER(%s) = '%s') AND LOWER(%s) = '%s';" % (method, user.lower(), method, user.lower())
            self.c.execute(query)
            data = self.c.fetchall()
            if data[0][0] != None:
                for row in data:
                    if row[0] == 'PRIVMSG':
                        chan = 'Private Message'
                    else:
                        chan = channel
                    days, hours, minutes = self.dt_diff(row[1])
                    self.PutModule("%s %s was last seen in %s %s days, %s hours, %s minutes ago saying \"%s\" (%s)" % (user_type.title(), user, row[0], days, hours, minutes, row[2], row[1]))
            else:
                self.PutModule("%s %s has not been seen talking." % (user_type.title(), user))

    ''' OK '''
    def cmd_offenses(self, method, user_type, user, channel):
        query = ''
        cols = "op_nick, op_host, channel, action, message, offender_nick, offender_host, added, time"
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
            for op_nick, op_host, channel, action, message, offender_nick, offender_host, added, time in data:
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
                    self.PutModule("%s (%s) was %s from %s by %s on %s." % (user, offender, action, channel, op_nick, time))
                elif action == "k":
                    self.PutModule("%s (%s) was kicked from %s by %s on %s. Reason: %s" % (user, offender, channel, op_nick, time, message))
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
                        action = "Killed"

                    self.PutModule("%s %s (%s) was %s on %s." % (user_type.title(), user, offender_host, action, time))

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
            query = "SELECT host, MAX(seen) FROM users WHERE nick = '%s'" % user
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
            if loc_json["status"] != "fail":
                self.PutModule("%s %s is located in %s, %s, %s (%s, %s) / Timezone: %s / Proxy: %s / Mobile: %s / IP: %s %s" % (method.title(), nick, loc_json["city"], loc_json["regionName"], loc_json["country"], loc_json["lat"], loc_json["lon"], loc_json["timezone"], loc_json["proxy"], loc_json["mobile"], loc_json["query"], loc_json["reverse"]))
            else:
                self.PutModule("Unable to geolocate %s %s. (Reason: %s)" % (method, nick, loc_json["message"]))
        else:
            self.PutModule("Invalid host for geolocation (%s)" % host)

    ''' OK '''
    def cmd_add(self, nick, host, ident, channel):
        self.process_user(host, nick, ident, channel, False)
        self.PutModule("%s => %s" % (nick, host, channel))

    ''' OK '''
    def cmd_info(self):
        self.PutModule("aka nick tracking module by MuffinMedic (Evan) and AwwCookies (Aww) - http://wiki.znc.in/aka")

    ''' OK '''
    def cmd_version(self):
        self.PutModule("Version: %s (%s)" % (version, updated))

    ''' OK '''
    def cmd_stats(self):
        self.c.execute('SELECT COUNT(DISTINCT host), COUNT(DISTINCT nick) FROM users;')
        for row in self.c:
            self.PutModule("Nicks: %s" % row[1])
            self.PutModule("Hosts: %s" % row[0])

    ''' OK '''
    def OnModCommand(self, command):
        # Valid Commands
        cmds = ["all", "trace", "seen", "offenses", "geoip", "help", "config", "getconfig", "info", "add", "import", "export", "version", "stats", "update"]
        if command.split()[0] in cmds:
            if command.split()[0] == "all":
                cmds = ["nick", "host"]
                if command.split()[1] in cmds:
                    self.cmd_all(command.split()[2], command.split()[1])
            if command.split()[0] == "trace":
                cmds = ["sharedchans", "intersect", "channels", "nick", "host", "geoip"]
                if command.split()[1] in cmds:
                    if command.split()[1] == "sharedchans":
                        cmds = ["hosts", "nicks"]
                        if command.split()[2] in cmds:
                            if command.split()[2] == "hosts":
                                type = "host"
                            elif command.split()[2] == "nicks":
                                type = "nick"
                            self.cmd_trace_sharedchans(type, list(command.split()[3:]))
                        else:
                            self.PutModule(command.split()[0] + " " + command.split()[1] + " " + command.split()[2] + " is not a valid command.")
                    elif command.split()[1] == "intersect":
                        cmds = ["hosts", "nicks"]
                        if command.split()[2] in cmds:
                            if command.split()[2] == "hosts":
                                type = "host"
                            elif command.split()[2] == "nicks":
                                type = "nick"
                            self.cmd_trace_intersect(type, command.split()[3:])
                        else:
                            self.PutModule(command.split()[0] + " " + command.split()[1] + " is not a valid command.")
                    elif command.split()[1] == "channels":
                        cmds = ["host", "nick"]
                        if command.split()[2] in cmds:
                            self.cmd_trace_channels(command.split()[2], command.split()[3])
                        else:
                            self.PutModule(command.split()[0] + " " + command.split()[1] + " " + command.split()[2] + " is not a valid command.")
                    elif command.split()[1] == "nick": # trace nick $nick
                        self.cmd_trace_nick(command.split()[2])
                    elif command.split()[1] == "host": # trace host $host
                        self.cmd_trace_host(command.split()[2])
                else:
                    self.PutModule("%s is not a valid command." % command)
            elif command.split()[0] == "seen":
                cmds = ["in", "nick", "host"]
                if command.split()[1] in cmds:
                    if command.split()[1] == "nick" or command.split()[1] == "host":
                        self.cmd_seen(command.split()[1], command.split()[1], None, command.split()[2])
                    elif command.split()[1] == "in":
                        cmds = ["nick", "host"]
                        if command.split()[2] in cmds:
                            self.cmd_seen(command.split()[1], command.split()[2], command.split()[3], command.split()[4])
                        else:
                            self.PutModule(command.split()[0] + " " + command.split()[1] + " " + command.split()[2] + " is not a valid command.")
                    else:
                        self.PutModule(command.split()[0] + " " + command.split()[1] + " is not a valid command.")
                else:
                    self.PutModule(command.split()[0] + " " + command.split()[1] + " is not a valid command.")
            elif command.split()[0] == "offenses":
                cmds = ["in", "nick", "host"]
                if command.split()[1] in cmds:
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
                            self.PutModule(command.split()[0] + " " + command.split()[1] + " " + command.split()[2] + " is not a valid command.")
                else:
                    self.PutModule(command.split()[0] + " " + command.split()[1] + " is not a valid command.")
            elif command.split()[0] == "geoip":
                cmds = ["host", "nick"]
                if command.split()[1] in cmds:
                    self.cmd_geoip(command.split()[1], command.split()[2])
                else:
                    self.PutModule(command.split()[0] + " " + command.split()[1] + " is not a valid command.")
            elif command.split()[0] == "info":
                self.cmd_info()
            elif command.split()[0] == "config":
                self.cmd_config(command.split()[1], command.split()[2])
            elif command.split()[0] == "getconfig":
                self.cmd_getconfig()
            elif command.split()[0] == "add":
                self.cmd_add(command.split()[1], command.split()[2], command.split()[3], command.split()[4])
            elif command.split()[0] == "help":
                self.cmd_help()
            elif command.split()[0] == "import":
                self.cmd_import_json(command.split()[1])
            elif command.split()[0] == "export":
                cmds = ["host", "nick"]
                if command.split()[1] in cmds:
                    self.cmd_export_json(command.split()[2], command.split()[1])
                else:
                    self.PutModule("%s is not a valid command." % command)
            elif command.split()[0] == "version":
                self.cmd_version()
            elif command.split()[0] == "stats":
                self.cmd_stats()
            elif command.split()[0] == "update":
                self.cmd_update()
        else:
            self.PutModule("%s is not a valid command." % command)

    ''' OK '''
    def dt_diff(self, td):
        time = td.split('.', 1)[0]
        then = datetime.datetime.strptime(time, "%Y-%m-%d %H:%M:%S")
        now = datetime.datetime.now()
        diff = now - then
        days = diff.days
        hours = diff.seconds//3600
        minutes = (diff.seconds//60)%60
        return days, hours, minutes

    ''' OK'''
    def cmd_getconfig(self):
        for key, value in self.nv.items():
            self.PutModule("%s = %s" % (key, value))

    ''' OK '''
    def cmd_config(self, var_name, value):
        valid = True
        bools = ["DEBUG_MODE", "NOTIFY_ON_JOIN", "NOTIFY_ON_MODE", "NOTIFY_ON_MODERATED", "PROCESS_CHANNEL_ON_JOIN", "PROCESS_CHANNELS_ON_LOAD"]
        if var_name.upper() in bools:
            if not str(value).upper() == "TRUE" or not str(value).upper() == "FALSE":
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
                self.PutModule("aka successfully updated. Please reload aka on all networks.")
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
                    query = "INSERT OR IGNORE INTO users (host, nick, channel) VALUES ('%s','%s','%s');" % (user[1], user[0], chan)
                    self.c.execute(query)
                del user
            del chans[chan]
            self.conn.commit()

            hosts = {}
            hosts = json.loads(open(self.GetSavePath() + "/hosts.json", 'r').read())
            for host in hosts:
                for nick in hosts[host]:
                        query = "INSERT OR IGNORE INTO users (host, nick) VALUES ('%s','%s');" % (host, nick)
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
        self.c.execute("create table if not exists users (host, nick, channel, seen, identity, UNIQUE(host COLLATE NOCASE, nick COLLATE NOCASE, channel COLLATE NOCASE));")
        self.c.execute("create table if not exists moderated (op_nick, op_host, channel, action, message, offender_nick, offender_host, added, time, offender_ident, op_ident)")

        ''' ADDITIONAL TABLES '''
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
            if str(table[1]) == 'message':
                exists = True
        if exists == False:
            self.c.execute("ALTER TABLE users ADD COLUMN message;")

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

    ''' OK '''
    def cmd_import_json(self, url):
        count = 0
        json_object = json.loads(requests.get(url).text)
        for user in json_object:
            query = "INSERT OR IGNORE INTO users (host, nick) VALUES ('%s','%s');" % (user["host"], user["nick"])
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
        help.SetCell("Description", "Shows nick change and host history for given nick")
        help.AddRow()
        help.SetCell("Command", "trace host")
        help.SetCell("Arguments", "<host>")
        help.SetCell("Description", "Shows nick history for given host")
        help.AddRow()
        help.SetCell("Command", "trace sharedchans nicks")
        help.SetCell("Arguments", "<nick1> <nick2> ... <nick#>")
        help.SetCell("Description", "Show common channels between a list of nicks")
        help.AddRow()
        help.SetCell("Command", "trace sharedchans hosts")
        help.SetCell("Arguments", "<host1> <host2> ... <host#>")
        help.SetCell("Description", "Show common channels between a list of hosts")
        help.AddRow()
        help.SetCell("Command", "trace intersect nicks")
        help.SetCell("Arguments", "<#channel1> <#channel2> ... <#channel#>")
        help.SetCell("Description", "Display nicks common to a list of channels")
        help.AddRow()
        help.SetCell("Command", "trace intersect hosts")
        help.SetCell("Arguments", "<#channel1> <#channel2> ... <#channel#>")
        help.SetCell("Description", "Display hosts common to a list of channels")
        help.AddRow()
        help.SetCell("Command", "trace channels nick")
        help.SetCell("Arguments", "<nick>")
        help.SetCell("Description", "Get all channels a nick has been seen in")
        help.AddRow()
        help.SetCell("Command", "trace channels host")
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
        help.SetCell("Description", "Displays last time nick was seen speaking")
        help.AddRow()
        help.SetCell("Command", "seen host")
        help.SetCell("Arguments", "<host>")
        help.SetCell("Description", "Displays last time host was seen speaking")
        help.AddRow()
        help.SetCell("Command", "seen in nick")
        help.SetCell("Arguments", "<#channel> <nick>")
        help.SetCell("Description", "Displays last time nick was seen speaking in channel")
        help.AddRow()
        help.SetCell("Command", "seen in host")
        help.SetCell("Arguments", "<#channel> <host>")
        help.SetCell("Description", "Displays last time host was seen speaking in channel")
        help.AddRow()
        help.SetCell("Command", "geoip nick")
        help.SetCell("Arguments", "<nick>")
        help.SetCell("Description", "Geolocates nick")
        help.AddRow()
        help.SetCell("Command", "geoip host")
        help.SetCell("Arguments", "<host>")
        help.SetCell("Description", "Geolocates host")
        help.AddRow()
        help.SetCell("Command", "add")
        help.SetCell("Arguments", "<nick> <host> <channel>")
        help.SetCell("Description", "Manually add a nick/host entry to the database")
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
        help.SetCell("Command", "stats")
        help.SetCell("Description", "Print nick and host stats for the network")
        help.AddRow()
        help.SetCell("Command", "update")
        help.SetCell("Description", "updates aka to latest version")
        help.AddRow()
        help.SetCell("Command", "help")
        help.SetCell("Description", "Print help from the module")

        self.PutModule(help)
