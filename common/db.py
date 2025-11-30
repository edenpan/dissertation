from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Generator

import pymysql  # noqa: F401 - ensure driver is present for SQLAlchemy
from dotenv import load_dotenv
from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

# 加载 .env 文件
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)


@dataclass(frozen=True)
class DatabaseSettings:
    """Connection details sourced from the environment."""

    host: str = os.environ.get("DATA_DB_HOST", "localhost")
    port: int = int(os.environ.get("DATA_DB_PORT", "3306"))
    user: str = os.environ.get("DATA_DB_USER", "root")
    password: str = os.environ.get("DATA_DB_PASSWORD", "")
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
        back_populates="symbol_ref",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    
    index_memberships: Mapped[list["IndexConstituent"]] = relationship(
        back_populates="symbol_ref",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class DailyPrice(Base):
    __tablename__ = "daily_prices"
    __table_args__ = (
        UniqueConstraint("symbol", "traded_at", name="uq_daily_prices_symbol_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
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
    
    # 创建时间
    created_at: Mapped[DateTime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    
    # 更新时间
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    symbol_ref: Mapped[Symbol] = relationship(back_populates="prices")


class Index(Base):
    """指数基本信息表"""
    __tablename__ = "indexes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    exchange: Mapped[str | None] = mapped_column(String(64), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    constituents: Mapped[list["IndexConstituent"]] = relationship(
        back_populates="index_ref",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class IndexConstituent(Base):
    """指数成分股关系表 - 支持历史变更追踪"""
    __tablename__ = "index_constituents"
    __table_args__ = (
        # 确保同一指数、同一股票、同一生效日期只有一条记录
        UniqueConstraint("index_id", "symbol_id", "effective_date", name="uq_index_constituent"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # 指数ID（外键）
    index_id: Mapped[int] = mapped_column(
        ForeignKey("indexes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # 股票ID（外键）
    symbol_id: Mapped[int] = mapped_column(
        ForeignKey("symbols.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # 股票代码（冗余字段，方便查询）
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    
    # 生效日期（该股票加入指数的日期）
    effective_date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
    
    # 失效日期（该股票从指数中移除的日期，NULL表示仍在指数中）
    expiry_date: Mapped[Date | None] = mapped_column(Date, nullable=True, index=True)
    
    # 权重（可选，某些指数有权重信息）
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    # 备注（记录变更原因等信息）
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 数据来源（如：wiki, bloomberg, manual等）
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual", server_default="manual")
    
    # 创建时间
    created_at: Mapped[DateTime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    
    # 更新时间
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    
    # 关系
    index_ref: Mapped[Index] = relationship(back_populates="constituents")
    symbol_ref: Mapped[Symbol] = relationship(back_populates="index_memberships")


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

