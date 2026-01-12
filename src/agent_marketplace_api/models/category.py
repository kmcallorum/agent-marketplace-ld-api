"""Category model."""

from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent_marketplace_api.database import Base

if TYPE_CHECKING:
    from agent_marketplace_api.models.agent import Agent

# Association table for agent-category many-to-many relationship
agent_categories = Table(
    "agent_categories",
    Base.metadata,
    Column(
        "agent_id",
        Integer,
        ForeignKey("agents.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "category_id",
        Integer,
        ForeignKey("categories.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Category(Base):
    """Category model for organizing agents."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    agents: Mapped[list["Agent"]] = relationship(
        "Agent", secondary=agent_categories, back_populates="categories"
    )

    def __repr__(self) -> str:
        return f"<Category(id={self.id}, slug={self.slug!r})>"
