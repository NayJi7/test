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

    def start(self):
        """Bind socket and start accepting connections."""
        self._running = True
        with socket.socket() as sock:
            sock.bind((self.host, self.port))
            sock.listen(5)
            self._loop(sock)
