"""HTTP server bootstrap."""
import socket

HOST = "0.0.0.0"
PORT = 8080

class Server:
    """Minimal HTTP server."""

    def __init__(self, host=HOST, port=PORT):
        self.host = host
        self.port = port
        self._running = False
