# Database Schema

Complete PostgreSQL schema for agent-marketplace-api.

## Core Tables

### users
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    github_id INTEGER UNIQUE NOT NULL,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    avatar_url TEXT,
    bio TEXT,
    reputation INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_github_id ON users(github_id);
```

### agents
```sql
CREATE TABLE agents (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    description TEXT NOT NULL,
    author_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    current_version VARCHAR(50) NOT NULL,
    downloads INTEGER DEFAULT 0,
    stars INTEGER DEFAULT 0,
    rating DECIMAL(3,2) DEFAULT 0.0,
    is_public BOOLEAN DEFAULT TRUE,
    is_validated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_agents_slug ON agents(slug);
CREATE INDEX idx_agents_author_id ON agents(author_id);
CREATE INDEX idx_agents_created_at ON agents(created_at);
```

### agent_versions
```sql
CREATE TABLE agent_versions (
    id SERIAL PRIMARY KEY,
    agent_id INTEGER REFERENCES agents(id) ON DELETE CASCADE,
    version VARCHAR(50) NOT NULL,
    storage_key TEXT NOT NULL,
    size_bytes BIGINT,
    changelog TEXT,
    tested BOOLEAN DEFAULT FALSE,
    security_scan_passed BOOLEAN DEFAULT FALSE,
    quality_score DECIMAL(3,2),
    published_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(agent_id, version)
);

CREATE INDEX idx_agent_versions_agent_id ON agent_versions(agent_id);
```

### categories
```sql
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    icon VARCHAR(50),
    description TEXT,
    agent_count INTEGER DEFAULT 0
);

CREATE INDEX idx_categories_slug ON categories(slug);
```

### agent_categories (many-to-many)
```sql
CREATE TABLE agent_categories (
    agent_id INTEGER REFERENCES agents(id) ON DELETE CASCADE,
    category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
    PRIMARY KEY (agent_id, category_id)
);
```

### reviews
```sql
CREATE TABLE reviews (
    id SERIAL PRIMARY KEY,
    agent_id INTEGER REFERENCES agents(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    helpful_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(agent_id, user_id)
);

CREATE INDEX idx_reviews_agent_id ON reviews(agent_id);
CREATE INDEX idx_reviews_user_id ON reviews(user_id);
```

### agent_stars
```sql
CREATE TABLE agent_stars (
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    agent_id INTEGER REFERENCES agents(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, agent_id)
);
```

### analytics_events
```sql
CREATE TABLE analytics_events (
    id SERIAL PRIMARY KEY,
    agent_id INTEGER REFERENCES agents(id) ON DELETE SET NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    event_type VARCHAR(50) NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_analytics_events_agent_id ON analytics_events(agent_id);
CREATE INDEX idx_analytics_events_event_type ON analytics_events(event_type);
CREATE INDEX idx_analytics_events_created_at ON analytics_events(created_at);
```

### validation_results
```sql
CREATE TABLE validation_results (
    id SERIAL PRIMARY KEY,
    agent_version_id INTEGER REFERENCES agent_versions(id) ON DELETE CASCADE,
    validator_type VARCHAR(50) NOT NULL,
    passed BOOLEAN NOT NULL,
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_validation_results_agent_version_id ON validation_results(agent_version_id);
```

## SQLAlchemy Models

### User Model
```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    github_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    avatar_url = Column(Text)
    bio = Column(Text)
    reputation = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    agents = relationship("Agent", back_populates="author")
    reviews = relationship("Review", back_populates="user")
    starred_agents = relationship("Agent", secondary="agent_stars")
```

### Agent Model
```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Numeric, ForeignKey
from sqlalchemy.orm import relationship

class Agent(Base):
    __tablename__ = "agents"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    description = Column(Text, nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    current_version = Column(String(50), nullable=False)
    downloads = Column(Integer, default=0)
    stars = Column(Integer, default=0)
    rating = Column(Numeric(3, 2), default=0.0)
    is_public = Column(Boolean, default=True)
    is_validated = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    author = relationship("User", back_populates="agents")
    versions = relationship("AgentVersion", back_populates="agent")
    reviews = relationship("Review", back_populates="agent")
    categories = relationship("Category", secondary="agent_categories")
```

### Review Model
```python
class Review(Base):
    __tablename__ = "reviews"
    
    id = Column(Integer, primary_key=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(Text)
    helpful_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    agent = relationship("Agent", back_populates="reviews")
    user = relationship("User", back_populates="reviews")
```

## Alembic Migration Commands

```bash
# Create migration
alembic revision --autogenerate -m "Create initial tables"

# Apply migrations
alembic upgrade head

# Rollback one version
alembic downgrade -1

# Show current version
alembic current

# Show migration history
alembic history
```
