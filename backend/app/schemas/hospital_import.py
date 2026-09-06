"""Pydantic schemas for FR-22 Rule-Based Fuzzy Import."""
from pydantic import BaseModel, ConfigDict, Field


class SheetImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sheet_url: str = Field(min_length=1)
    target_table: str


class ColumnMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_column: str
    matched_field: str | None
    confidence: float
    sample_values: list[str]


class MatchReportOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    import_session_id: str
    target_table: str
    row_count: int
    columns: list[ColumnMatch]
    unmatched_columns: list[str]


class CommitImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # {source_column: target_field_name_or_null} — the user-confirmed (possibly
    # overridden) mapping; a null value means "ignore this column".
    column_mapping: dict[str, str | None]


class SkippedRow(BaseModel):
    row: int
    reason: str


class CommitResultOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    imported: int
    skipped: list[SkippedRow]
