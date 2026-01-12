# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-01-12

### Added

- **Core API**
  - FastAPI application with async/await support
  - OpenAPI documentation at /docs and /redoc
  - Health check endpoint at /health
  - Prometheus metrics endpoint at /metrics

- **Authentication**
  - GitHub OAuth integration
  - JWT access and refresh tokens
  - Protected endpoint middleware
  - Token refresh mechanism

- **Agents**
  - Create, read, update, delete agents
  - Version management with changelog
  - File upload to S3/MinIO storage
  - Presigned download URLs
  - Star/unstar functionality

- **Reviews**
  - Create, update, delete reviews
  - Rating system (1-5 stars)
  - Helpful vote tracking
  - Average rating calculations

- **Categories**
  - Category management
  - Agent categorization
  - Category-based filtering

- **Users**
  - User profiles from GitHub
  - Reputation system
  - User statistics

- **Search**
  - Full-text search for agents
  - Search suggestions
  - Category and rating filters
  - Multiple sort options

- **Analytics**
  - Platform statistics
  - Trending agents algorithm
  - Popular agents listing
  - Download tracking

- **Validation Pipeline**
  - Security scanning
  - Code quality checks
  - Compatibility testing
  - Background task processing with Celery

- **Metrics**
  - HTTP request counters and histograms
  - Business metrics (downloads, uploads, reviews)
  - Agent and user gauges
  - Validation duration tracking

- **Infrastructure**
  - PostgreSQL with SQLAlchemy 2.0 async
  - Redis for caching
  - S3/MinIO for file storage
  - Docker and Docker Compose support
  - Alembic migrations

### Security

- JWT token authentication
- Password hashing with bcrypt
- Input validation with Pydantic
- Rate limiting support
- CORS configuration

### Documentation

- Comprehensive README
- API endpoint documentation
- Contributing guidelines
- Security policy

[Unreleased]: https://github.com/kmcallorum/agent-marketplace-api/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/kmcallorum/agent-marketplace-api/releases/tag/v1.0.0
