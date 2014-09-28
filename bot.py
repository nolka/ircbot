#!/usr/bin/python
# -*- coding: utf8


from core.lib.bot import SimpleBot
from settings import botConfig
import sys

reload(sys)
sys.setdefaultencoding('utf-8')

c = SimpleBot(botConfig['nick'], debug_mode=True)
c.set_config(botConfig)
c.connect(botConfig['server'], botConfig['port'])
c.loop()
