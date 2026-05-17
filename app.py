import os
from beetiful import app
from dotenv import load_dotenv

load_dotenv()

DEFAULT_PORT = 3001

# Read port from environment variable, defaulting to 3001 if not set
try:
    port = int(os.getenv("FLASK_PORT", DEFAULT_PORT))
except ValueError:
    print("Invalid FLASK_PORT value. Using default port 3001.")
    port = DEFAULT_PORT

app.run(debug=True, host="0.0.0.0", port=port)
