import logging
import sys
from pyexpat import ExpatError

try:
    from twisted.internet import protocol, reactor
    from twisted.words.protocols.irc import IRCClient
    from twisted.internet.protocol import ClientFactory
except ImportError:
    logging.exception("Could not start the IRC backend")
    logging.error("""
    If you intend to use the IRC backend please install Twisted Words:
    -> On debian-like systems
    sudo apt-get install python-twisted-words
    -> On Gentoo
    sudo emerge -av dev-python/twisted-words
    -> Generic
    pip install "Twisted Words"
    """)
    sys.exit(-1)

from xmpp.simplexml import XML2Node
from errbot.backends.base import Identifier, Message
from errbot.errBot import ErrBot
from errbot.utils import xhtml2txt
from config import CHATROOM_PRESENCE

class IRCConnection(IRCClient, object):
    connected = False

    def __init__(self, callback, nickname='err'):
        self.nickname = nickname
        self.callback = callback
        self.lineRate = 1 # ONE second ... it looks like it is a minimum for freenode.

    #### Connection

    def send_message(self, mess):
        if self.connected:
            self.msg(mess.getTo(), mess.getBody().encode("utf-8"))
        else:
            logging.debug("Zapped message because the backend is not connected yet %s" % mess.getBody())

    #### IRC Client duck typing
    def lineReceived(self, line):
        logging.debug('IRC line received : %s' % line)
        super(IRCConnection, self).lineReceived(line)

    def irc_PRIVMSG(self, prefix, params):
        fr, line = params
        if fr == self.nickname: # it is a private message
            fr = prefix.split('!')[0] # reextract the real from
            typ = 'chat'
        else:
            typ = 'groupchat'
        logging.debug('IRC message received from %s [%s]' % (fr, line))
        msg = Message(line, typ=typ)
        msg.setFrom(Identifier(node=fr, domain=prefix))
        self.callback.callback_message(self, msg)


    def connectionMade(self):
        self.connected = True
        super(IRCConnection, self).connectionMade()
        self.callback.connect_callback() # notify that the connection occured
        logging.debug("IRC Connected")

    def clientConnectionLost(self, connection, reason):
        pass


class IRCFactory(ClientFactory):
    """
    Factory used for creating IRC protocol objects
    """

    protocol = IRCConnection

    def __init__(self, callback, nickname='err-chatbot'):
        self.irc = IRCConnection(callback, nickname)

    def buildProtocol(self, addr=None):
        return self.irc

    def clientConnectionLost(self, conn, reason):
        pass


ENCODING_INPUT = sys.stdin.encoding

class IRCBackend(ErrBot):
    conn = None

    def __init__(self, nickname, server, port=6667, password=None):
        super(IRCBackend, self).__init__()
        self.nickname = nickname
        self.server = server
        self.port = port

    def serve_forever(self):
        self.jid = Identifier(node=self.nickname)
        self.connect() # be sure we are "connected" before the first command
        try:
            reactor.run()
        finally:
            logging.debug("Trigger disconnect callback")
            self.disconnect_callback()
            logging.debug("Trigger shutdown")
            self.shutdown()

    def connect(self):
        if not self.conn:
            ircFactory = IRCFactory(self, self.jid.node)
            self.conn = ircFactory.irc
            reactor.connectTCP(self.server, self.port, ircFactory)

        return self.conn

    def build_message(self, text):
        return Message(self.build_text_html_message_pair(text)[0]) # 0 = Only retain pure text

    def shutdown(self):
        super(IRCBackend, self).shutdown()

    def join_room(self, room, username=None, password=None):
        self.conn.join(room)

    @property
    def mode(self):
        return 'IRC'
