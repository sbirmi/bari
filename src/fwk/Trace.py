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
    conn = 8
    db = 9

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
        db: "DB",
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
                Level.conn,
                Level.db}

# Trace output
traceout=sys.stderr

def setTraceFile(filename):
    global traceout # pylint: disable=global-statement
    if filename:
        traceout = open(filename, "a") # pylint: disable=bad-option-value
    else:
        traceout = sys.stderr

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
    traceout.write("%-26s %-5s %-40s" % (now, Level.strep[lvl], framedesc))
    for m in msg:
        traceout.write(" " + str(m))
    traceout.write("\n")

    traceout.flush()
