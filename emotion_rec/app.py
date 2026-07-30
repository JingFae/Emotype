"""Stable ASGI entry point.

Deployment and local commands may continue to use ``emotion_rec.app:app`` or,
from inside this directory, ``app:app``. The implementation lives in the API
package so the repository root no longer mixes application assembly with
domain, persistence, and provider modules.
"""

try:
    from emotion_rec.api import application as _application
except ModuleNotFoundError:  # Support ``uvicorn app:app`` from emotion_rec/.
    from api import application as _application  # type: ignore

app = _application.app
__all__ = [name for name in dir(_application) if not name.startswith("_")]


def __getattr__(name: str):
    """Delegate legacy attribute imports to the application module."""
    return getattr(_application, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_application)))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
