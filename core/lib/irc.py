# -*- coding: utf8
import socket
import re

class Connection():
    def __init__(self, nick_name, password=None, real_name=None, ident=None, debug_mode=False, allow_reconnect=False,
                 read_buf=4096):
        self.nick_name = nick_name
        self.password = password

        if not real_name:
            real_name = "r%s" % self.nick_name
        self.real_name = real_name

        if not ident:
            ident = "i%s" % self.nick_name
        self.ident = ident

        self.debug_mode = debug_mode
        self.allow_reconnect = allow_reconnect
        self._read_buf = read_buf

        self.is_connected = False
        self._shutdown_pending = False

        self.re_ident = re.compile("^(?P<nick>[^!]+)!~?(?P<ident>[^@]+)@(?P<host>.+)$")
        self.re_message = re.compile("^(:(?P<prefix>\S+) )?(?P<command>\S+)( (?!:)(?P<params>.+?))?( :(?P<trail>.+))?$")

    def print_debug(self, message):
        if self.debug_mode:
            print "%s" % message

    def sendMessage(self, message, raw=False):
        self.print_debug("< %s" % message)
        if not self._c:
            raise AttributeError("Not connected!")

        if not raw:
            message = "%s\r\n" % message

        self._c.send(message)

    def do_message(self, prefix, command, params, trailing, is_system):
        evt_name = "on_%s" % str(command).lower()
        if hasattr(self, evt_name):
            self.print_debug("Calling event %s with prefix %s params %s; ends with %s" % (evt_name, prefix, params, trailing))
            meth = getattr(self, evt_name)
            if prefix:
                data = self.re_ident.match(prefix)
                if data:
                    data = data.groupdict()
                    meth(data['nick'], data['ident'], data['host'], params, trailing)
                    return

            meth(prefix, params, trailing)

    def parse(self, message):
        self.print_debug("> %s" % message)
        data = self.re_message.match(message)
        if data is not None:
            data = data.groupdict()
            is_system = False
            if data['command'].isdigit():
                data['command'] = int(data['command'])
                is_system = True

            self.do_message(data['prefix'], data['command'], data['params'], data['trail'], is_system)


    def connect(self, host_name, port=6667):
        self.host_name = host_name
        self._c = socket.socket()
        self._c.connect((host_name, port))
        self.sendMessage("NICK %s" % self.nick_name)
        self.sendMessage('USER %s HOST %s :%s' % (self.ident, self.host_name, self.real_name))
        self.is_connected = True
        self.on_connected()


    def disconnect(self):
        if self._c is not None:
            self._c.close()
            self.is_connected = False
            self.print_debug("Socket closed.")
            self.on_disconnected()

    def loop(self):
        text_buf = []
        while self._shutdown_pending == False:
            # try:
            text_blob = self._c.recv(self._read_buf)
            blob_size = len(text_blob)
            for id, char in enumerate(text_blob):
                if char in ["\r", "\n"]:
                    if text_buf:
                        self.parse("".join(text_buf))
                    text_buf = []
                else:
                    text_buf.append(char)
                    # except:
        # if self.allow_reconnect:
        # if self._conn_info is not None:
        # self.connect(self._conn_info)
        # else:
        #						self.print_debug("Connection info damaged, exiting")
        #						self._shutdown_pending = True
        #				else:
        #					self.print_debug("Reconnect on disconnect is not allowed, exiting.")
        #					self._shutdown_pending = True
        self.print_debug("Connection listener done...")
        self.disconnect()

    #
    ##
    ##  Event handlers!
    ##
    #
    def on_ping(self, prefix, params, trailing):
        self.sendMessage("PONG :%s" % trailing)

    def on_connected(self):
        pass

    def on_disconnected(self):
        pass


class Client(Connection):
    def join(self, channel_name, password=""):
        self.sendMessage("JOIN %s %s" % (channel_name, password))

    def part(self, channel_name):
        self.sendMessage("PART %s" % channel_name)

    def say_to(self, recipients, message, channels=None):
        if isinstance(recipients, list):
            recipients = ",".join(recipients)
        if isinstance(channels, list):
            channels = ",".join(channels)

        if channels is None:
            self.sendMessage("PRIVMSG %s :%s" % (recipients, message))
        else:
            self.sendMessage("PRIVMSG %s :%s, %s" % (channels, recipients, message))

    def set_config(self, config):
        self.config = config