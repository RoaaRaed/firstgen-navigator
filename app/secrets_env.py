"""Copy the keys the app needs from Streamlit's secrets into environment variables.

On Streamlit Community Cloud the Groq key is stored under "Secrets" (TOML), not in a .env file,
but core/agent.py reads os.environ. Locally there is no secrets file and .env is used instead.
No Streamlit import here, so it can be tested.
"""
import os

KEYS = ("GROQ_API_KEY", "GROQ_MODEL")


def export_secrets(secrets, environ=None, keys=KEYS) -> list[str]:
    """Put each key found in `secrets` into `environ`, unless it is already set there.
    Returns the names it exported (never the values)."""
    environ = os.environ if environ is None else environ
    exported = []
    for key in keys:
        try:
            value = secrets[key]
        except Exception:  # not in the secrets, or no secrets file at all (local run)
            continue
        if value and key not in environ:
            environ[key] = str(value)
            exported.append(key)
    return exported
