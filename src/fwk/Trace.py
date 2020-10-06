import datetime
import inspect
import os
import sys
import websockets

class Level:
    error = 0
    warn = 1
    game = 2
    rnd = 3  # round
    play = 4
    info = 5
    msg = 6
    debug = 7
    conn = 8

    strep = {
        error: "ERR",
        warn: "WARN",
        game: "GAME",
        rnd: "ROUND",
        play: "PLAY",
        info: "INFO",
        msg: "MSG",
        debug: "DEBUG",
        conn: "CONN",
    }

# TRACE_LEVELS
#   None => no tracing
#   "*" => all tracing levels
#   set of numbers => levels to trace
TRACE_LEVELS = {Level.error, Level.warn,
                Level.game,
                Level.rnd,
                Level.play,
                Level.info,
                Level.msg,
                #Level.debug,
                Level.conn}

def strep(obj):
    if isinstance(obj, websockets.server.WebSocketServerProtocol):
        return obj.bari_name
    return str(obj)


def trace(lvl, *msg):
    if TRACE_LEVELS is None:
        return
    if not TRACE_LEVELS == "*":
        if lvl not in TRACE_LEVELS:
            return

    now = datetime.datetime.now()

    currentframe = inspect.currentframe()
    caller = inspect.getouterframes(currentframe, 2)[1]
    framedesc = "%s:%s %s" % (os.path.split(caller.filename)[-1], caller.lineno, caller.function)
    sys.stderr.write("%-26s %-5s %-40s" % (now, Level.strep[lvl], framedesc))
    for m in msg:
        sys.stderr.write(" " + strep(m))
    sys.stderr.write("\n")
