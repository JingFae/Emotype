"""Backward-compatible import path for the DeepSeek integration."""

try:
    from emotion_rec.integrations.llm import *  # noqa: F401,F403
except ModuleNotFoundError:  # Support imports from inside emotion_rec/.
    from integrations.llm import *  # type: ignore  # noqa: F401,F403
