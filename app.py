import argparse
import ipaddress
import os
import socket

from dotenv import load_dotenv

from beetiful import app

load_dotenv()

DEFAULT_PORT = 3001


def _default_port() -> int:
    raw = os.getenv("FLASK_PORT", str(DEFAULT_PORT))
    try:
        return int(raw)
    except ValueError:
        print(f"Invalid FLASK_PORT value {raw!r}; using default {DEFAULT_PORT}.")
        return DEFAULT_PORT


def _detect_local_subnet() -> ipaddress.IPv4Network | None:
    """Return the host's primary IPv4 /24 network, or None on failure."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # No packet is actually sent; this just picks the outbound interface.
        s.connect(("8.8.8.8", 53))
        ip = s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()
    return ipaddress.IPv4Network(f"{ip}/24", strict=False)


def _install_subnet_filter(network: ipaddress.IPv4Network) -> None:
    from flask import abort, request

    @app.before_request
    def _restrict_to_subnet():
        remote = request.remote_addr
        if remote is None:
            abort(403)
        addr = ipaddress.ip_address(remote)
        if addr.is_loopback or addr in network:
            return
        abort(403)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Beetiful web interface.")
    parser.add_argument(
        "--port",
        type=int,
        default=_default_port(),
        help=f"TCP port to bind (default: env FLASK_PORT or {DEFAULT_PORT}).",
    )
    parser.add_argument(
        "--allow-local-subnet",
        action="store_true",
        help="Accept connections from the host's local /24 subnet in addition to loopback. "
             "Without this flag, the server is bound to 127.0.0.1 only.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run with Flask's development server (auto-reload + interactive debugger). "
             "Default uses waitress.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    if args.allow_local_subnet:
        subnet = _detect_local_subnet()
        if subnet is None:
            raise SystemExit("--allow-local-subnet: could not detect a local network interface.")
        _install_subnet_filter(subnet)
        host = "0.0.0.0"
        print(f"Accepting connections from loopback and {subnet}.")
    else:
        host = "127.0.0.1"

    print(f"Beetiful listening on http://{host}:{args.port}/")

    if args.debug:
        app.run(debug=True, host=host, port=args.port)
    else:
        from waitress import serve
        serve(app, host=host, port=args.port)


if __name__ == "__main__":
    main()
