from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from typing import Generator

import pymysql  # noqa: F401 - ensure driver is present for SQLAlchemy
from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker


@dataclass(frozen=True)
class DatabaseSettings:
    """Connection details sourced from the environment."""

    host: str = os.environ.get("DATA_DB_HOST", "127.0.0.1")
    port: int = int(os.environ.get("DATA_DB_PORT", "3306"))
    user: str = os.environ.get("DATA_DB_USER", "runner")
    password: str = os.environ.get("DATA_DB_PASSWORD", "tester")
    name: str = os.environ.get("DATA_DB_NAME", "stockdb")
    charset: str = os.environ.get("DATA_DB_CHARSET", "utf8mb4")

    @property
    def url(self) -> str:
        return (
            f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/"
            f"{self.name}?charset={self.charset}"
        )


DATABASE_SETTINGS = DatabaseSettings()


class Base(DeclarativeBase):
    pass


class Symbol(Base):
    __tablename__ = "symbols"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(64), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(16), nullable=True)

    prices: Mapped[list["DailyPrice"]] = relationship(
        back_populates="symbol",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class DailyPrice(Base):
    __tablename__ = "daily_prices"
    __table_args__ = (
        UniqueConstraint("symbol_id", "traded_at", name="uq_daily_prices_symbol_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol_id: Mapped[int] = mapped_column(
        ForeignKey("symbols.id", ondelete="CASCADE"),
        nullable=False,
    )
    traded_at: Mapped[Date] = mapped_column(Date, nullable=False)
    open: Mapped[float | None] = mapped_column(Float, nullable=True)
    high: Mapped[float | None] = mapped_column(Float, nullable=True)
    low: Mapped[float | None] = mapped_column(Float, nullable=True)
    close: Mapped[float | None] = mapped_column(Float, nullable=True)
    adj_close: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    symbol: Mapped[Symbol] = relationship(back_populates="prices")


@lru_cache()
def get_engine() -> Engine:
    """Construct (and cache) the SQLAlchemy engine."""
    return create_engine(
        DATABASE_SETTINGS.url,
        pool_pre_ping=True,
        pool_recycle=3600,
        future=True,
    )


SessionFactory = sessionmaker(bind=get_engine(), autocommit=False, autoflush=False, future=True)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Yield a session with automatic commit/rollback semantics."""
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Ensure all tables exist."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
