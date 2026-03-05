"""
WSGI entry point for Opalstack deployment.

On Opalstack, configure your Python/WSGI app to point to this file.
The WSGI callable is `application`.
"""

from app import create_app

application = create_app()

if __name__ == "__main__":
    application.run(debug=True, host="0.0.0.0", port=5000)
