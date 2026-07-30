"""Compatibility import for the renamed audio-model experiment.

The implementation is not a test suite; new code should import
``emotion_rec.tools.audio_model_demo`` directly.
"""

try:
    from emotion_rec.tools.audio_model_demo import *  # noqa: F401,F403
except ModuleNotFoundError:
    from tools.audio_model_demo import *  # type: ignore  # noqa: F401,F403
