"""Tests for database module."""

import contextlib
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agent_marketplace_api.database import Base, check_database_connection, get_db


class TestBase:
    """Tests for SQLAlchemy Base class."""

    def test_base_is_declarative(self) -> None:
        """Test Base is a proper declarative base."""
        assert hasattr(Base, "metadata")
        assert hasattr(Base, "registry")


class TestGetDb:
    """Tests for get_db dependency."""

    @pytest.mark.asyncio
    async def test_get_db_yields_session(self) -> None:
        """Test get_db yields a database session."""
        mock_session = AsyncMock(spec=AsyncSession)

        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch("agent_marketplace_api.database.async_session_maker", mock_session_maker):
            gen = get_db()
            assert isinstance(gen, AsyncGenerator)

            session = await gen.__anext__()
            assert session is mock_session

            # Complete the generator
            with contextlib.suppress(StopAsyncIteration):
                await gen.__anext__()

            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_db_rollback_on_exception(self) -> None:
        """Test get_db rolls back on exception."""
        mock_session = AsyncMock(spec=AsyncSession)

        mock_session_maker = MagicMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch("agent_marketplace_api.database.async_session_maker", mock_session_maker):
            gen = get_db()
            await gen.__anext__()

            # Simulate an exception by throwing into the generator
            with pytest.raises(ValueError):
                await gen.athrow(ValueError("Test error"))

            mock_session.rollback.assert_called_once()


class TestCheckDatabaseConnection:
    """Tests for database connection check."""

    @pytest.mark.asyncio
    async def test_check_connection_success(self) -> None:
        """Test successful database connection check."""
        mock_conn = AsyncMock()

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_context

        with patch("agent_marketplace_api.database.async_engine", mock_engine):
            result = await check_database_connection()

        assert result is True
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_connection_failure(self) -> None:
        """Test failed database connection check."""
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = Exception("Connection failed")

        with patch("agent_marketplace_api.database.async_engine", mock_engine):
            result = await check_database_connection()

        assert result is False
