"""Unit tests for security module."""

from datetime import timedelta

import pytest

from agent_marketplace_api.security import (
    InvalidTokenError,
    TokenExpiredError,
    create_access_token,
    create_refresh_token,
    decode_token_without_verification,
    hash_password,
    verify_password,
    verify_token,
)


class TestPasswordHashing:
    """Tests for password hashing functions."""

    def test_hash_password_returns_hash(self) -> None:
        """Test that hash_password returns a bcrypt hash."""
        password = "secret123"
        hashed = hash_password(password)

        assert hashed != password
        assert hashed.startswith("$2b$")  # bcrypt prefix

    def test_verify_password_correct(self) -> None:
        """Test that verify_password returns True for correct password."""
        password = "secret123"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self) -> None:
        """Test that verify_password returns False for incorrect password."""
        password = "secret123"
        hashed = hash_password(password)

        assert verify_password("wrongpassword", hashed) is False

    def test_same_password_different_hashes(self) -> None:
        """Test that same password produces different hashes (due to salt)."""
        password = "secret123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


class TestAccessToken:
    """Tests for access token creation and verification."""

    def test_create_access_token(self) -> None:
        """Test that create_access_token returns a valid JWT."""
        data = {"sub": "123", "username": "testuser"}
        token = create_access_token(data)

        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_access_token(self) -> None:
        """Test that verify_token correctly decodes access token."""
        data = {"sub": "123", "username": "testuser"}
        token = create_access_token(data)

        payload = verify_token(token)

        assert payload["sub"] == "123"
        assert payload["username"] == "testuser"
        assert payload["type"] == "access"

    def test_create_access_token_custom_expiry(self) -> None:
        """Test access token with custom expiry."""
        data = {"sub": "123"}
        token = create_access_token(data, expires_delta=timedelta(hours=2))

        payload = verify_token(token)
        assert payload["sub"] == "123"

    def test_verify_expired_access_token(self) -> None:
        """Test that expired access token raises TokenExpiredError."""
        data = {"sub": "123"}
        token = create_access_token(data, expires_delta=timedelta(seconds=-1))

        with pytest.raises(TokenExpiredError, match="Token has expired"):
            verify_token(token)

    def test_verify_invalid_access_token(self) -> None:
        """Test that invalid token raises InvalidTokenError."""
        with pytest.raises(InvalidTokenError, match="Invalid token"):
            verify_token("invalid.token.here")

    def test_verify_access_token_wrong_type(self) -> None:
        """Test that refresh token fails verification as access token."""
        data = {"sub": "123"}
        refresh_token = create_refresh_token(data)

        with pytest.raises(InvalidTokenError, match="Invalid token type"):
            verify_token(refresh_token, token_type="access")


class TestRefreshToken:
    """Tests for refresh token creation and verification."""

    def test_create_refresh_token(self) -> None:
        """Test that create_refresh_token returns a valid JWT."""
        data = {"sub": "123", "username": "testuser"}
        token = create_refresh_token(data)

        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_refresh_token(self) -> None:
        """Test that verify_token correctly decodes refresh token."""
        data = {"sub": "123", "username": "testuser"}
        token = create_refresh_token(data)

        payload = verify_token(token, token_type="refresh")

        assert payload["sub"] == "123"
        assert payload["username"] == "testuser"
        assert payload["type"] == "refresh"

    def test_create_refresh_token_custom_expiry(self) -> None:
        """Test refresh token with custom expiry."""
        data = {"sub": "123"}
        token = create_refresh_token(data, expires_delta=timedelta(days=14))

        payload = verify_token(token, token_type="refresh")
        assert payload["sub"] == "123"

    def test_verify_expired_refresh_token(self) -> None:
        """Test that expired refresh token raises TokenExpiredError."""
        data = {"sub": "123"}
        token = create_refresh_token(data, expires_delta=timedelta(seconds=-1))

        with pytest.raises(TokenExpiredError, match="Token has expired"):
            verify_token(token, token_type="refresh")

    def test_verify_refresh_token_wrong_type(self) -> None:
        """Test that access token fails verification as refresh token."""
        data = {"sub": "123"}
        access_token = create_access_token(data)

        with pytest.raises(InvalidTokenError, match="Invalid token type"):
            verify_token(access_token, token_type="refresh")


class TestDecodeWithoutVerification:
    """Tests for decode_token_without_verification."""

    def test_decode_valid_token(self) -> None:
        """Test decoding a valid token without verification."""
        data = {"sub": "123", "username": "testuser"}
        token = create_access_token(data)

        payload = decode_token_without_verification(token)

        assert payload["sub"] == "123"
        assert payload["username"] == "testuser"

    def test_decode_expired_token(self) -> None:
        """Test that expired token can still be decoded without verification."""
        data = {"sub": "123"}
        token = create_access_token(data, expires_delta=timedelta(seconds=-1))

        payload = decode_token_without_verification(token)

        assert payload["sub"] == "123"

    def test_decode_invalid_token_format(self) -> None:
        """Test that invalid token format raises InvalidTokenError."""
        with pytest.raises(InvalidTokenError, match="Invalid token format"):
            decode_token_without_verification("not-a-valid-token")


class TestTokenEdgeCases:
    """Tests for edge cases in token handling."""

    def test_empty_payload(self) -> None:
        """Test token with empty payload."""
        token = create_access_token({})
        payload = verify_token(token)

        assert payload["type"] == "access"
        assert "exp" in payload

    def test_token_with_special_characters(self) -> None:
        """Test token with special characters in payload."""
        data = {"sub": "123", "info": "test@example.com!#$%"}
        token = create_access_token(data)
        payload = verify_token(token)

        assert payload["info"] == "test@example.com!#$%"

    def test_token_with_nested_data(self) -> None:
        """Test token with nested data structures."""
        data = {"sub": "123", "permissions": ["read", "write"]}
        token = create_access_token(data)
        payload = verify_token(token)

        assert payload["permissions"] == ["read", "write"]
