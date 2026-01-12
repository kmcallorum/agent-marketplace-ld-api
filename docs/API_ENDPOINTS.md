# API Endpoints

Complete REST API specification for agent-marketplace-api.

## Base URL
```
https://api.agent-marketplace.com/api/v1
```

---

## Authentication Endpoints

### POST /auth/github
GitHub OAuth callback.

**Request:**
```json
{
  "code": "github_oauth_code"
}
```

**Response:**
```json
{
  "access_token": "jwt_token",
  "refresh_token": "refresh_token",
  "user": {
    "id": 1,
    "username": "johndoe",
    "email": "john@example.com",
    "avatar_url": "https://..."
  }
}
```

### POST /auth/refresh
Refresh access token.

**Request:**
```json
{
  "refresh_token": "refresh_token"
}
```

**Response:**
```json
{
  "access_token": "new_jwt_token"
}
```

### POST /auth/logout
Logout user (invalidate tokens).

**Response:** `204 No Content`

### GET /auth/me
Get current user info.

**Headers:** `Authorization: Bearer {token}`

**Response:**
```json
{
  "id": 1,
  "username": "johndoe",
  "email": "john@example.com",
  "reputation": 150,
  "created_at": "2025-01-01T00:00:00Z"
}
```

---

## Agent Endpoints

### GET /agents
List/search agents.

**Query Parameters:**
- `category` (optional): Filter by category
- `limit` (default: 20): Results per page
- `offset` (default: 0): Pagination offset
- `sort` (default: relevance): Sort by (downloads, stars, rating, created_at)

**Response:**
```json
{
  "items": [
    {
      "id": 1,
      "name": "Advanced PM",
      "slug": "advanced-pm",
      "description": "Enhanced PM agent",
      "author": {
        "id": 1,
        "username": "johndoe"
      },
      "current_version": "1.2.0",
      "downloads": 1000,
      "stars": 50,
      "rating": 4.5,
      "category": "pm",
      "is_validated": true,
      "created_at": "2025-01-01T00:00:00Z"
    }
  ],
  "total": 100,
  "limit": 20,
  "offset": 0
}
```

### POST /agents
Publish new agent.

**Headers:** `Authorization: Bearer {token}`

**Request (multipart/form-data):**
- `name` (string): Agent name
- `description` (string): Agent description
- `category` (string): Category slug
- `version` (string): Version number
- `code` (file): Agent code (ZIP file)

**Response:** `202 Accepted`
```json
{
  "id": 1,
  "slug": "my-agent",
  "validation_status": "pending",
  "message": "Agent submitted for validation"
}
```

### GET /agents/{slug}
Get agent details.

**Response:**
```json
{
  "id": 1,
  "name": "Advanced PM",
  "slug": "advanced-pm",
  "description": "Full markdown description...",
  "author": {
    "id": 1,
    "username": "johndoe",
    "avatar_url": "https://..."
  },
  "current_version": "1.2.0",
  "downloads": 1000,
  "stars": 50,
  "rating": 4.5,
  "category": "pm",
  "is_validated": true,
  "versions": [
    {
      "version": "1.2.0",
      "published_at": "2025-01-10T00:00:00Z",
      "changelog": "Bug fixes"
    },
    {
      "version": "1.1.0",
      "published_at": "2025-01-05T00:00:00Z",
      "changelog": "New features"
    }
  ],
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-10T00:00:00Z"
}
```

### PUT /agents/{slug}
Update agent metadata.

**Headers:** `Authorization: Bearer {token}`

**Request:**
```json
{
  "description": "Updated description",
  "category": "testing"
}
```

**Response:** `200 OK` (returns updated agent)

### DELETE /agents/{slug}
Unpublish agent.

**Headers:** `Authorization: Bearer {token}`

**Response:** `204 No Content`

### GET /agents/{slug}/versions
Get version history.

**Response:**
```json
{
  "versions": [
    {
      "id": 1,
      "version": "1.2.0",
      "changelog": "Bug fixes",
      "size_bytes": 1024000,
      "tested": true,
      "security_scan_passed": true,
      "published_at": "2025-01-10T00:00:00Z"
    }
  ]
}
```

### POST /agents/{slug}/versions
Publish new version.

**Headers:** `Authorization: Bearer {token}`

**Request (multipart/form-data):**
- `version` (string): Version number
- `changelog` (string): What's new
- `code` (file): Agent code (ZIP)

**Response:** `202 Accepted`

### GET /agents/{slug}/download/{version}
Download agent code.

**Response:** Redirect to presigned S3 URL

### POST /agents/{slug}/star
Star an agent.

**Headers:** `Authorization: Bearer {token}`

**Response:** `204 No Content`

### DELETE /agents/{slug}/star
Unstar an agent.

**Headers:** `Authorization: Bearer {token}`

**Response:** `204 No Content`

### GET /agents/{slug}/stats
Get agent analytics.

**Response:**
```json
{
  "downloads": {
    "total": 1000,
    "last_30_days": 150,
    "daily": [
      {"date": "2025-01-10", "count": 10},
      {"date": "2025-01-09", "count": 8}
    ]
  },
  "stars": {
    "total": 50,
    "last_30_days": 10
  },
  "reviews": {
    "count": 25,
    "average_rating": 4.5
  }
}
```

---

## Review Endpoints

### GET /agents/{slug}/reviews
List reviews for agent.

**Query Parameters:**
- `limit` (default: 20)
- `offset` (default: 0)
- `sort` (default: helpful): Sort by (helpful, recent, rating)

**Response:**
```json
{
  "items": [
    {
      "id": 1,
      "user": {
        "id": 2,
        "username": "janedoe",
        "avatar_url": "https://..."
      },
      "rating": 5,
      "comment": "Excellent agent!",
      "helpful_count": 10,
      "created_at": "2025-01-05T00:00:00Z"
    }
  ],
  "total": 25,
  "average_rating": 4.5
}
```

### POST /agents/{slug}/reviews
Create review.

**Headers:** `Authorization: Bearer {token}`

**Request:**
```json
{
  "rating": 5,
  "comment": "Excellent agent!"
}
```

**Response:** `201 Created`

### PUT /reviews/{id}
Update review.

**Headers:** `Authorization: Bearer {token}`

**Request:**
```json
{
  "rating": 4,
  "comment": "Updated review"
}
```

**Response:** `200 OK`

### DELETE /reviews/{id}
Delete review.

**Headers:** `Authorization: Bearer {token}`

**Response:** `204 No Content`

### POST /reviews/{id}/helpful
Mark review as helpful.

**Headers:** `Authorization: Bearer {token}`

**Response:** `204 No Content`

---

## Category Endpoints

### GET /categories
List all categories.

**Response:**
```json
{
  "categories": [
    {
      "id": 1,
      "name": "Project Management",
      "slug": "pm",
      "icon": "📋",
      "description": "Task tracking, milestones",
      "agent_count": 15
    }
  ]
}
```

### GET /categories/{slug}
Get category details.

**Response:**
```json
{
  "id": 1,
  "name": "Project Management",
  "slug": "pm",
  "description": "...",
  "agent_count": 15
}
```

### GET /categories/{slug}/agents
List agents in category.

**Query Parameters:** Same as `GET /agents`

**Response:** Same format as `GET /agents`

---

## User Endpoints

### GET /users/{username}
Get user profile.

**Response:**
```json
{
  "id": 1,
  "username": "johndoe",
  "avatar_url": "https://...",
  "bio": "Agent developer",
  "reputation": 150,
  "created_at": "2024-01-01T00:00:00Z",
  "stats": {
    "agents_published": 5,
    "total_downloads": 5000,
    "total_stars": 250
  }
}
```

### GET /users/{username}/agents
List user's agents.

**Response:** Same format as `GET /agents`

### GET /users/{username}/reviews
List user's reviews.

**Response:** Same format as `GET /agents/{slug}/reviews`

### GET /users/{username}/starred
List user's starred agents.

**Response:** Same format as `GET /agents`

---

## Search Endpoints

### GET /search
Global search.

**Query Parameters:**
- `q` (required): Search query
- `type` (optional): Filter by type (agents, users)
- `limit` (default: 20)

**Response:**
```json
{
  "agents": [...],
  "users": [...],
  "total": 50
}
```

### GET /search/agents
Agent-specific search.

**Query Parameters:**
- `q` (required): Search query
- `category` (optional): Filter by category
- `min_rating` (optional): Minimum rating
- `sort` (default: relevance)
- `limit` (default: 20)

**Response:** Same format as `GET /agents`

### GET /search/suggestions
Get search suggestions.

**Query Parameters:**
- `q` (required): Partial query

**Response:**
```json
{
  "suggestions": [
    "code review agent",
    "code analysis",
    "code quality"
  ]
}
```

---

## Analytics Endpoints

### GET /stats
Platform statistics.

**Response:**
```json
{
  "agents": {
    "total": 500,
    "validated": 450,
    "pending": 50
  },
  "users": {
    "total": 1000,
    "active_this_month": 300
  },
  "downloads": {
    "total": 100000,
    "last_30_days": 15000
  }
}
```

### GET /trending
Trending agents.

**Query Parameters:**
- `timeframe` (default: week): hour, day, week, month
- `limit` (default: 10)

**Response:**
```json
{
  "agents": [
    {
      "agent": {...},
      "trend_score": 0.95,
      "downloads_change": "+150%"
    }
  ]
}
```

### GET /popular
Popular agents.

**Query Parameters:**
- `limit` (default: 10)

**Response:** Same format as `GET /agents`

---

## Error Responses

### 400 Bad Request
```json
{
  "error": "Validation error",
  "detail": "Rating must be between 1 and 5"
}
```

### 401 Unauthorized
```json
{
  "error": "Authentication required",
  "detail": "Invalid or missing token"
}
```

### 403 Forbidden
```json
{
  "error": "Permission denied",
  "detail": "You don't own this agent"
}
```

### 404 Not Found
```json
{
  "error": "Agent not found",
  "detail": "Agent 'nonexistent' does not exist"
}
```

### 422 Unprocessable Entity
```json
{
  "error": "Validation failed",
  "detail": [
    {
      "loc": ["body", "name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 429 Too Many Requests
```json
{
  "error": "Rate limit exceeded",
  "detail": "Try again in 60 seconds"
}
```

### 500 Internal Server Error
```json
{
  "error": "Internal server error",
  "detail": "Something went wrong"
}
```

---

## Rate Limiting

**Default limits:**
- Authenticated: 1000 requests/hour
- Anonymous: 100 requests/hour

**Headers:**
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 995
X-RateLimit-Reset: 1609459200
```

---

## Pagination

**All list endpoints support:**
- `limit`: Results per page (max 100)
- `offset`: Starting position

**Response includes:**
```json
{
  "items": [...],
  "total": 500,
  "limit": 20,
  "offset": 0,
  "has_more": true
}
```
