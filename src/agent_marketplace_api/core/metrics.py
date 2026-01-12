"""Prometheus metrics for monitoring and observability."""

import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# Create a custom registry for testing isolation
REGISTRY = CollectorRegistry()

# HTTP Request Metrics
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
    registry=REGISTRY,
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=REGISTRY,
)

# Business Metrics - Counters
AGENT_UPLOADS_TOTAL = Counter(
    "agent_uploads_total",
    "Total agent uploads",
    ["status"],  # success, failure
    registry=REGISTRY,
)

AGENT_DOWNLOADS_TOTAL = Counter(
    "agent_downloads_total",
    "Total agent downloads",
    ["agent_slug"],
    registry=REGISTRY,
)

REVIEWS_TOTAL = Counter(
    "reviews_total",
    "Total reviews created",
    ["rating"],  # 1-5
    registry=REGISTRY,
)

STARS_TOTAL = Counter(
    "stars_total",
    "Total star operations",
    ["operation"],  # star, unstar
    registry=REGISTRY,
)

# Business Metrics - Gauges
AGENTS_GAUGE = Gauge(
    "agents_count",
    "Current number of agents",
    ["status"],  # validated, pending, total
    registry=REGISTRY,
)

USERS_GAUGE = Gauge(
    "users_count",
    "Current number of users",
    ["status"],  # active, total
    registry=REGISTRY,
)

PENDING_VALIDATIONS_GAUGE = Gauge(
    "pending_validations_count",
    "Number of agents pending validation",
    registry=REGISTRY,
)

# Validation Metrics
VALIDATION_DURATION_SECONDS = Histogram(
    "validation_duration_seconds",
    "Validation pipeline duration in seconds",
    ["validator_type"],  # security, quality, compatibility, tests
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
    registry=REGISTRY,
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to track HTTP request metrics."""

    def __init__(self, app: ASGIApp) -> None:
        """Initialize metrics middleware."""
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Track request metrics."""
        # Skip metrics endpoint to avoid recursion
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        # Normalize path to avoid high cardinality
        endpoint = self._normalize_path(request.url.path)

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            status = str(response.status_code)
        except Exception:
            status = "500"
            raise
        finally:
            duration = time.perf_counter() - start_time

            # Record metrics
            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                endpoint=endpoint,
                status=status,
            ).inc()

            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=method,
                endpoint=endpoint,
            ).observe(duration)

        return response

    def _normalize_path(self, path: str) -> str:
        """
        Normalize path to reduce cardinality.

        Replaces dynamic segments (IDs, slugs) with placeholders.
        """
        parts = path.split("/")
        normalized_parts = []

        for i, part in enumerate(parts):
            if not part:
                continue

            # Check if previous part suggests this is a dynamic segment
            if i > 0 and parts[i - 1] in ("agents", "users", "reviews", "categories"):
                # This might be a slug or ID
                if part.isdigit():
                    normalized_parts.append("{id}")
                elif part not in ("star", "reviews", "versions", "download", "stats"):
                    normalized_parts.append("{slug}")
                else:
                    normalized_parts.append(part)
            elif part.isdigit():
                normalized_parts.append("{id}")
            else:
                normalized_parts.append(part)

        return "/" + "/".join(normalized_parts) if normalized_parts else "/"


def get_metrics() -> tuple[bytes, str]:
    """
    Generate Prometheus metrics output.

    Returns:
        Tuple of (metrics bytes, content type)
    """
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST


def track_agent_upload(success: bool) -> None:
    """Track an agent upload."""
    status = "success" if success else "failure"
    AGENT_UPLOADS_TOTAL.labels(status=status).inc()


def track_agent_download(agent_slug: str) -> None:
    """Track an agent download."""
    AGENT_DOWNLOADS_TOTAL.labels(agent_slug=agent_slug).inc()


def track_review(rating: int) -> None:
    """Track a review creation."""
    REVIEWS_TOTAL.labels(rating=str(rating)).inc()


def track_star(operation: str) -> None:
    """Track a star operation (star or unstar)."""
    STARS_TOTAL.labels(operation=operation).inc()


def track_validation(validator_type: str, duration: float) -> None:
    """Track validation duration."""
    VALIDATION_DURATION_SECONDS.labels(validator_type=validator_type).observe(duration)


def update_agent_gauge(total: int, validated: int, pending: int) -> None:
    """Update agent count gauges."""
    AGENTS_GAUGE.labels(status="total").set(total)
    AGENTS_GAUGE.labels(status="validated").set(validated)
    AGENTS_GAUGE.labels(status="pending").set(pending)


def update_user_gauge(total: int, active: int) -> None:
    """Update user count gauges."""
    USERS_GAUGE.labels(status="total").set(total)
    USERS_GAUGE.labels(status="active").set(active)


def update_pending_validations_gauge(count: int) -> None:
    """Update pending validations gauge."""
    PENDING_VALIDATIONS_GAUGE.set(count)


def get_metric_value(
    metric: Counter | Gauge | Histogram,
    labels: dict[str, str] | None = None,
) -> float:
    """
    Get the current value of a metric.

    Args:
        metric: The metric to query
        labels: Optional label values

    Returns:
        Current metric value
    """
    if labels:
        # For labeled metrics
        try:
            if isinstance(metric, (Counter, Gauge)):
                return float(metric.labels(**labels)._value.get())
            elif isinstance(metric, Histogram):
                return float(metric.labels(**labels)._sum.get())
        except KeyError:
            return 0.0
    else:
        # For non-labeled metrics
        if isinstance(metric, Gauge):
            return float(metric._value.get())
    return 0.0
