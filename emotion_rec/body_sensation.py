"""Backward-compatible import path for the body-sensation service."""

try:
    from emotion_rec.services.body_sensation import *  # noqa: F401,F403
except ModuleNotFoundError:  # Support imports from inside emotion_rec/.
    from services.body_sensation import *  # type: ignore  # noqa: F401,F403
