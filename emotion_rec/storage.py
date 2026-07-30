"""Backward-compatible import path for the persistence repository."""

try:
    from emotion_rec.persistence.repository import *  # noqa: F401,F403
except ModuleNotFoundError:  # Support imports from inside emotion_rec/.
    from persistence.repository import *  # type: ignore  # noqa: F401,F403
