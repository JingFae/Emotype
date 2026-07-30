"""Backward-compatible import path for the V-A mapping domain module."""

try:
    from emotion_rec.domain.emotion.mapping import *  # noqa: F401,F403
except ModuleNotFoundError:  # Support imports from inside emotion_rec/.
    from domain.emotion.mapping import *  # type: ignore  # noqa: F401,F403
