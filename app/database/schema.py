from enum import StrEnum
from typing import Optional, List
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy import (
    Integer,
    Identity,
    LargeBinary,
    Boolean,
    text,
    Index,
    Column,
    BigInteger,
    String,
    Enum as SqlEnum,
    ForeignKey,
)
from sqlalchemy import TIMESTAMP
from datetime import datetime


class Role(StrEnum):
    USER = "USER"
    ADMIN = "ADMIN"
    AGENT = "AGENT"


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    deleted_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )


class EncryptionKey(Base, TimestampMixin):
    __tablename__ = "encryption_keys"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    symmetric_key: Mapped[bytes] = mapped_column(LargeBinary)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    expired_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    api_keys: Mapped[List["ApiKey"]] = relationship(
        back_populates="encryption_key",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_active_encryption_keys", "id", postgresql_where=Column("is_active")),
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    role: Mapped[Role] = mapped_column(
        SqlEnum(Role, name="user_roles"),
        nullable=False,
    )

    api_keys: Mapped[List["ApiKey"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class ApiKey(Base, TimestampMixin):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key_id: Mapped[int] = mapped_column(
        ForeignKey("encryption_keys.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key_credential: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
        unique=True,
    )
    key_signature: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    user: Mapped["User"] = relationship(back_populates="api_keys")
    encryption_key: Mapped["EncryptionKey"] = relationship(back_populates="api_keys")
