import datetime
import inspect
import os
import sys

class Level:
    error = 0
    warn = 1
    game = 2
    rnd = 3  # round
    play = 4
    info = 5
    msg = 6
    debug = 7

    strep = {
        error: "ERR",
        warn: "WARN",
        game: "GAME",
        rnd: "ROUND",
        play: "PLAY",
        info: "INFO",
        msg: "MSG",
        debug: "DEBUG",
    }

SHOW_UPTO_LEVEL = Level.debug

def trace(lvl, *msg):
    if lvl > SHOW_UPTO_LEVEL:
        return
    now = datetime.datetime.now()

    currentframe = inspect.currentframe()
    caller = inspect.getouterframes(currentframe, 2)[1]
    framedesc = "%s:%s %s" % (os.path.split(caller.filename)[-1], caller.lineno, caller.function)
    sys.stderr.write("%-26s %-5s %-40s" % (now, Level.strep[lvl], framedesc))
    for m in msg:
        sys.stderr.write(" " + str(m))
    sys.stderr.write("\n")
