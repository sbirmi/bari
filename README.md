bari (बारी) 
==========

A web-based, multiplayer turn based game framework and collection of games.


Requirements
============

1. python3
2. websockets


Setup
=====

    git clone https://github.com/sbirmi/bari.git
    python3 -m venv bari
    source bari/bin/activate
    pip install websockets


Running the game server
=======================

    source bari/bin/activate
    cd bari/src
    ./server.py

The server listen on port 4000 (default) for websocket connections (no SSL).

A simple HTML page to manually test functionality by creating and sending/receiving websocket messages can be done with the following HTML page.

    <html>
    <script>
    var conn = null;
    var url = "ws://127.0.0.1:4001/";
    
    function receive(msg)   { console.log(msg.data); }
    function send(msg)      { conn.send(JSON.stringify(msg)); }
    function connect(path) {
       conn = new WebSocket(url + path);
       conn.onmessage = receive;
    }
    </script>
    </html>

Load the page and open the Web Console (in firefox).

    >> connect("lobby")
       undefined
       ["GAME-STATUS", "chat:1", {"clients": 0}] bari_client.html:6:35
       ["GAME-STATUS", "chat:2", {"clients": 0}] bari_client.html:6:35
    >> send(["HOST", "chat"])
       undefined
       ["GAME-STATUS", "chat:3", {"clients": 0}]


Development
===========

Setup pre-commit hook to run pylint and unit tests before committing.

    ln -sf ../../pre-commit bari/.git/hooks
