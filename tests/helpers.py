import os
import sys


def fresh_app(tmp_data_dir):
    """Create a fresh Flask app using an isolated data directory."""

    os.environ["ACTIMISH_DATA_DIR"] = tmp_data_dir
    os.environ["ACTIMISH_DOMAIN"] = "example.test"
    os.environ["ACTIMISH_USERNAME"] = "testuser"
    os.environ["ACTIMISH_DISPLAY_NAME"] = "Test User"
    os.environ["ACTIMISH_BIO"] = ""
    os.environ["ACTIMISH_SECRET_KEY"] = "test-secret-key"

    # Best-effort cleanup of any previously-imported SQLAlchemy engines.
    old_models = sys.modules.get("models")
    if old_models is not None:
        try:
            old_models.db.session.remove()
            old_models.db.engine.dispose()
        except Exception:
            pass

    for name in list(sys.modules.keys()):
        if name in ("app", "config", "models"):
            sys.modules.pop(name, None)
        elif name.startswith("routes.") or name.startswith("utils."):
            sys.modules.pop(name, None)

    import app
    import models

    flask_app = app.create_app()
    flask_app.testing = True
    return flask_app, models


def make_token(flask_app, models, access_token="testtoken"):
    """Create a basic OAuth app + bearer token for auth-required endpoints."""

    with flask_app.app_context():
        app_obj = models.OAuthApp(
            client_id="cid",
            client_secret="csecret",
            client_name="TestApp",
            redirect_uris="urn:ietf:wg:oauth:2.0:oob",
            scopes="read write",
        )
        models.db.session.add(app_obj)
        models.db.session.commit()

        token = models.OAuthToken(
            access_token=access_token,
            scope="read write",
            app_id=app_obj.id,
            revoked=False,
        )
        models.db.session.add(token)
        models.db.session.commit()


def close_db(flask_app, models):
    try:
        with flask_app.app_context():
            models.db.session.remove()
            models.db.engine.dispose()
    except Exception:
        pass
