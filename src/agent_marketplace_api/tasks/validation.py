"""Background validation tasks."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from celery import Task
from celery.exceptions import MaxRetriesExceededError

from agent_marketplace_api.tasks.celery import celery_app

if TYPE_CHECKING:
    from agent_marketplace_api.services.validation_service import ValidationResult


class ValidationTask(Task):  # type: ignore[misc]
    """Base task class for validation tasks."""

    autoretry_for = (Exception,)
    retry_kwargs: dict[str, int] = {"max_retries": 3}
    retry_backoff = True
    retry_backoff_max = 600  # 10 minutes max backoff
    retry_jitter = True


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    base=ValidationTask,
    name="agent_marketplace_api.tasks.validation.validate_agent_task",
)
def validate_agent_task(
    self: Task,
    agent_version_id: int,
    storage_key: str,
) -> dict[str, Any]:
    """Validate an agent version asynchronously.

    This task:
    1. Downloads the agent code from storage
    2. Extracts it to a temporary directory
    3. Runs the validation pipeline
    4. Updates the database with results

    Args:
        agent_version_id: ID of the agent version to validate
        storage_key: S3 key where the agent code is stored

    Returns:
        Validation result dict
    """
    try:
        # Run async validation in sync context
        result = asyncio.run(
            _run_validation(agent_version_id, storage_key)
        )
        return result
    except MaxRetriesExceededError:
        # Update status to failed after max retries
        asyncio.run(_update_validation_status(agent_version_id, "failed", "Max retries exceeded"))
        raise
    except Exception as e:
        # Re-raise for retry
        raise self.retry(exc=e, countdown=60) from e


async def _run_validation(agent_version_id: int, storage_key: str) -> dict[str, Any]:
    """Run the actual validation pipeline.

    Args:
        agent_version_id: ID of the agent version
        storage_key: S3 storage key

    Returns:
        Validation result dict
    """
    from agent_marketplace_api.services.validation_service import (
        ValidationConfig,
        ValidationService,
    )
    from agent_marketplace_api.storage import get_storage_service

    storage = get_storage_service()

    # Update status to running
    await _update_validation_status(agent_version_id, "running")

    # Download agent code
    file_data = await storage.download_file(storage_key)

    # Extract to temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        zip_path = temp_path / "agent.zip"

        # Write zip file
        zip_path.write_bytes(file_data)

        # Extract zip
        import zipfile

        extract_path = temp_path / "extracted"
        extract_path.mkdir()

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_path)

        # Run validation
        config = ValidationConfig(
            require_tests=False,  # Don't require tests for now
            skip_tests=True,  # Skip tests for initial validation
        )
        service = ValidationService(config)
        result = await service.validate(extract_path)

        # Update database with results
        await _update_validation_results(agent_version_id, result)

        return result.to_dict()


async def _update_validation_status(
    agent_version_id: int,
    status: str,
    error_message: str | None = None,  # noqa: ARG001
) -> None:
    """Update validation status in database.

    Args:
        agent_version_id: ID of the agent version
        status: New status
        error_message: Optional error message
    """
    from agent_marketplace_api.database import async_session_maker
    from agent_marketplace_api.models import AgentVersion

    async with async_session_maker() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(AgentVersion).where(AgentVersion.id == agent_version_id)
        )
        version = result.scalar_one_or_none()

        if version:
            # Store status in the version's metadata or a separate table
            # For now, we update the security_scan_passed field as a proxy
            if status == "running":
                version.tested = False
                version.security_scan_passed = False
            elif status == "failed":
                version.tested = True
                version.security_scan_passed = False

            await session.commit()


async def _update_validation_results(
    agent_version_id: int,
    result: ValidationResult,
) -> None:
    """Update validation results in database.

    Args:
        agent_version_id: ID of the agent version
        result: Validation result
    """
    from agent_marketplace_api.database import async_session_maker
    from agent_marketplace_api.models import AgentVersion

    async with async_session_maker() as session:
        from sqlalchemy import select

        db_result = await session.execute(
            select(AgentVersion).where(AgentVersion.id == agent_version_id)
        )
        version = db_result.scalar_one_or_none()

        if version:
            version.tested = True
            version.security_scan_passed = (
                result.security_result.passed if result.security_result else True
            )
            if result.quality_result:
                from decimal import Decimal
                version.quality_score = Decimal(str(result.quality_result.lint_score / 100.0))

            # Also update the parent agent's is_validated flag
            if version.agent:
                version.agent.is_validated = result.passed

            await session.commit()


@celery_app.task(name="agent_marketplace_api.tasks.validation.cleanup_old_validations")  # type: ignore[untyped-decorator]
def cleanup_old_validations(days: int = 30) -> dict[str, Any]:  # noqa: ARG001
    """Clean up old validation results.

    Args:
        days: Number of days after which to clean up

    Returns:
        Cleanup result dict
    """
    # This would clean up old temporary files, logs, etc.
    # For now, just return success
    return {"status": "completed", "cleaned_up": 0}
