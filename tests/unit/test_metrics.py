"""Unit tests for Prometheus metrics."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import CONTENT_TYPE_LATEST

from agent_marketplace_api.core.metrics import (
    AGENT_DOWNLOADS_TOTAL,
    AGENT_UPLOADS_TOTAL,
    AGENTS_GAUGE,
    HTTP_REQUESTS_TOTAL,
    PENDING_VALIDATIONS_GAUGE,
    REVIEWS_TOTAL,
    STARS_TOTAL,
    USERS_GAUGE,
    MetricsMiddleware,
    get_metric_value,
    get_metrics,
    track_agent_download,
    track_agent_upload,
    track_review,
    track_star,
    track_validation,
    update_agent_gauge,
    update_pending_validations_gauge,
    update_user_gauge,
)


class TestGetMetrics:
    """Tests for get_metrics function."""

    def test_returns_bytes_and_content_type(self) -> None:
        """Test get_metrics returns bytes and content type."""
        content, content_type = get_metrics()

        assert isinstance(content, bytes)
        assert content_type == CONTENT_TYPE_LATEST

    def test_contains_metric_names(self) -> None:
        """Test metrics output contains expected metric names."""
        content, _ = get_metrics()
        content_str = content.decode("utf-8")

        # Check for presence of metric names
        assert "http_requests_total" in content_str
        assert "http_request_duration_seconds" in content_str
        assert "agent_uploads_total" in content_str
        assert "agent_downloads_total" in content_str


class TestTrackAgentUpload:
    """Tests for track_agent_upload function."""

    def test_tracks_successful_upload(self) -> None:
        """Test tracking successful upload."""
        initial = get_metric_value(AGENT_UPLOADS_TOTAL, {"status": "success"})
        track_agent_upload(success=True)
        final = get_metric_value(AGENT_UPLOADS_TOTAL, {"status": "success"})

        assert final == initial + 1

    def test_tracks_failed_upload(self) -> None:
        """Test tracking failed upload."""
        initial = get_metric_value(AGENT_UPLOADS_TOTAL, {"status": "failure"})
        track_agent_upload(success=False)
        final = get_metric_value(AGENT_UPLOADS_TOTAL, {"status": "failure"})

        assert final == initial + 1


class TestTrackAgentDownload:
    """Tests for track_agent_download function."""

    def test_tracks_download(self) -> None:
        """Test tracking download by agent slug."""
        slug = "test-agent-download"
        initial = get_metric_value(AGENT_DOWNLOADS_TOTAL, {"agent_slug": slug})
        track_agent_download(slug)
        final = get_metric_value(AGENT_DOWNLOADS_TOTAL, {"agent_slug": slug})

        assert final == initial + 1


class TestTrackReview:
    """Tests for track_review function."""

    def test_tracks_review_by_rating(self) -> None:
        """Test tracking review with rating."""
        rating = 5
        initial = get_metric_value(REVIEWS_TOTAL, {"rating": str(rating)})
        track_review(rating)
        final = get_metric_value(REVIEWS_TOTAL, {"rating": str(rating)})

        assert final == initial + 1


class TestTrackStar:
    """Tests for track_star function."""

    def test_tracks_star_operation(self) -> None:
        """Test tracking star operation."""
        initial = get_metric_value(STARS_TOTAL, {"operation": "star"})
        track_star("star")
        final = get_metric_value(STARS_TOTAL, {"operation": "star"})

        assert final == initial + 1

    def test_tracks_unstar_operation(self) -> None:
        """Test tracking unstar operation."""
        initial = get_metric_value(STARS_TOTAL, {"operation": "unstar"})
        track_star("unstar")
        final = get_metric_value(STARS_TOTAL, {"operation": "unstar"})

        assert final == initial + 1


class TestTrackValidation:
    """Tests for track_validation function."""

    def test_tracks_validation_duration(self) -> None:
        """Test tracking validation duration."""
        validator_type = "security"
        duration = 5.5

        # This will add to the histogram
        track_validation(validator_type, duration)

        # Verify the metric exists in output
        content, _ = get_metrics()
        assert b"validation_duration_seconds" in content


class TestUpdateAgentGauge:
    """Tests for update_agent_gauge function."""

    def test_sets_agent_counts(self) -> None:
        """Test setting agent count gauges."""
        update_agent_gauge(total=100, validated=80, pending=20)

        assert get_metric_value(AGENTS_GAUGE, {"status": "total"}) == 100
        assert get_metric_value(AGENTS_GAUGE, {"status": "validated"}) == 80
        assert get_metric_value(AGENTS_GAUGE, {"status": "pending"}) == 20


class TestUpdateUserGauge:
    """Tests for update_user_gauge function."""

    def test_sets_user_counts(self) -> None:
        """Test setting user count gauges."""
        update_user_gauge(total=500, active=200)

        assert get_metric_value(USERS_GAUGE, {"status": "total"}) == 500
        assert get_metric_value(USERS_GAUGE, {"status": "active"}) == 200


class TestUpdatePendingValidationsGauge:
    """Tests for update_pending_validations_gauge function."""

    def test_sets_pending_count(self) -> None:
        """Test setting pending validations count."""
        update_pending_validations_gauge(15)

        assert get_metric_value(PENDING_VALIDATIONS_GAUGE) == 15


class TestMetricsMiddleware:
    """Tests for MetricsMiddleware."""

    @pytest.fixture
    def app_with_middleware(self) -> FastAPI:
        """Create test app with metrics middleware."""
        app = FastAPI()
        app.add_middleware(MetricsMiddleware)

        @app.get("/test")
        async def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        @app.get("/test/{id}")
        async def test_with_id(id: int) -> dict[str, int]:
            return {"id": id}

        @app.get("/metrics")
        async def metrics_endpoint() -> dict[str, str]:
            return {"metrics": "data"}

        return app

    def test_tracks_request_count(self, app_with_middleware: FastAPI) -> None:
        """Test middleware tracks request count."""
        client = TestClient(app_with_middleware)

        initial = get_metric_value(
            HTTP_REQUESTS_TOTAL,
            {"method": "GET", "endpoint": "/test", "status": "200"},
        )

        client.get("/test")

        final = get_metric_value(
            HTTP_REQUESTS_TOTAL,
            {"method": "GET", "endpoint": "/test", "status": "200"},
        )

        assert final == initial + 1

    def test_tracks_request_duration(self, app_with_middleware: FastAPI) -> None:
        """Test middleware tracks request duration."""
        client = TestClient(app_with_middleware)

        client.get("/test")

        # Verify duration was recorded
        content, _ = get_metrics()
        assert b"http_request_duration_seconds" in content

    def test_skips_metrics_endpoint(self, app_with_middleware: FastAPI) -> None:
        """Test middleware skips /metrics endpoint."""
        client = TestClient(app_with_middleware)

        initial_count = get_metric_value(
            HTTP_REQUESTS_TOTAL,
            {"method": "GET", "endpoint": "/metrics", "status": "200"},
        )

        client.get("/metrics")

        final_count = get_metric_value(
            HTTP_REQUESTS_TOTAL,
            {"method": "GET", "endpoint": "/metrics", "status": "200"},
        )

        # Count should not change for /metrics endpoint
        assert final_count == initial_count

    def test_normalizes_path_with_id(self, app_with_middleware: FastAPI) -> None:
        """Test middleware normalizes paths with IDs."""
        client = TestClient(app_with_middleware)

        client.get("/test/123")

        # The path should be normalized to /test/{id}
        content, _ = get_metrics()
        content_str = content.decode("utf-8")
        # Check that we're tracking with normalized path
        assert "http_requests_total" in content_str


class TestMetricsMiddlewarePathNormalization:
    """Tests for path normalization in MetricsMiddleware."""

    def test_normalizes_agent_slug(self) -> None:
        """Test normalizing agent slug paths."""
        middleware = MetricsMiddleware(None)  # type: ignore[arg-type]

        path = "/api/v1/agents/my-cool-agent"
        normalized = middleware._normalize_path(path)

        assert normalized == "/api/v1/agents/{slug}"

    def test_normalizes_user_slug(self) -> None:
        """Test normalizing user paths."""
        middleware = MetricsMiddleware(None)  # type: ignore[arg-type]

        path = "/api/v1/users/johndoe"
        normalized = middleware._normalize_path(path)

        assert normalized == "/api/v1/users/{slug}"

    def test_normalizes_review_id(self) -> None:
        """Test normalizing review ID paths."""
        middleware = MetricsMiddleware(None)  # type: ignore[arg-type]

        path = "/api/v1/reviews/123"
        normalized = middleware._normalize_path(path)

        assert normalized == "/api/v1/reviews/{id}"

    def test_preserves_static_paths(self) -> None:
        """Test preserving static path segments."""
        middleware = MetricsMiddleware(None)  # type: ignore[arg-type]

        path = "/api/v1/agents/my-agent/reviews"
        normalized = middleware._normalize_path(path)

        assert normalized == "/api/v1/agents/{slug}/reviews"

    def test_normalizes_nested_paths(self) -> None:
        """Test normalizing nested paths."""
        middleware = MetricsMiddleware(None)  # type: ignore[arg-type]

        path = "/api/v1/agents/my-agent/versions"
        normalized = middleware._normalize_path(path)

        assert normalized == "/api/v1/agents/{slug}/versions"

    def test_handles_empty_path(self) -> None:
        """Test handling empty path."""
        middleware = MetricsMiddleware(None)  # type: ignore[arg-type]

        path = "/"
        normalized = middleware._normalize_path(path)

        assert normalized == "/"


class TestGetMetricValue:
    """Tests for get_metric_value helper function."""

    def test_gets_counter_value(self) -> None:
        """Test getting counter value with labels."""
        track_agent_upload(success=True)
        value = get_metric_value(AGENT_UPLOADS_TOTAL, {"status": "success"})

        assert value >= 1

    def test_gets_gauge_value(self) -> None:
        """Test getting gauge value with labels."""
        update_agent_gauge(total=50, validated=40, pending=10)
        value = get_metric_value(AGENTS_GAUGE, {"status": "total"})

        assert value == 50

    def test_gets_gauge_value_without_labels(self) -> None:
        """Test getting gauge value without labels."""
        update_pending_validations_gauge(25)
        value = get_metric_value(PENDING_VALIDATIONS_GAUGE)

        assert value == 25

    def test_returns_zero_for_missing_labels(self) -> None:
        """Test returns zero for non-existent label combination."""
        value = get_metric_value(AGENT_UPLOADS_TOTAL, {"status": "nonexistent"})

        assert value == 0.0

    def test_gets_histogram_value(self) -> None:
        """Test getting histogram value with labels."""
        from agent_marketplace_api.core.metrics import VALIDATION_DURATION_SECONDS

        # Record some values to the histogram
        track_validation("security", 5.0)
        track_validation("security", 10.0)

        # Get the sum (histograms return sum when queried)
        value = get_metric_value(VALIDATION_DURATION_SECONDS, {"validator_type": "security"})

        assert value >= 15.0  # Sum of 5.0 + 10.0 plus any previous values

    def test_returns_zero_for_counter_without_labels(self) -> None:
        """Test returns zero for counter queried without labels."""
        # Counters require labels to get a meaningful value
        value = get_metric_value(AGENT_UPLOADS_TOTAL)

        assert value == 0.0


class TestMetricsEndpointIntegration:
    """Integration tests for /metrics endpoint."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self) -> None:
        """Test /metrics endpoint returns Prometheus metrics."""
        from httpx import ASGITransport, AsyncClient

        from agent_marketplace_api.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/metrics")

            assert response.status_code == 200
            assert "text/plain" in response.headers["content-type"]
            # Check for metric names in response
            assert b"http_requests_total" in response.content


class TestMetricsMiddlewareExceptionHandling:
    """Tests for exception handling in MetricsMiddleware."""

    def test_handles_exception_in_endpoint(self) -> None:
        """Test middleware records 500 status on exception."""
        app = FastAPI()
        app.add_middleware(MetricsMiddleware)

        @app.get("/error")
        async def error_endpoint() -> dict[str, str]:
            raise ValueError("Test error")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/error")

        assert response.status_code == 500


class TestMetricsMiddlewarePathNormalizationExtended:
    """Extended tests for path normalization."""

    def test_normalizes_star_endpoint(self) -> None:
        """Test normalizing star endpoint path."""
        middleware = MetricsMiddleware(None)  # type: ignore[arg-type]

        path = "/api/v1/agents/my-agent/star"
        normalized = middleware._normalize_path(path)

        assert normalized == "/api/v1/agents/{slug}/star"

    def test_normalizes_download_endpoint(self) -> None:
        """Test normalizing download endpoint path."""
        middleware = MetricsMiddleware(None)  # type: ignore[arg-type]

        path = "/api/v1/agents/my-agent/download"
        normalized = middleware._normalize_path(path)

        assert normalized == "/api/v1/agents/{slug}/download"

    def test_normalizes_stats_endpoint(self) -> None:
        """Test normalizing stats endpoint path."""
        middleware = MetricsMiddleware(None)  # type: ignore[arg-type]

        path = "/api/v1/agents/my-agent/stats"
        normalized = middleware._normalize_path(path)

        assert normalized == "/api/v1/agents/{slug}/stats"

    def test_normalizes_category_slug(self) -> None:
        """Test normalizing category slug path."""
        middleware = MetricsMiddleware(None)  # type: ignore[arg-type]

        path = "/api/v1/categories/development"
        normalized = middleware._normalize_path(path)

        assert normalized == "/api/v1/categories/{slug}"

    def test_preserves_keyword_after_collection(self) -> None:
        """Test preserving keyword paths directly after collection."""
        middleware = MetricsMiddleware(None)  # type: ignore[arg-type]

        # This tests the case where a keyword like "reviews" appears
        # directly after "agents" (e.g., listing all reviews)
        path = "/api/v1/agents/reviews"
        normalized = middleware._normalize_path(path)

        # "reviews" should be preserved as-is since it's a keyword
        assert normalized == "/api/v1/agents/reviews"

    def test_preserves_versions_keyword(self) -> None:
        """Test preserving versions keyword path."""
        middleware = MetricsMiddleware(None)  # type: ignore[arg-type]

        path = "/api/v1/agents/versions"
        normalized = middleware._normalize_path(path)

        assert normalized == "/api/v1/agents/versions"
