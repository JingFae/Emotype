"""Dependency-free structural compatibility checks for the main service."""

from __future__ import annotations

import ast
import re
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parents[1]

EXPECTED_ROUTES = {
    ("GET", "/"), ("HEAD", "/"),
    ("GET", "/diary"), ("HEAD", "/diary"),
    ("GET", "/review"), ("HEAD", "/review"),
    ("GET", "/records"), ("HEAD", "/records"),
    ("GET", "/history"), ("HEAD", "/history"),
    ("GET", "/essay"), ("HEAD", "/essay"),
    ("GET", "/historyreview"), ("HEAD", "/historyreview"),
    ("GET", "/emo-echo"), ("HEAD", "/emo-echo"),
    ("GET", "/login"), ("GET", "/profile"),
    ("GET", "/body"), ("HEAD", "/body"),
    ("GET", "/body-sensation"), ("HEAD", "/body-sensation"),
    ("GET", "/body_sensation"), ("HEAD", "/body_sensation"),
    ("GET", "/healthz"),
    ("POST", "/api/auth/register"), ("POST", "/api/auth/login"),
    ("GET", "/api/auth/me"), ("PUT", "/api/auth/me"),
    ("PUT", "/api/auth/me/password"),
    ("GET", "/api/auth/me/settings"), ("PUT", "/api/auth/me/settings"),
    ("GET", "/api/admin/users"), ("GET", "/api/admin/users/{username}"),
    ("POST", "/participants/session"),
    ("GET", "/participants/{participant_code}/diaries"),
    ("DELETE", "/participants/{participant_code}/all-data"),
    ("POST", "/diaries"), ("POST", "/usage-events"),
    ("GET", "/participants/{participant_code}/export.json"),
    ("GET", "/participants/{participant_code}/export.csv"),
    ("GET", "/admin/export.json"), ("GET", "/admin/export.csv"),
    ("GET", "/api/diary"), ("GET", "/api/diary/context"),
    ("PUT", "/api/diary/by-date/{diary_date}"),
    ("POST", "/api/diary/by-date/{diary_date}/reflect"),
    ("GET", "/api/review/overview"), ("GET", "/api/review/report"),
    ("POST", "/api/review/reflect"), ("GET", "/api/records"),
    ("GET", "/api/admin/review/overview"),
    ("GET", "/api/admin/records"),
    ("POST", "/body-sensation/advice"),
    ("POST", "/api/uploads"), ("POST", "/api/analyze-combined"),
    ("POST", "/api/transcribe"), ("POST", "/analyze-text"),
    ("POST", "/predict"),
    ("GET", "/api/emo-echo/sessions"), ("POST", "/api/emo-echo/chat"),
}


def _routes_in(path: Path) -> set[tuple[str, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    routes: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not decorator.args:
                continue
            target = decorator.func
            route = decorator.args[0]
            if (
                isinstance(target, ast.Attribute)
                and target.attr in {"get", "post", "put", "delete", "head", "patch"}
                and isinstance(route, ast.Constant)
                and isinstance(route.value, str)
            ):
                routes.add((target.attr.upper(), route.value))
    return routes


def _missing_static_assets() -> list[str]:
    static_dir = PACKAGE_DIR / "static"
    pattern = re.compile(r"/static/([^?'\"#)]+)")
    missing: set[str] = set()
    for source in static_dir.iterdir():
        if source.suffix.lower() not in {".html", ".js", ".css"}:
            continue
        for relative in pattern.findall(source.read_text(encoding="utf-8")):
            if not (static_dir / relative).is_file():
                missing.add(f"{source.name} -> {relative}")
    return sorted(missing)


def main() -> int:
    actual_routes = set()
    actual_routes |= _routes_in(PACKAGE_DIR / "api" / "application.py")
    actual_routes |= _routes_in(PACKAGE_DIR / "api" / "routes" / "pages.py")

    missing_routes = EXPECTED_ROUTES - actual_routes
    unexpected_routes = actual_routes - EXPECTED_ROUTES
    missing_assets = _missing_static_assets()

    failures = []
    if missing_routes:
        failures.append(f"missing routes: {sorted(missing_routes)}")
    if unexpected_routes:
        failures.append(f"unexpected routes: {sorted(unexpected_routes)}")
    if missing_assets:
        failures.append(f"missing static assets: {missing_assets}")
    if not (PACKAGE_DIR / "shared" / "emotion_lexicon.json").is_file():
        failures.append("missing shared/emotion_lexicon.json")

    if failures:
        print("Contract check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(f"Contract check passed: {len(actual_routes)} routes and all static references are present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

