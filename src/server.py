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

    def stop(self):
        """Signal the server to stop after current request."""
        self._running = False

    def _loop(self, sock):
        while self._running:
            conn, addr = sock.accept()
            self._handle(conn, addr)

    def _handle(self, conn, addr):
        with conn:
            data = conn.recv(1024)
            if data:
                conn.sendall(b"HTTP/1.1 200 OK\r\n\r\nOK")

    def health_check(self):
        """Return True if server socket is reachable."""
        try:
            with socket.create_connection((self.host, self.port), timeout=1):
                return True
        except OSError:
            return False

    def __repr__(self):
        status = "running" if self._running else "stopped"
        return f"<Server {self.host}:{self.port} [{status}]>"

if __name__ == "__main__":
    srv = Server()
    print(f"Starting {srv}")
    srv.start()
# ligne stagée
# ligne NON stagée
