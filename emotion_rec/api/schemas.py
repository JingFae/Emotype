"""Pydantic request contracts shared by API route groups."""

from pydantic import BaseModel, Field


class TextAnalysisRequest(BaseModel):
    text: str = Field(default="", max_length=6000)
    intensity: float = Field(default=0.8, ge=0.0, le=1.0)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=4, max_length=128)
    display_name: str | None = Field(default=None, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=4, max_length=128)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=4, max_length=128)
    new_password: str = Field(min_length=4, max_length=128)


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=128)


class SettingsUpdateRequest(BaseModel):
    language: str | None = Field(default=None, max_length=8)
    theme: str | None = Field(default=None, max_length=32)


class ParticipantSessionRequest(BaseModel):
    participant_code: str = Field(min_length=2, max_length=64)
    consent_version: str = Field(default="research-v1", max_length=64)


class DiaryEntryRequest(BaseModel):
    participant_code: str = Field(min_length=2, max_length=64)
    raw_text: str = Field(default="", max_length=20000)
    transcript_text: str = Field(default="", max_length=20000)
    original_valence: float | None = None
    original_arousal: float | None = None
    original_label: str | None = Field(default=None, max_length=128)
    final_valence: float | None = None
    final_arousal: float | None = None
    final_label: str | None = Field(default=None, max_length=128)
    final_color: str | None = Field(default=None, max_length=16)
    candidates_json: list | dict | None = None
    text_emotion_json: dict | None = None
    va_mapping_json: dict | None = None


class UsageEventRequest(BaseModel):
    participant_code: str = Field(min_length=2, max_length=64)
    event_type: str = Field(min_length=1, max_length=80)
    metadata_json: dict = Field(default_factory=dict)


class FormalDiaryUpsertRequest(BaseModel):
    participant_code: str | None = Field(default=None, min_length=2, max_length=64)
    title: str = Field(default="", max_length=240)
    content: str = Field(default="", max_length=50000)
    physical_weather: str = Field(default="sunny", max_length=16)
    mood_weather: str = Field(default="sunny", max_length=16)
    source_entry_ids_json: list = Field(default_factory=list)
    save_type: str = Field(default="autosave", max_length=20)
    auto_analyze: bool = False
    is_draft: bool | None = None


class DiaryReflectRequest(BaseModel):
    participant_code: str | None = Field(default=None, min_length=2, max_length=64)
    image_analyses: list[dict] = Field(default_factory=list)


class ReviewReflectRequest(BaseModel):
    participant_code: str | None = Field(default=None, min_length=2, max_length=64)
    start_date: str = Field(..., max_length=10)
    end_date: str = Field(..., max_length=10)


class BodySensationAdviceRequest(BaseModel):
    participant_code: str | None = Field(default=None, max_length=64)
    journal_text: str = Field(default="", max_length=20000)
    selected_regions: list[dict] = Field(default_factory=list)
    symptoms: list[dict] = Field(default_factory=list)
    free_text: str = Field(default="", max_length=12000)
    include_recent_diaries: bool = True
    recent_diary_limit: int = Field(default=3, ge=0, le=10)


class CombinedAnalysisRequest(BaseModel):
    text: str = Field(default="", max_length=6000)
    image_analysis: dict | None = None


class EchoChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    session_id: str = Field(..., min_length=8, max_length=64)
    history: list[dict] = Field(default_factory=list)
    participant_code: str | None = Field(default=None, min_length=2, max_length=64)

