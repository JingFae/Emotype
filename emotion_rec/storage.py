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
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    select,
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


def get_or_create_participant(participant_code: str, consent_version: str = "research-v1") -> dict[str, Any]:
    code = normalize_participant_code(participant_code)
    with SessionLocal() as session:
        participant = _participant_by_code(session, code)
        if participant is None:
            participant = Participant(participant_code=code, consent_version=consent_version)
            session.add(participant)
        participant.consent_version = consent_version or participant.consent_version
        participant.last_seen_at = now_utc()
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
        events = session.execute(
            select(UsageEvent)
            .where(UsageEvent.participant_id == participant.id)
            .order_by(UsageEvent.created_at.asc())
        ).scalars()
        return {
            "participant": participant_to_dict(participant),
            "diary_entries": [diary_entry_to_dict(row) for row in diaries],
            "usage_events": [usage_event_to_dict(row) for row in events],
        }


def export_all_data() -> dict[str, Any]:
    with SessionLocal() as session:
        participants = session.execute(select(Participant).order_by(Participant.created_at.asc())).scalars()
        diaries = session.execute(select(DiaryEntry).order_by(DiaryEntry.created_at.asc())).scalars()
        events = session.execute(select(UsageEvent).order_by(UsageEvent.created_at.asc())).scalars()
        return {
            "participants": [participant_to_dict(row) for row in participants],
            "diary_entries": [diary_entry_to_dict(row) for row in diaries],
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


def usage_event_to_dict(event: UsageEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "participant_id": event.participant_id,
        "event_type": event.event_type,
        "metadata_json": event.metadata_json,
        "created_at": isoformat(event.created_at),
    }


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
