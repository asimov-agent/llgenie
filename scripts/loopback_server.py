#!/usr/bin/env python3
"""A loopback HTTP fixture that listens immediately.

``python3 -m http.server`` calls ``socket.getfqdn()`` between ``bind()`` and
``listen()``. On the macOS 15 GitHub runner that lookup stalls ~35s (local
network privacy, actions/runner-images#14409), so a readiness probe that waits
30s reports the server as dead while the process is still alive and has written
nothing. This server does no name lookup: it binds, listens, then answers.
"""
import socket
import sys


def main(argv: list[str]) -> int:
    host, port = "127.0.0.1", 8000
    args = argv[1:]
    if args and args[0].isdigit():
        port = int(args.pop(0))
    if "--bind" in args:
        host = args[args.index("--bind") + 1]
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(8)
    body = b"ok\n"
    head = b"HTTP/1.0 200 OK\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % len(body)
    while True:
        conn, _ = sock.accept()
        try:
            conn.recv(4096)
            conn.sendall(head + body)
        finally:
            conn.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
