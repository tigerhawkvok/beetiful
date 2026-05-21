# Beetiful-Redux

## Background

> Dude, I don't care, [take me to the instructions](#installation).

I'm setting up my self hosted environment, and I set up my Google Takeout, and lo and behold, my library is a disaster. Duplicates abound. Bad tags. Flat directories. [Beets](https://beets.io/) can only do so much, and manual tagging on the command line for thousands of lookups is a PITA.

I look around for a GUI. The results are slim pickings. Beetiful looks promising, but it got archived read-only the day before. Well, it's just a Flask app and some JS, I can extend this if needed.

Digging around shows both the scope of my problematic imports and the fact that Beetiful expected less ... creative a starting place. The alternative is weeks of manual CLI work that's likely spotty, soI suppose it's time to bring on an LLM to do the grunt work.

For better or worse, that's right. This fork is heavily LLM modified (Claude Opus 4.7). I manually repaired some of its bugs and gave each features 2-3 minutes of reading diffs, but most of the proofing was in the using. Every feature I've added or extended was because I needed to avail of it for my disaster of an import.

That said -- **98% of the code here was vibe-coded**. This should be run _locally only_ without internet access unless you really trust Claude that much.


---------------

## Installation

To install Beetiful, follow these steps:

1. **Clone the Repository**

    ```bash
    git clone https://github.com/tigerhawkvok/beetiful.git
    cd beetiful
    ```

2. **Create a UV Environment**

    This project uses [uv](https://docs.astral.sh/uv/getting-started/installation/) for package and environment management. Hard package pins are your friend.

    Create a new UV environment and activate it:

    ```bash
    uv sync
    touch .env  # Create an empty .env if it doesn't exist
    ```

4. ## Environment Variables

Create a `.env` file in the project root to configure Beets-specific settings. Here's an example:

    ```
    # .env file

    # Path to the user's Beets configuration directory
    BEETSDIR=/.config/beets

    # Path to your music library
    LIBRARY_PATH=/music
    ```

    Beetiful manages its own `FLASK_PORT` entry in `.env` on first run.

5. **Running the Application**

To start the application, run the following command from the project root:

```bash
uv run app.py
```

On startup Beetiful prints its listening URL, e.g. `Beetiful listening on http://127.0.0.1:4732/` — open that in your browser.

By default Beetiful binds only to loopback (`127.0.0.1`) and runs under [waitress](https://github.com/Pylons/waitress).

#### Port selection

On first run (no `FLASK_PORT` in `.env`) Beetiful picks a random free port in the range 3000-8000, saves it to `.env` as `FLASK_PORT=N`, and reuses it on every subsequent run. The randomization makes the port stable per-host but not predictable across hosts, which is a trivial amount of security-by-obscurity. Still don't expose this to the web. If the first random pick is already in use, Beetiful-Redux retries up to 3 times before giving up.

To change the port: edit `FLASK_PORT` in `.env`, delete the line to re-randomize on next run, or pass `--port N` for a one-off override (this does not modify `.env`).

#### Flags

| Flag | Effect |
| --- | --- |
| `--port N` | One-off port override for this invocation. Does not modify `.env`. |
| `--allow-local-subnet` | Also accept connections from the host's local `/24` subnet (e.g. `192.168.1.0/24` if the host's LAN IP is `192.168.1.50`). Loopback is still allowed; everything else is rejected with HTTP 403. The host/subnet is detected automatically at startup. |
| `--debug` | Run with Flask's development server (auto-reload + interactive debugger). Off by default. |

Examples:

```bash
# Localhost only, production server (default)
uv run app.py

# Localhost + your LAN, production server
uv run app.py --allow-local-subnet

# Localhost only, Flask dev server with debugger
uv run app.py --debug

# LAN-accessible dev server on a one-off port
uv run app.py --allow-local-subnet --debug --port 8080
```

## Usage

- **Command Builder**: Execute standard Beets commands like `import`, `list`, `update`, `modify`, and more. Build commands interactively through the UI.
- **Library Management**: View your library with sorting and filtering options. Use the pagination buttons to navigate large libraries.
- **Config Editor**: Edit the Beets configuration directly from the web interface. The `save` button will update the `config.yaml` file.
- **Batch Mode**
- **Duplicate Detection**
