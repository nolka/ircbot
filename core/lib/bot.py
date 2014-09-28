# -*- coding: utf8

__author__ = 'nolka'

import sys
import os
import re
import datetime
import time
import calendar
from sqlite3 import Connection
import requests

from  core.lib.irc import Client
from core.lib.query_builder import parse_data


class SimpleBot(Client):
    def on_connected(self):
        self.init_db()

        self.authorized_users = list()
        self.command_prefix = "*"

        for channel in self.config['channels']:
            self.join(channel)

        self.aliases = {
            "telka": ["телка", "телочка"]
        }

    def on_disconnected(self):
        if self.db:
            self.db.close()

    def init_db(self):
        self.db = Connection(self.config['database'])
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS
            message_log (
                id INTEGER PRIMARY KEY ASC,
                channel TEXT,
                nick TEXT,
                ident TEXT,
                host TEXT,
                message TEXT,
                date INTEGER
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS
            social_telki (
              id INTEGER PRIMARY KEY ASC,
              rating INTEGER,
              displayed_times INNTEGER,
              url TEXT,
              who_added TEXT,
              date_added INTEGER
            )
        """)
        def dict_factory(cursor, row):
            d = {}
            for idx, col in enumerate(cursor.description):
                d[col[0]] = row[idx]
            return d

        self.db.row_factory = dict_factory

    def get_unix_timestamp(self):
        return int(time.mktime(datetime.datetime.now().timetuple()))

    def log_message(self, nick_name, ident, host_name, message, channel):
        self.db.execute("""
        INSERT INTO message_log (channel, nick, ident, host, message, date)
        VALUES (?,?,?,?,?,?)
        """, (channel, nick_name, ident, host_name, message, self.get_unix_timestamp()))
        self.db.commit()

    def on_private(self, nick, ident, host, message):
        print u"pm from:%s: %s" % (nick, message)

    def on_channel(self, nick, ident, host, message, channel):
        print u"on %s from %s: %s" % (channel, nick, message)


    def on_privmsg(self, nick, ident, host, params, trailing):

        channel = None
        message = trailing

        if params == self.config['nick']:
            self.on_private(nick, ident, host, message)
        else:
            channel = params.decode('utf-8')
            self.on_channel(nick, ident, host, message, channel)

        self.log_message(nick.decode('utf-8'), ident.decode('utf-8'), host.decode('utf-8'), message.decode('utf-8'), channel)

        if message.startswith(self.command_prefix):
            self.handle_command(nick, ident, host, message[len(self.command_prefix):], channel)

    def on_nick(self, old_nick, ident, host, params, new_nick):
        if old_nick == self.nick_name:
            self.print_debug("Yay! My name changed to: %s" % new_nick)
            self.nick_name = new_nick

    def is_authorized(self, nick, ident, host):
        for login_data in self.authorized_users:
            if login_data[0] == nick and login_data[1] == ident and login_data[2] == host:
                return True
        return False

    def authorize(self, nick, ident, host, password):
        for bot_oper in self.config['allowed_ops']:
            if bot_oper['nick'] == nick and bot_oper['password'] == password:
                self.authorized_users.append((nick, ident, host))
                return True

    def handle_command(self, nick, ident, host, command, channel):
        args = None
        if " " in command:
            command, args = command.split(" ", 1)

        command_name = "cmd_%s" %  command.lower()

        try:
            meth = getattr(self, command_name, None)
            if meth is None:
                for cmdname, aliases in self.aliases.iteritems():
                    for alias in aliases:
                        if command == alias:
                            command_name = "cmd_%s" % cmdname.lower()
                            meth = getattr(self, command_name)
                            break
            if meth:
                meth(nick, ident, host, channel, args)

            ameth = getattr(self, "a%s" % command_name, None)
            if ameth is not None:
                if self.is_authorized(nick, ident, host):
                    ameth(nick, ident, host, channel, args)
                    return
                else:
                    self.say_to(nick, "Nope!")
        except Exception as e:
            print(e.message)
            self.say_to(nick, "Some error occurred while your command being executed :[")


    def cmd_auth(self, nick, ident, host, channel, args):
        if channel:
            self.say_to(nick, 'Noob :D', channel)

        if not self.is_authorized(nick, ident, host):
            if self.authorize(nick, ident, host, args):
                self.say_to(nick, "Auth successed!")
            else:
                self.say_to(nick, "Auth failed!")
        else:
            self.say_to(nick, "You're already authorized!")

    def acmd_die(self, nick, ident, host, channel, args):
        self.say_to(nick, "Quitting....")
        self._shutdown_pending = True

    def acmd_join(self, nick, ident, host, channel, args):
        self.join(args)

    def acmd_part(self, nick, ident, host, channel, args):
        self.part(args)

    def cmd_lastlog(self, nick, ident, host, channel, args):

        known_args = ["nick", "channel", "message", "date", "limit"]
        if not args:
            self.say_to(nick, "Known args are: %s" % ", ".join(known_args), channel)
            return

        arg_dict = dict()

        if args:
            arg_pairs = args.split(" ")
            wrong_attrs = list()

            for p in arg_pairs:
                if "=" in p:
                    k,v = p.split("=")
                    if k in known_args:
                        arg_dict[k] = v
                    else:
                        wrong_attrs.append(k)
                else:
                    wrong_attrs.append(p)
            if wrong_attrs:
                self.say_to(nick, "Wrong or unknown attributes: %s" % ",".join(wrong_attrs), channel)

            if not arg_dict:
                return

        has_limit = 30
        if "limit" in arg_dict.keys():
            has_limit = arg_dict.pop("limit")

        query = [
            "SELECT * FROM ("
            "SELECT id, channel, nick, ident, host, message, date FROM message_log"
        ]
        if arg_dict:
            query.append("WHERE")

        query_conditions = list()
        placeholders = list()

        parsed = parse_data(arg_dict)
        #print parsed
        for attr, value in parsed:
            query_conditions.append("%s %s"% (attr, value[0]))
            placeholders.append(value[1])

        query.append(" AND ".join(query_conditions))

        query.append("LIMIT ?")
        placeholders.append(has_limit)

        query.append(") ORDER BY id ASC")

        self.print_debug("querying: %s" % " ".join(query))
        cur = self.db.execute(" ".join(query), placeholders)

        message = ["chan\tnick\tmessage"]
        for row in cur.fetchall():
            datime = datetime.datetime.fromtimestamp(row['date'])
            row['date'] = datime.strftime("%Y.%m.%d %H:%M:%S")
            message.append("%(date)s\t%(channel)s\t%(nick)s\t%(message)s" % row)

        if not message:
            self.say_to(nick, "Nothing found :[")
            return

        resp = requests.post("https://clbin.com", dict(clbin="\n".join(message)))
        if resp.status_code == 200:
            self.say_to(nick, resp.text, channel)
        else:
            self.say_to(nick, "Post failed. Code %d" % resp.status_code,channel)

    def acmd_nick(self, nick, ident, host, channel, args):
        self.sendMessage("NICK :%s" % args)

    def acmd_telki_loadf(self, nick, ident, host, channel, args):
        self.print_debug("Loading telki from plain file %s" % args)
        duplicated_rows = 0
        added_rows = 0
        processed_rows = 0
        incorrect_urls = 0
        if os.path.exists(args):
            args = open(args)
        elif "," in args:
            args = args.split(",")
        elif args.startswith("http"):
            args = [args]

        for line in args:
            clean_url = line.strip()
            if not clean_url.startswith("http"):
                incorrect_urls +=1
                continue
            cur = self.db.execute("SELECT COUNT(*) count FROM social_telki WHERE URL=?", (clean_url, ))
            count = cur.fetchone()
            if int(count['count']) <=0:
                self.db.execute("""INSERT INTO social_telki (
                    rating,
                    displayed_times,
                    url,
                    who_added,
                    date_added
                    )
                    VALUES
                    (?,?,?,?,?)""", (0, 0, clean_url, nick, self.get_unix_timestamp()))
                added_rows +=1
            else:
                duplicated_rows += 1
            processed_rows+=1
        self.db.commit()
        self.say_to(nick, "File loaded; total rows: %d; added: %s; doubles ignored: %s; incorrect urls: %d" % (processed_rows, added_rows, duplicated_rows, incorrect_urls), channel)

    def cmd_telka(self, nick, ident, host, channel, args):
        cur = self.db.execute("""
        SELECT id, url FROM social_telki
          WHERE displayed_times<= (SELECT MIN(displayed_times) FROM social_telki)
          ORDER BY RANDOM()
          LIMIT 1
        """)
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE social_telki SET displayed_times=displayed_times+1 WHERE id=?", (row['id'], ))
            url = row['url']
            resp = requests.get(url)
            if resp.status_code == 200:
                self.say_to(args or nick, row['url'], channel)
                self.db.commit()
            else:
                self.say_to(nick, "Еще разок попробуй, ссыль битая :(", channel)
                self.db.rollback()
            return

        self.say_to(nick, "Nothing found O_o", channel)




