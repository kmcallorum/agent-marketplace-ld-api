"""Agent and AgentVersion models."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent_marketplace_api.database import Base

if TYPE_CHECKING:
    from agent_marketplace_api.models.category import Category
    from agent_marketplace_api.models.review import Review
    from agent_marketplace_api.models.user import User


class Agent(Base):
    """Agent model representing published AI agents."""

    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    current_version: Mapped[str] = mapped_column(String(50), nullable=False)
    downloads: Mapped[int] = mapped_column(Integer, default=0)
    stars: Mapped[int] = mapped_column(Integer, default=0)
    rating: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("0.00"))
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    is_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    author: Mapped["User"] = relationship("User", back_populates="agents")
    versions: Mapped[list["AgentVersion"]] = relationship(
        "AgentVersion", back_populates="agent", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["Review"]] = relationship(
        "Review", back_populates="agent", cascade="all, delete-orphan"
    )
    categories: Mapped[list["Category"]] = relationship(
        "Category", secondary="agent_categories", back_populates="agents"
    )
    starred_by: Mapped[list["User"]] = relationship(
        "User", secondary="agent_stars", back_populates="starred_agents"
    )

    def __repr__(self) -> str:
        return f"<Agent(id={self.id}, slug={self.slug!r})>"


class AgentVersion(Base):
    """AgentVersion model for tracking agent version history."""

    __tablename__ = "agent_versions"
    __table_args__ = (UniqueConstraint("agent_id", "version", name="uq_agent_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    changelog: Mapped[str | None] = mapped_column(Text, nullable=True)
    tested: Mapped[bool] = mapped_column(Boolean, default=False)
    security_scan_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    quality_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    agent: Mapped["Agent"] = relationship("Agent", back_populates="versions")

    def __repr__(self) -> str:
        return f"<AgentVersion(id={self.id}, version={self.version!r})>"
