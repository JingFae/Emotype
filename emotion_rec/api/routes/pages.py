"""HTML page routes.

Static assets keep their existing ``/static/*`` public paths; this router only
maps stable page URLs to the corresponding HTML entry files.
"""

from fastapi import APIRouter
from fastapi.responses import FileResponse, Response

try:
    from emotion_rec.core.config import STATIC_DIR
except ModuleNotFoundError:  # Support ``uvicorn app:app`` from emotion_rec/.
    from core.config import STATIC_DIR  # type: ignore


router = APIRouter(include_in_schema=False)


def _page(filename: str) -> FileResponse:
    return FileResponse(STATIC_DIR / filename)


def _head() -> Response:
    return Response(status_code=200, media_type="text/html")


@router.get("/")
async def index():
    return _page("index.html")


@router.head("/")
async def index_head():
    return _head()


@router.get("/diary")
async def diary_page():
    return _page("diary.html")


@router.head("/diary")
async def diary_page_head():
    return _head()


@router.get("/review")
async def review_page():
    return _page("review.html")


@router.head("/review")
async def review_page_head():
    return _head()


@router.get("/records")
@router.get("/history")
async def records_page():
    return _page("records.html")


@router.head("/records")
@router.head("/history")
async def records_page_head():
    return _head()


@router.get("/essay")
async def essay_page():
    return _page("essay.html")


@router.head("/essay")
async def essay_page_head():
    return _head()


@router.get("/historyreview")
async def historyreview_page():
    return _page("historyreview.html")


@router.head("/historyreview")
async def historyreview_page_head():
    return _head()


@router.get("/emo-echo")
async def emo_echo_page():
    return _page("emo_echo.html")


@router.head("/emo-echo")
async def emo_echo_page_head():
    return _head()


@router.get("/login")
async def login_page():
    return _page("login.html")


@router.get("/profile")
async def profile_page():
    return _page("profile.html")


@router.get("/body")
@router.get("/body-sensation")
@router.get("/body_sensation")
async def body_sensation_page():
    return _page("body_sensation.html")


@router.head("/body")
@router.head("/body-sensation")
@router.head("/body_sensation")
async def body_sensation_page_head():
    return _head()

