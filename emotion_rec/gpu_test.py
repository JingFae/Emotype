"""Compatibility entry point; prefer ``python -m emotion_rec.tools.gpu_check``."""

try:
    from emotion_rec.tools.gpu_check import *  # noqa: F401,F403
except ModuleNotFoundError:
    from tools.gpu_check import *  # type: ignore  # noqa: F401,F403
