"""User model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent_marketplace_api.database import Base

if TYPE_CHECKING:
    from agent_marketplace_api.models.agent import Agent
    from agent_marketplace_api.models.review import Review

# Association table for user starred agents
agent_stars = Table(
    "agent_stars",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("agent_id", Integer, ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True),
    Column("created_at", DateTime, default=datetime.utcnow),
)


class User(Base):
    """User model representing marketplace users."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    github_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    reputation: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    agents: Mapped[list["Agent"]] = relationship("Agent", back_populates="author")
    reviews: Mapped[list["Review"]] = relationship("Review", back_populates="user")
    starred_agents: Mapped[list["Agent"]] = relationship(
        "Agent", secondary=agent_stars, back_populates="starred_by"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username!r})>"
