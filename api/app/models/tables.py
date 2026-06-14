from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Score(Base):
    __tablename__ = "scores"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    imslp_id: Mapped[str | None] = mapped_column(String(255))
    num_pages: Mapped[int | None] = mapped_column(Integer)
    file_size: Mapped[int | None] = mapped_column(Integer)
    file_hash: Mapped[str | None] = mapped_column(String(255), unique=True)
    import_start: Mapped[datetime | None] = mapped_column(DateTime)
    import_complete: Mapped[datetime | None] = mapped_column(DateTime)
    convert_start: Mapped[datetime | None] = mapped_column(DateTime)
    convert_complete: Mapped[datetime | None] = mapped_column(DateTime)
    analysis_start: Mapped[datetime | None] = mapped_column(DateTime)
    analysis_complete: Mapped[datetime | None] = mapped_column(DateTime)
    num_downloads: Mapped[int] = mapped_column(Integer, default=0)
    s3: Mapped[bool] = mapped_column(Boolean, default=False)


class Partset(Base):
    __tablename__ = "partsets"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    private_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    score_id: Mapped[str | None] = mapped_column(String(255), index=True)
    imslp_id: Mapped[str | None] = mapped_column(String(255))
    tmpdir: Mapped[str | None] = mapped_column(String(255))
    create_ts: Mapped[datetime | None] = mapped_column(DateTime)
    mod_ts: Mapped[datetime | None] = mapped_column(DateTime)
    last_access: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    parts_ready: Mapped[bool | None] = mapped_column(Boolean, default=False)
    title: Mapped[str | None] = mapped_column(String(255))
    composer: Mapped[str | None] = mapped_column(String(255))
    publisher: Mapped[str | None] = mapped_column(String(255))
    copyright: Mapped[str | None] = mapped_column(
        Enum("before 1923", "after 1923", "unknown", name="copyright_enum")
    )
    user_id: Mapped[str | None] = mapped_column(String(255))
    num_downloads: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str | None] = mapped_column(
        Enum("import", "convert", "analysis", "cut", "paste", name="status_enum")
    )
    error: Mapped[str | None] = mapped_column(
        Enum(
            "import",
            "import_size",
            "convert",
            "analysis",
            "cut",
            "paste",
            name="error_enum",
        )
    )
    error_message: Mapped[str | None] = mapped_column(String(512))
    error_ts: Mapped[datetime | None] = mapped_column(DateTime)
    last_job_id: Mapped[str | None] = mapped_column(String(32))
    import_start: Mapped[datetime | None] = mapped_column(DateTime)
    import_complete: Mapped[datetime | None] = mapped_column(DateTime)
    import_progress: Mapped[float] = mapped_column(Float, default=0.0)
    convert_start: Mapped[datetime | None] = mapped_column(DateTime)
    convert_complete: Mapped[datetime | None] = mapped_column(DateTime)
    convert_progress: Mapped[float] = mapped_column(Float, default=0.0)
    analysis_start: Mapped[datetime | None] = mapped_column(DateTime)
    analysis_complete: Mapped[datetime | None] = mapped_column(DateTime)
    analysis_progress: Mapped[float] = mapped_column(Float, default=0.0)
    cut_start: Mapped[datetime | None] = mapped_column(DateTime)
    cut_complete: Mapped[datetime | None] = mapped_column(DateTime)
    cut_progress: Mapped[float] = mapped_column(Float, default=0.0)
    paste_start: Mapped[datetime | None] = mapped_column(DateTime)
    paste_complete: Mapped[datetime | None] = mapped_column(DateTime)
    paste_progress: Mapped[float] = mapped_column(Float, default=0.0)


class OriginalPage(Base):
    __tablename__ = "original_pages"

    score_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    page: Mapped[int] = mapped_column(Integer, primary_key=True)
    left_margin: Mapped[float | None] = mapped_column(Float)
    right_margin: Mapped[float | None] = mapped_column(Float)
    rotation: Mapped[float | None] = mapped_column(Float)


class OriginalSegment(Base):
    __tablename__ = "original_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    score_id: Mapped[str] = mapped_column(String(255), index=True)
    page: Mapped[int | None] = mapped_column(Integer)
    top: Mapped[float | None] = mapped_column(Float)
    bottom: Mapped[float | None] = mapped_column(Float)


class Page(Base):
    __tablename__ = "pages"

    partset_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    page: Mapped[int] = mapped_column(Integer, primary_key=True)
    left_margin: Mapped[float | None] = mapped_column(Float)
    right_margin: Mapped[float | None] = mapped_column(Float)
    rotation: Mapped[float | None] = mapped_column(Float)


class Segment(Base):
    __tablename__ = "segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    partset_id: Mapped[str] = mapped_column(String(255), index=True)
    page: Mapped[int | None] = mapped_column(Integer)
    top: Mapped[float | None] = mapped_column(Float)
    bottom: Mapped[float | None] = mapped_column(Float)
    tags: Mapped[str | None] = mapped_column(String(255))
    tag_is_suggestion: Mapped[bool] = mapped_column(Boolean, default=False)
    label: Mapped[str | None] = mapped_column(String(255))
    label_is_suggestion: Mapped[bool] = mapped_column(Boolean, default=False)


class Break(Base):
    __tablename__ = "breaks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    partset_id: Mapped[str] = mapped_column(String(255), index=True)
    tag: Mapped[str | None] = mapped_column(String(255))
    break_: Mapped[int | None] = mapped_column("break", Integer)


class Part(Base):
    __tablename__ = "parts"

    partset_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    tag: Mapped[str] = mapped_column(String(255), primary_key=True)
    spacing: Mapped[float | None] = mapped_column(Float)
    combined: Mapped[bool | None] = mapped_column(Boolean)
    file_name: Mapped[str | None] = mapped_column(String(255))


class Download(Base):
    __tablename__ = "downloads"

    score_id: Mapped[str | None] = mapped_column(String(255), index=True)
    partset_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    tag: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(255))
    bcookie: Mapped[str | None] = mapped_column(String(255))
    ts: Mapped[datetime] = mapped_column(DateTime, primary_key=True)


class ImslpInfo(Base):
    __tablename__ = "imslp_info"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    title: Mapped[str | None] = mapped_column(String(255))
    composer: Mapped[str | None] = mapped_column(String(255))
    publisher: Mapped[str | None] = mapped_column(String(255))
    copyright: Mapped[str | None] = mapped_column(String(255))
    url: Mapped[str | None] = mapped_column(String(255))
    file_type: Mapped[str | None] = mapped_column(String(255))


class Favorite(Base):
    __tablename__ = "favorites"

    partset_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    admin: Mapped[bool | None] = mapped_column(Boolean)
    ts: Mapped[datetime | None] = mapped_column(DateTime)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255))
    ts: Mapped[datetime | None] = mapped_column(DateTime)


class Friend(Base):
    __tablename__ = "friends"

    u1: Mapped[str] = mapped_column(String(255), primary_key=True)
    u2: Mapped[str] = mapped_column(String(255), primary_key=True)


class Composer(Base):
    __tablename__ = "composers"

    composer: Mapped[str] = mapped_column(String(255), primary_key=True)
    popularity: Mapped[int] = mapped_column(Integer)
