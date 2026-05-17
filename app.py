import argparse
import ipaddress
import os
import random
import socket

from dotenv import find_dotenv, load_dotenv, set_key

from beetiful import app

load_dotenv()

RANDOM_PORT_RANGE = (3000, 8000)
RANDOM_PORT_ATTEMPTS = 3


def _port_from_env() -> int | None:
    raw = os.getenv("FLASK_PORT")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print(f"Invalid FLASK_PORT value {raw!r}; selecting a new random port.")
        return None


def _is_port_free(port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
    except OSError:
        return False
    finally:
        s.close()
    return True


def _persist_port(port: int) -> None:
    dotenv_path = find_dotenv()
    if not dotenv_path:
        dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        open(dotenv_path, "a").close()
    set_key(dotenv_path, "FLASK_PORT", str(port))
    print(f"Picked random port {port}; saved to {dotenv_path}.")


def _pick_random_port() -> int:
    lo, hi = RANDOM_PORT_RANGE
    for _ in range(RANDOM_PORT_ATTEMPTS):
        candidate = random.randint(lo, hi)
        if _is_port_free(candidate):
            _persist_port(candidate)
            return candidate
    raise SystemExit(
        f"Could not find a free port in {lo}-{hi} after {RANDOM_PORT_ATTEMPTS} attempts."
    )


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
        default=None,
        help=f"TCP port to bind. If omitted, uses FLASK_PORT from .env, or picks a random "
             f"port in {RANDOM_PORT_RANGE[0]}-{RANDOM_PORT_RANGE[1]} on first run and saves it.",
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

    if args.port is not None:
        port = args.port
    else:
        env_port = _port_from_env()
        port = env_port if env_port is not None else _pick_random_port()

    if args.allow_local_subnet:
        subnet = _detect_local_subnet()
        if subnet is None:
            raise SystemExit("--allow-local-subnet: could not detect a local network interface.")
        _install_subnet_filter(subnet)
        host = "0.0.0.0"
        print(f"Accepting connections from loopback and {subnet}.")
    else:
        host = "127.0.0.1"

    print(f"Beetiful listening on http://{host}:{port}/")

    if args.debug:
        app.run(debug=True, host=host, port=port)
    else:
        from waitress import serve
        serve(app, host=host, port=port)


if __name__ == "__main__":
    main()
