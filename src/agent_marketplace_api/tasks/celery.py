"""Celery application configuration."""

from celery import Celery

from agent_marketplace_api.config import get_settings


def create_celery_app() -> Celery:
    """Create and configure Celery application.

    Returns:
        Configured Celery application
    """
    settings = get_settings()

    app = Celery(
        "agent_marketplace",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
    )

    # Configure Celery
    app.conf.update(
        # Task settings
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        # Task execution settings
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        # Result settings
        result_expires=3600,  # 1 hour
        # Worker settings
        worker_prefetch_multiplier=1,
        worker_concurrency=4,
        # Task routing
        task_routes={
            "agent_marketplace_api.tasks.validation.*": {"queue": "validation"},
        },
        # Task time limits
        task_soft_time_limit=600,  # 10 minutes
        task_time_limit=900,  # 15 minutes hard limit
    )

    # Auto-discover tasks
    app.autodiscover_tasks(["agent_marketplace_api.tasks"])

    return app


# Create the Celery app instance
celery_app = create_celery_app()


# Health check task
@celery_app.task(name="agent_marketplace_api.tasks.celery.health_check")  # type: ignore[untyped-decorator]
def health_check() -> dict[str, str]:
    """Health check task to verify Celery is working.

    Returns:
        Status dict
    """
    return {"status": "healthy", "worker": "celery"}
