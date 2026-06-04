
from __future__ import annotations
import csv
import io
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Boolean,
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    inspect as sa_inspect,
    select,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATABASE_URL = f"sqlite:///{BASE_DIR / 'emomirror_data.sqlite3'}"
PARTICIPANT_CODE_RE = re.compile(r"^[A-Za-z0-9_-]{2,64}$")


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL).strip()
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://") and "+psycopg" not in url:
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


class Base(DeclarativeBase):
    pass


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    consent_version: Mapped[str] = mapped_column(String(64), default="research-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: now_utc())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: now_utc())


class DiaryEntry(Base):
    __tablename__ = "diary_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id"), index=True)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    transcript_text: Mapped[str] = mapped_column(Text, default="")
    original_valence: Mapped[float | None] = mapped_column(Float, nullable=True)
    original_arousal: Mapped[float | None] = mapped_column(Float, nullable=True)
    original_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    final_valence: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_arousal: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    final_color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    candidates_json: Mapped[Any] = mapped_column(JSON, default=list)
    text_emotion_json: Mapped[Any] = mapped_column(JSON, default=dict)
    va_mapping_json: Mapped[Any] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: now_utc())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: now_utc())


class FormalDiary(Base):
    __tablename__ = "formal_diaries"
    __table_args__ = (
        UniqueConstraint("participant_id", "diary_date", name="uq_formal_diaries_participant_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id"), index=True)
    diary_date: Mapped[str] = mapped_column(String(10), index=True)
    title: Mapped[str] = mapped_column(String(240), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    physical_weather: Mapped[str] = mapped_column(String(16), default="sunny")
    mood_weather: Mapped[str] = mapped_column(String(16), default="sunny")
    source_entry_ids_json: Mapped[Any] = mapped_column(JSON, default=list)
    valence: Mapped[float | None] = mapped_column(Float, nullable=True)
    arousal: Mapped[float | None] = mapped_column(Float, nullable=True)
    primary_emotion: Mapped[str | None] = mapped_column(String(128), nullable=True)
    secondary_emotions_json: Mapped[Any] = mapped_column(JSON, default=list)
    fine_emotions_json: Mapped[Any] = mapped_column(JSON, default=list)
    body_signals_json: Mapped[Any] = mapped_column(JSON, default=list)
    emotion_color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    emotion_color_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reflection_json: Mapped[Any] = mapped_column(JSON, default=dict)
    analysis_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_draft: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: now_utc())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: now_utc())
    last_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    metadata_json: Mapped[Any] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: now_utc())


engine = create_engine(
    _database_url(),
    connect_args={"check_same_thread": False} if _database_url().startswith("sqlite") else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def init_database() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_schema()


def _ensure_sqlite_schema() -> None:
    """Keep older local SQLite files compatible with the current ORM schema."""
    if engine.dialect.name != "sqlite":
        return

    inspector = sa_inspect(engine)
    if "formal_diaries" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("formal_diaries")}
    column_sql = {
        "title": "VARCHAR(240) DEFAULT ''",
        "content": "TEXT DEFAULT ''",
        "physical_weather": "VARCHAR(16) DEFAULT 'sunny'",
        "mood_weather": "VARCHAR(16) DEFAULT 'sunny'",
        "source_entry_ids_json": "JSON",
        "valence": "FLOAT",
        "arousal": "FLOAT",
        "primary_emotion": "VARCHAR(128)",
        "secondary_emotions_json": "JSON",
        "fine_emotions_json": "JSON",
        "body_signals_json": "JSON",
        "emotion_color": "VARCHAR(16)",
        "emotion_color_name": "VARCHAR(64)",
        "reflection_json": "JSON",
        "analysis_version": "VARCHAR(64)",
        "is_draft": "BOOLEAN DEFAULT 1",
        "created_at": "DATETIME",
        "updated_at": "DATETIME",
        "last_analyzed_at": "DATETIME",
    }
    missing = [(name, ddl) for name, ddl in column_sql.items() if name not in existing]

    with engine.begin() as connection:
        for name, ddl in missing:
            connection.execute(text(f"ALTER TABLE formal_diaries ADD COLUMN {name} {ddl}"))
        try:
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "uq_formal_diaries_participant_date_idx "
                    "ON formal_diaries (participant_id, diary_date)"
                )
            )
        except Exception as error:
            print(f"Formal diary unique index migration skipped: {error}")


def normalize_participant_code(code: str) -> str:
    normalized = str(code or "").strip()
    if not PARTICIPANT_CODE_RE.match(normalized):
        raise ValueError("Participant code must be 2-64 letters, numbers, underscores, or dashes.")
    return normalized


def _participant_by_code(session: Session, participant_code: str) -> Participant | None:
    code = normalize_participant_code(participant_code)
    return session.execute(
        select(Participant).where(Participant.participant_code == code)
    ).scalar_one_or_none()


def _get_or_create_participant_row(
    session: Session,
    participant_code: str,
    consent_version: str = "research-v1",
) -> Participant:
    code = normalize_participant_code(participant_code)
    participant = _participant_by_code(session, code)
    if participant is None:
        participant = Participant(participant_code=code, consent_version=consent_version)
        session.add(participant)
        session.flush()
    elif consent_version != "diary-v1":
        participant.consent_version = consent_version or participant.consent_version
    participant.last_seen_at = now_utc()
    return participant


def get_or_create_participant(participant_code: str, consent_version: str = "research-v1") -> dict[str, Any]:
    with SessionLocal() as session:
        participant = _get_or_create_participant_row(session, participant_code, consent_version)
        session.commit()
        session.refresh(participant)
        return participant_to_dict(participant)


def log_usage_event(
    participant_code: str,
    event_type: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with SessionLocal() as session:
        participant = _participant_by_code(session, participant_code)
        if participant is None:
            raise ValueError("Participant not found.")
        participant.last_seen_at = now_utc()
        event = UsageEvent(
            participant_id=participant.id,
            event_type=str(event_type or "unknown")[:80],
            metadata_json=safe_json(metadata or {}),
        )
        session.add(event)
        session.commit()
        session.refresh(event)
        return usage_event_to_dict(event)


def create_diary_entry(participant_code: str, payload: dict[str, Any]) -> dict[str, Any]:
    with SessionLocal() as session:
        participant = _participant_by_code(session, participant_code)
        if participant is None:
            raise ValueError("Participant not found.")
        participant.last_seen_at = now_utc()
        entry = DiaryEntry(
            participant_id=participant.id,
            raw_text=str(payload.get("raw_text", "")),
            transcript_text=str(payload.get("transcript_text", "")),
            original_valence=optional_float(payload.get("original_valence")),
            original_arousal=optional_float(payload.get("original_arousal")),
            original_label=optional_str(payload.get("original_label"), 128),
            final_valence=optional_float(payload.get("final_valence")),
            final_arousal=optional_float(payload.get("final_arousal")),
            final_label=optional_str(payload.get("final_label"), 128),
            final_color=optional_str(payload.get("final_color"), 16),
            candidates_json=safe_json(payload.get("candidates_json", [])),
            text_emotion_json=safe_json(payload.get("text_emotion_json", {})),
            va_mapping_json=safe_json(payload.get("va_mapping_json", {})),
        )
        session.add(entry)
        session.flush()
        session.add(
            UsageEvent(
                participant_id=participant.id,
                event_type="diary_saved",
                metadata_json={
                    "diary_entry_id": entry.id,
                    "final_label": entry.final_label,
                    "final_valence": entry.final_valence,
                    "final_arousal": entry.final_arousal,
                    "text_length": len(entry.raw_text),
                },
            )
        )
        session.commit()
        session.refresh(entry)
        return diary_entry_to_dict(entry)


def list_diary_entries(participant_code: str) -> list[dict[str, Any]]:
    with SessionLocal() as session:
        participant = _participant_by_code(session, participant_code)
        if participant is None:
            raise ValueError("Participant not found.")
        rows = session.execute(
            select(DiaryEntry)
            .where(DiaryEntry.participant_id == participant.id)
            .order_by(DiaryEntry.created_at.desc())
        ).scalars()
        return [diary_entry_to_dict(row) for row in rows]


def normalize_diary_date(value: str) -> str:
    text = str(value or "").strip()
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("diary_date must use YYYY-MM-DD.") from exc
    return text


def empty_formal_diary(participant_code: str, diary_date: str) -> dict[str, Any]:
    return {
        "id": None,
        "participant_id": None,
        "participant_code": normalize_participant_code(participant_code or "local"),
        "diary_date": normalize_diary_date(diary_date),
        "title": "",
        "content": "",
        "physical_weather": "sunny",
        "mood_weather": "sunny",
        "source_entry_ids_json": [],
        "valence": None,
        "arousal": None,
        "primary_emotion": None,
        "secondary_emotions_json": [],
        "fine_emotions_json": [],
        "body_signals_json": [],
        "emotion_color": None,
        "emotion_color_name": None,
        "reflection_json": {},
        "analysis_version": None,
        "is_draft": True,
        "created_at": None,
        "updated_at": None,
        "last_analyzed_at": None,
        "analysis_pending": False,
    }


def get_formal_diary_by_date(participant_code: str, diary_date: str) -> dict[str, Any]:
    code = normalize_participant_code(participant_code or "local")
    date_text = normalize_diary_date(diary_date)
    with SessionLocal() as session:
        participant = _participant_by_code(session, code)
        if participant is None:
            return empty_formal_diary(code, date_text)
        diary = session.execute(
            select(FormalDiary)
            .where(FormalDiary.participant_id == participant.id, FormalDiary.diary_date == date_text)
        ).scalar_one_or_none()
        if diary is None:
            return empty_formal_diary(code, date_text)
        return formal_diary_to_dict(diary, participant.participant_code)


def upsert_formal_diary_by_date(
    participant_code: str,
    diary_date: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    code = normalize_participant_code(participant_code or "local")
    date_text = normalize_diary_date(diary_date)
    payload = payload or {}
    with SessionLocal() as session:
        participant = _get_or_create_participant_row(session, code, "diary-v1")
        diary = session.execute(
            select(FormalDiary)
            .where(FormalDiary.participant_id == participant.id, FormalDiary.diary_date == date_text)
        ).scalar_one_or_none()
        if diary is None:
            diary = FormalDiary(participant_id=participant.id, diary_date=date_text)
            session.add(diary)
            session.flush()

        tracked_before = (
            diary.title,
            diary.content,
            diary.physical_weather,
            diary.mood_weather,
            json.dumps(diary.source_entry_ids_json or [], sort_keys=True, default=str),
        )

        if "title" in payload:
            diary.title = str(payload.get("title") or "")[:240]
        if "content" in payload:
            diary.content = str(payload.get("content") or "")[:50000]
        if "physical_weather" in payload:
            diary.physical_weather = optional_str(payload.get("physical_weather"), 16) or "sunny"
        if "mood_weather" in payload:
            diary.mood_weather = optional_str(payload.get("mood_weather"), 16) or "sunny"
        if "source_entry_ids_json" in payload:
            diary.source_entry_ids_json = safe_json(payload.get("source_entry_ids_json") or [])

        save_type = str(payload.get("save_type") or "autosave").strip().lower()
        if payload.get("is_draft") is not None:
            diary.is_draft = bool(payload.get("is_draft"))
        elif save_type == "manual":
            diary.is_draft = False
        elif save_type == "autosave":
            diary.is_draft = True

        tracked_after = (
            diary.title,
            diary.content,
            diary.physical_weather,
            diary.mood_weather,
            json.dumps(diary.source_entry_ids_json or [], sort_keys=True, default=str),
        )
        if tracked_before != tracked_after and diary.last_analyzed_at is not None:
            version = diary.analysis_version or "diary-reflection-v1"
            diary.analysis_version = version if version.endswith(":stale") else f"{version}:stale"

        diary.updated_at = now_utc()
        session.commit()
        session.refresh(diary)
        return formal_diary_to_dict(diary, participant.participant_code)


def update_formal_diary_reflection(
    participant_code: str,
    diary_date: str,
    analysis: dict[str, Any],
) -> dict[str, Any]:
    code = normalize_participant_code(participant_code or "local")
    date_text = normalize_diary_date(diary_date)
    analysis = analysis or {}
    with SessionLocal() as session:
        participant = _get_or_create_participant_row(session, code, "diary-v1")
        diary = session.execute(
            select(FormalDiary)
            .where(FormalDiary.participant_id == participant.id, FormalDiary.diary_date == date_text)
        ).scalar_one_or_none()
        if diary is None:
            diary = FormalDiary(participant_id=participant.id, diary_date=date_text)
            session.add(diary)
            session.flush()

        diary.valence = optional_float(analysis.get("valence"))
        diary.arousal = optional_float(analysis.get("arousal"))
        diary.primary_emotion = optional_str(analysis.get("primary_emotion"), 128)
        diary.secondary_emotions_json = safe_json(analysis.get("secondary_emotions_json") or [])
        diary.fine_emotions_json = safe_json(analysis.get("fine_emotions_json") or [])
        diary.body_signals_json = safe_json(analysis.get("body_signals_json") or [])
        diary.emotion_color = optional_str(analysis.get("emotion_color"), 16)
        diary.emotion_color_name = optional_str(analysis.get("emotion_color_name"), 64)
        diary.reflection_json = safe_json(analysis.get("reflection_json") or {})
        diary.analysis_version = optional_str(analysis.get("analysis_version"), 64) or "diary-reflection-v1"
        diary.last_analyzed_at = now_utc()
        diary.updated_at = diary.last_analyzed_at
        if "is_draft" in analysis:
            diary.is_draft = bool(analysis.get("is_draft"))
        session.commit()
        session.refresh(diary)
        return formal_diary_to_dict(diary, participant.participant_code)


def list_diary_context(participant_code: str, diary_date: str) -> list[dict[str, Any]]:
    code = normalize_participant_code(participant_code or "local")
    date_text = normalize_diary_date(diary_date)
    with SessionLocal() as session:
        participant = _participant_by_code(session, code)
        if participant is None:
            return []

        journal_rows = session.execute(
            select(DiaryEntry)
            .where(DiaryEntry.participant_id == participant.id)
            .order_by(DiaryEntry.created_at.asc())
        ).scalars()
        events = session.execute(
            select(UsageEvent)
            .where(UsageEvent.participant_id == participant.id)
            .order_by(UsageEvent.created_at.asc())
        ).scalars()

        items: list[dict[str, Any]] = []
        for entry in journal_rows:
            created_at = isoformat(entry.created_at)
            if not _iso_date_matches(created_at, date_text):
                continue
            text = str(entry.raw_text or entry.transcript_text or "").strip()
            summary = text[:180] + ("..." if len(text) > 180 else "")
            items.append({
                "source": "journal",
                "id": entry.id,
                "time": created_at,
                "summary": summary or "随手记记录",
                "valence": entry.final_valence if entry.final_valence is not None else entry.original_valence,
                "arousal": entry.final_arousal if entry.final_arousal is not None else entry.original_arousal,
                "primary_emotion": entry.final_label or entry.original_label or "中性",
            })

        for event in events:
            created_at = isoformat(event.created_at)
            if not _iso_date_matches(created_at, date_text):
                continue
            context_item = usage_event_to_diary_context(event)
            if context_item:
                items.append(context_item)

        return sorted(items, key=lambda item: str(item.get("time") or ""))


def export_participant_data(participant_code: str) -> dict[str, Any]:
    with SessionLocal() as session:
        participant = _participant_by_code(session, participant_code)
        if participant is None:
            raise ValueError("Participant not found.")
        diaries = session.execute(
            select(DiaryEntry)
            .where(DiaryEntry.participant_id == participant.id)
            .order_by(DiaryEntry.created_at.asc())
        ).scalars()
        formal_diaries = session.execute(
            select(FormalDiary)
            .where(FormalDiary.participant_id == participant.id)
            .order_by(FormalDiary.diary_date.asc())
        ).scalars()
        events = session.execute(
            select(UsageEvent)
            .where(UsageEvent.participant_id == participant.id)
            .order_by(UsageEvent.created_at.asc())
        ).scalars()
        return {
            "participant": participant_to_dict(participant),
            "diary_entries": [diary_entry_to_dict(row) for row in diaries],
            "formal_diaries": [formal_diary_to_dict(row, participant.participant_code) for row in formal_diaries],
            "usage_events": [usage_event_to_dict(row) for row in events],
        }


def export_all_data() -> dict[str, Any]:
    with SessionLocal() as session:
        participants = session.execute(select(Participant).order_by(Participant.created_at.asc())).scalars()
        diaries = session.execute(select(DiaryEntry).order_by(DiaryEntry.created_at.asc())).scalars()
        formal_diaries = session.execute(select(FormalDiary).order_by(FormalDiary.diary_date.asc())).scalars()
        events = session.execute(select(UsageEvent).order_by(UsageEvent.created_at.asc())).scalars()
        participant_rows = [participant_to_dict(row) for row in participants]
        participants_by_id = {item["id"]: item["participant_code"] for item in participant_rows}
        return {
            "participants": participant_rows,
            "diary_entries": [diary_entry_to_dict(row) for row in diaries],
            "formal_diaries": [formal_diary_to_dict(row, participants_by_id.get(row.participant_id, "")) for row in formal_diaries],
            "usage_events": [usage_event_to_dict(row) for row in events],
        }


def export_participant_csv(participant_code: str) -> str:
    return export_bundle_to_csv(export_participant_data(participant_code))


def export_all_csv() -> str:
    return export_bundle_to_csv(export_all_data())


def export_bundle_to_csv(bundle: dict[str, Any]) -> str:
    output = io.StringIO()
    fields = [
        "record_type",
        "participant_code",
        "id",
        "created_at",
        "updated_at",
        "event_type",
        "raw_text",
        "transcript_text",
        "original_label",
        "original_valence",
        "original_arousal",
        "final_label",
        "final_valence",
        "final_arousal",
        "final_color",
        "json_payload",
    ]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()

    participants_by_id = {
        item["id"]: item["participant_code"]
        for item in bundle.get("participants", [])
    }
    participant = bundle.get("participant")
    if participant:
        participants_by_id[participant["id"]] = participant["participant_code"]
        writer.writerow(
            {
                "record_type": "participant",
                "participant_code": participant["participant_code"],
                "id": participant["id"],
                "created_at": participant["created_at"],
                "updated_at": participant["last_seen_at"],
                "json_payload": json.dumps(participant, ensure_ascii=False),
            }
        )
    for participant_row in bundle.get("participants", []):
        writer.writerow(
            {
                "record_type": "participant",
                "participant_code": participant_row["participant_code"],
                "id": participant_row["id"],
                "created_at": participant_row["created_at"],
                "updated_at": participant_row["last_seen_at"],
                "json_payload": json.dumps(participant_row, ensure_ascii=False),
            }
        )

    for entry in bundle.get("diary_entries", []):
        writer.writerow(
            {
                "record_type": "diary_entry",
                "participant_code": participants_by_id.get(entry["participant_id"], ""),
                "id": entry["id"],
                "created_at": entry["created_at"],
                "updated_at": entry["updated_at"],
                "raw_text": entry["raw_text"],
                "transcript_text": entry["transcript_text"],
                "original_label": entry["original_label"],
                "original_valence": entry["original_valence"],
                "original_arousal": entry["original_arousal"],
                "final_label": entry["final_label"],
                "final_valence": entry["final_valence"],
                "final_arousal": entry["final_arousal"],
                "final_color": entry["final_color"],
                "json_payload": json.dumps(entry, ensure_ascii=False),
            }
        )

    for diary in bundle.get("formal_diaries", []):
        writer.writerow(
            {
                "record_type": "formal_diary",
                "participant_code": diary.get("participant_code") or participants_by_id.get(diary.get("participant_id"), ""),
                "id": diary["id"],
                "created_at": diary["created_at"],
                "updated_at": diary["updated_at"],
                "raw_text": diary.get("content", ""),
                "final_label": diary.get("primary_emotion"),
                "final_valence": diary.get("valence"),
                "final_arousal": diary.get("arousal"),
                "final_color": diary.get("emotion_color"),
                "json_payload": json.dumps(diary, ensure_ascii=False),
            }
        )

    for event in bundle.get("usage_events", []):
        writer.writerow(
            {
                "record_type": "usage_event",
                "participant_code": participants_by_id.get(event["participant_id"], ""),
                "id": event["id"],
                "created_at": event["created_at"],
                "event_type": event["event_type"],
                "json_payload": json.dumps(event, ensure_ascii=False),
            }
        )

    return output.getvalue()


def participant_to_dict(participant: Participant) -> dict[str, Any]:
    return {
        "id": participant.id,
        "participant_code": participant.participant_code,
        "consent_version": participant.consent_version,
        "created_at": isoformat(participant.created_at),
        "last_seen_at": isoformat(participant.last_seen_at),
    }


def diary_entry_to_dict(entry: DiaryEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "participant_id": entry.participant_id,
        "raw_text": entry.raw_text,
        "transcript_text": entry.transcript_text,
        "original_valence": entry.original_valence,
        "original_arousal": entry.original_arousal,
        "original_label": entry.original_label,
        "final_valence": entry.final_valence,
        "final_arousal": entry.final_arousal,
        "final_label": entry.final_label,
        "final_color": entry.final_color,
        "candidates_json": entry.candidates_json,
        "text_emotion_json": entry.text_emotion_json,
        "va_mapping_json": entry.va_mapping_json,
        "created_at": isoformat(entry.created_at),
        "updated_at": isoformat(entry.updated_at),
    }


def formal_diary_to_dict(diary: FormalDiary, participant_code: str | None = None) -> dict[str, Any]:
    return {
        "id": diary.id,
        "participant_id": diary.participant_id,
        "participant_code": participant_code,
        "diary_date": diary.diary_date,
        "title": diary.title,
        "content": diary.content,
        "physical_weather": diary.physical_weather,
        "mood_weather": diary.mood_weather,
        "source_entry_ids_json": diary.source_entry_ids_json or [],
        "valence": diary.valence,
        "arousal": diary.arousal,
        "primary_emotion": diary.primary_emotion,
        "secondary_emotions_json": diary.secondary_emotions_json or [],
        "fine_emotions_json": diary.fine_emotions_json or [],
        "body_signals_json": diary.body_signals_json or [],
        "emotion_color": diary.emotion_color,
        "emotion_color_name": diary.emotion_color_name,
        "reflection_json": diary.reflection_json or {},
        "analysis_version": diary.analysis_version,
        "is_draft": diary.is_draft,
        "created_at": isoformat(diary.created_at),
        "updated_at": isoformat(diary.updated_at),
        "last_analyzed_at": isoformat(diary.last_analyzed_at),
        "analysis_pending": formal_diary_analysis_pending(diary),
    }


def formal_diary_analysis_pending(diary: FormalDiary) -> bool:
    if not str(diary.content or "").strip():
        return False
    if diary.last_analyzed_at is None:
        return True
    return str(diary.analysis_version or "").endswith(":stale")


def usage_event_to_diary_context(event: UsageEvent) -> dict[str, Any] | None:
    event_type = str(event.event_type or "")
    metadata = event.metadata_json if isinstance(event.metadata_json, dict) else {}
    created_at = isoformat(event.created_at)

    if event_type == "body_sensation_advice":
        symptoms = metadata.get("symptoms") or []
        regions = metadata.get("selected_regions") or []
        symptom_labels = [str(item.get("label") or item.get("id") or "") for item in symptoms if isinstance(item, dict)]
        region_labels = [str(item.get("label") or item.get("id") or "") for item in regions if isinstance(item, dict)]
        parts = [item for item in ["、".join(region_labels), "、".join(symptom_labels)] if item]
        return {
            "source": "body_sensation",
            "id": event.id,
            "time": created_at,
            "summary": "身体感受：" + ("；".join(parts) if parts else "已生成身体感受建议"),
            "valence": optional_float(metadata.get("valence")),
            "arousal": optional_float(metadata.get("arousal")),
            "primary_emotion": metadata.get("primary_label") or "身体感受",
        }

    if event_type == "custom_label_applied":
        return {
            "source": "realtime_emotion",
            "id": event.id,
            "time": created_at,
            "summary": f"实时情绪标签调整为：{metadata.get('label') or '未命名'}",
            "valence": optional_float(metadata.get("valence")),
            "arousal": optional_float(metadata.get("arousal")),
            "primary_emotion": metadata.get("label") or "自定义情绪",
        }

    if event_type == "va_coordinate_adjusted":
        return {
            "source": "realtime_emotion",
            "id": event.id,
            "time": created_at,
            "summary": "实时 V-A 坐标被手动调整",
            "valence": optional_float(metadata.get("valence")),
            "arousal": optional_float(metadata.get("arousal")),
            "primary_emotion": metadata.get("label") or "V-A 调整",
        }

    return None


def usage_event_to_dict(event: UsageEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "participant_id": event.participant_id,
        "event_type": event.event_type,
        "metadata_json": event.metadata_json,
        "created_at": isoformat(event.created_at),
    }


def _iso_date_matches(value: str | None, diary_date: str) -> bool:
    return bool(value and str(value).startswith(diary_date))


def isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def optional_str(value: Any, max_length: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:max_length] if text else None


def safe_json(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        return json.loads(json.dumps(value, default=str))
