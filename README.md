# Beetiful

<img src="https://github.com/user-attachments/assets/7a8eabb9-bfc4-4f40-a07c-382d382e64f7" width="200" height="200">

Beetiful is a simple yet elegant web-based interface for managing your music library using [beets](https://beets.io/). It allows you to manage and interact with your music library through an intuitive GUI, while leveraging the power of beets on the backend.

## Features

- Command Builder for running Beets commands
- Config Editor to edit the `beets` configuration file directly from the interface
- Music Library Viewer with filtering, sorting, and pagination
- Simple integration with beets' advanced music management features

## Future additions
- Docker
- Plugin manager
- More commands
- Mobile friendly layout
## Installation

To install Beetiful, follow these steps:

1. **Clone the Repository**

    ```bash
    git clone https://github.com/tigerhawkvok/beetiful.git
    cd beetiful
    ```

2. **Create a Virtual Environment**

    It's recommended to use a Python virtual environment to keep your dependencies isolated.

    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3. **Install Dependencies**

    Install the required Python packages:

    ```bash
    pip install .
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

    Beetiful manages its own `FLASK_PORT` entry in `.env` — see "Running the Application" below.
5. **Running the Application**

To start the application, run the following command from the project root:

```bash
python app.py
```

On startup Beetiful prints its listening URL, e.g. `Beetiful listening on http://127.0.0.1:4732/` — open that in your browser.

By default Beetiful binds only to loopback (`127.0.0.1`) and runs under [waitress](https://github.com/Pylons/waitress), a production-grade WSGI server, so it won't trip Flask's "development server" warnings.

#### Port selection

On first run (no `FLASK_PORT` in `.env`) Beetiful picks a random free port in the range 3000-8000, saves it to `.env` as `FLASK_PORT=N`, and reuses it on every subsequent run. The randomization makes the port stable per-host but not predictable across hosts, which slightly shrinks the attack surface compared to a well-known default. If the first random pick is already in use, Beetiful retries up to 3 times before giving up.

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
python app.py

# Localhost + your LAN, production server
python app.py --allow-local-subnet

# Localhost only, Flask dev server with debugger
python app.py --debug

# LAN-accessible dev server on a one-off port
python app.py --allow-local-subnet --debug --port 8080
```

## Usage

- **Command Builder**: Execute standard Beets commands like `import`, `list`, `update`, `modify`, and more. Build commands interactively through the UI.
- **Library Management**: View your library with sorting and filtering options. Use the pagination buttons to navigate large libraries.
- **Config Editor**: Edit the Beets configuration directly from the web interface. The `save` button will update the `config.yaml` file.


![Unified Music Management](https://github.com/user-attachments/assets/4bc8887a-aee5-4450-a7f1-799c4eaf8c86)
