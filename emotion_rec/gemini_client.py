"""Backward-compatible import path for the Gemini vision integration."""

try:
    from emotion_rec.integrations.vision import *  # noqa: F401,F403
except ModuleNotFoundError:  # Support imports from inside emotion_rec/.
    from integrations.vision import *  # type: ignore  # noqa: F401,F403
