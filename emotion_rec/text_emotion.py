"""Backward-compatible import path for semantic text-emotion inference."""

try:
    from emotion_rec.domain.emotion.text import *  # noqa: F401,F403
except ModuleNotFoundError:  # Support imports from inside emotion_rec/.
    from domain.emotion.text import *  # type: ignore  # noqa: F401,F403
