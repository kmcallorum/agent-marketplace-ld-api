#!/usr/bin/env python3
"""Seed the database with sample agents for development/demo purposes."""

import asyncio
import os
import sys
from datetime import UTC, datetime
from decimal import Decimal

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from agent_marketplace_api.models.agent import Agent, AgentVersion
from agent_marketplace_api.models.user import User

SAMPLE_AGENTS = [
    {
        "name": "Code Review Agent",
        "slug": "code-review-agent",
        "description": "Analyzes code for bugs, security vulnerabilities, and style issues. Provides detailed feedback with suggestions for improvement.",
        "category": "code-review",
        "version": "1.0.0",
        "downloads": 1250,
        "stars": 89,
        "rating": Decimal("4.5"),
    },
    {
        "name": "Documentation Generator",
        "slug": "documentation-generator",
        "description": "Automatically generates comprehensive documentation from code, including API references, README files, and inline comments.",
        "category": "documentation",
        "version": "2.1.0",
        "downloads": 3420,
        "stars": 156,
        "rating": Decimal("4.7"),
    },
    {
        "name": "Test Suite Creator",
        "slug": "test-suite-creator",
        "description": "Generates unit tests, integration tests, and end-to-end tests for your codebase. Supports Python, JavaScript, and Go.",
        "category": "testing",
        "version": "1.3.0",
        "downloads": 890,
        "stars": 67,
        "rating": Decimal("4.2"),
    },
    {
        "name": "DevOps Pipeline Agent",
        "slug": "devops-pipeline-agent",
        "description": "Creates and manages CI/CD pipelines for GitHub Actions, GitLab CI, and Jenkins. Automates deployments and infrastructure.",
        "category": "devops",
        "version": "3.0.0",
        "downloads": 2100,
        "stars": 203,
        "rating": Decimal("4.8"),
    },
    {
        "name": "Security Scanner",
        "slug": "security-scanner",
        "description": "Scans code for OWASP vulnerabilities, secrets exposure, and dependency issues. Integrates with GitHub Security Advisories.",
        "category": "security",
        "version": "1.5.2",
        "downloads": 4500,
        "stars": 312,
        "rating": Decimal("4.9"),
    },
    {
        "name": "Research Assistant",
        "slug": "research-assistant",
        "description": "Helps with technical research by searching documentation, Stack Overflow, and academic papers. Summarizes findings.",
        "category": "research",
        "version": "2.0.0",
        "downloads": 1800,
        "stars": 145,
        "rating": Decimal("4.4"),
    },
    {
        "name": "Project Manager Agent",
        "slug": "project-manager-agent",
        "description": "Manages project tasks, creates issues, assigns work, and tracks progress. Integrates with Jira, Linear, and GitHub Projects.",
        "category": "pm",
        "version": "1.2.0",
        "downloads": 950,
        "stars": 78,
        "rating": Decimal("4.1"),
    },
    {
        "name": "Data Pipeline Builder",
        "slug": "data-pipeline-builder",
        "description": "Creates ETL pipelines for data processing. Supports SQL, Pandas, and Spark transformations with automatic optimization.",
        "category": "data",
        "version": "1.0.0",
        "downloads": 620,
        "stars": 45,
        "rating": Decimal("4.3"),
    },
]


async def seed_agents():
    """Seed the database with sample agents."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        print("Example: DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/dbname")
        sys.exit(1)

    # Ensure we're using asyncpg
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Get or create a demo user
        result = await session.execute(select(User).where(User.username == "demo"))
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                username="demo",
                email="demo@agent-marketplace.local",
                github_id=0,
                avatar_url="https://avatars.githubusercontent.com/u/0",
            )
            session.add(user)
            await session.flush()
            print(f"Created demo user: {user.username}")

        # Check existing agents
        result = await session.execute(select(Agent.slug))
        existing_slugs = {row[0] for row in result.fetchall()}

        created_count = 0
        for agent_data in SAMPLE_AGENTS:
            if agent_data["slug"] in existing_slugs:
                print(f"Skipping {agent_data['name']} (already exists)")
                continue

            now = datetime.now(UTC)
            agent = Agent(
                name=agent_data["name"],
                slug=agent_data["slug"],
                description=agent_data["description"],
                category=agent_data["category"],
                current_version=agent_data["version"],
                author_id=user.id,
                downloads=agent_data["downloads"],
                stars=agent_data["stars"],
                rating=agent_data["rating"],
                is_public=True,
                is_validated=True,
                created_at=now,
                updated_at=now,
            )
            session.add(agent)
            await session.flush()

            # Add version
            version = AgentVersion(
                agent_id=agent.id,
                version=agent_data["version"],
                changelog="Initial release",
                storage_key=f"agents/demo/{agent_data['slug']}-{agent_data['version']}.zip",
                size_bytes=1024 * 100,  # 100KB placeholder
                tested=True,
                security_scan_passed=True,
                quality_score=Decimal("85.0"),
                published_at=now,
            )
            session.add(version)
            created_count += 1
            print(f"Created: {agent_data['name']}")

        await session.commit()
        print(f"\nSeeded {created_count} agents successfully!")


if __name__ == "__main__":
    asyncio.run(seed_agents())
