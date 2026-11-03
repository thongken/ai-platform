from typing import Literal
from pydantic import BaseModel, Field


class SourceLocation(BaseModel):
    # Vị trí trong tài liệu PDF
    page: int | None = Field(default=None, ge=1)

    # Vị trí trong audio hoặc video (giây)
    start_seconds: float | None = Field(default=None, ge=0)
    end_seconds: float | None = Field(default=None, ge=0)


class ContentSection(BaseModel):
    section_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    source: SourceLocation | None = None


class ContentDocument(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    material_id: str = Field(min_length=1)
    source_type: Literal["audio", "video", "pdf"]
    title: str = Field(min_length=1)
    sections: list[ContentSection] = Field(min_length=1)
