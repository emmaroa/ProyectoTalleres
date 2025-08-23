# WSGI entrypoint for Gunicorn in Render
# Assumes your Flask instance is named `app` in app.py
from app import app

# Optional: provide an alias for some hosting providers
application = app

if __name__ == "__main__":
    app.run()
