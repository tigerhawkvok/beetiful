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

    # Add any other environment-specific settings here
    PORT=
    ```
5. **Running the Application**

To start the application, run the following command from the project root:

```bash
python app.py
```

Open your browser and navigate to `http://127.0.0.1:3001`.

By default Beetiful binds only to loopback (`127.0.0.1`) and runs under [waitress](https://github.com/Pylons/waitress), a production-grade WSGI server, so it won't trip Flask's "development server" warnings.

#### Flags

| Flag | Effect |
| --- | --- |
| `--port N` | TCP port to bind. Defaults to the `FLASK_PORT` env var, or `3001`. |
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

# LAN-accessible dev server on a custom port
python app.py --allow-local-subnet --debug --port 8080
```

## Usage

- **Command Builder**: Execute standard Beets commands like `import`, `list`, `update`, `modify`, and more. Build commands interactively through the UI.
- **Library Management**: View your library with sorting and filtering options. Use the pagination buttons to navigate large libraries.
- **Config Editor**: Edit the Beets configuration directly from the web interface. The `save` button will update the `config.yaml` file.


![Unified Music Management](https://github.com/user-attachments/assets/4bc8887a-aee5-4450-a7f1-799c4eaf8c86)
