"""
Okta Authentication and RBAC Module for FastMCP
Provides JWT token validation and role-based access control
"""

import os
import time
import logging
from typing import Dict, Any, List, Callable, Optional
from functools import wraps

import jwt
from jwt import PyJWKClient
from cachetools import TTLCache
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

# Logging setup
logger = logging.getLogger(__name__)
security_logger = logging.getLogger('mcp.security')

# Token cache (1000 tokens, 1 hour TTL)
token_cache = TTLCache(maxsize=1000, ttl=3600)


class AuthenticationError(Exception):
    """Custom exception for authentication failures."""
    pass


class OktaConfig:
    """Okta configuration singleton."""

    def __init__(self):
        self.issuer = os.getenv('OKTA_ISSUER')
        self.audience = os.getenv('OKTA_AUDIENCE')
        self.jwks_uri = f"{self.issuer}/v1/keys" if self.issuer else None
        self.client_id = os.getenv('OKTA_CLIENT_ID')

        # Validate configuration
        if not all([self.issuer, self.audience]):
            logger.warning("Okta configuration incomplete - authentication will be disabled")

    @property
    def is_configured(self) -> bool:
        """Check if Okta is properly configured."""
        return bool(self.issuer and self.audience and self.jwks_uri)


# Global config instance
okta_config = OktaConfig()


# RBAC Configuration
ROLE_DEFINITIONS = {
    "mcp_viewer": {
        "description": "Read-only access to public data",
        "allowed_tools": ["echo_tool", "search_providers", "search_organizations", "lookup_npi"]
    },
    "mcp_analyst": {
        "description": "Data analyst access with advanced search",
        "allowed_tools": ["echo_tool", "search_providers", "search_organizations", "lookup_npi", "advanced_search"]
    },
    "mcp_clinician": {
        "description": "Healthcare provider access",
        "allowed_tools": ["echo_tool", "search_providers", "search_organizations", "lookup_npi", "advanced_search"]
    },
    "mcp_admin": {
        "description": "Full administrative access",
        "allowed_tools": ["*"]  # Access to all tools
    }
}


async def validate_okta_token(access_token: str) -> Dict[str, Any]:
    """
    Validate Okta JWT token with comprehensive security checks.

    Args:
        access_token: JWT access token from Okta

    Returns:
        Dict containing validated token claims

    Raises:
        AuthenticationError: If token validation fails
    """
    if not okta_config.is_configured:
        raise AuthenticationError("Okta authentication is not configured")

    # Check cache first
    cache_key = access_token[:32]  # Use token prefix as cache key
    if cache_key in token_cache:
        logger.debug("Token found in cache")
        return token_cache[cache_key]

    start_time = time.time()

    try:
        # Fetch JWKS and verify signature
        jwks_client = PyJWKClient(okta_config.jwks_uri, cache_jwk_set=True, lifespan=360)
        signing_key = jwks_client.get_signing_key_from_jwt(access_token)

        # Decode and validate all claims
        claims = jwt.decode(
            access_token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=okta_config.issuer,
            audience=okta_config.audience,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_aud": True,
                "verify_iss": True,
                "require": ["exp", "iat", "sub", "aud", "iss"]
            }
        )

        # Cache validated claims
        ttl = max(claims['exp'] - int(time.time()), 0)
        if ttl > 0:
            token_cache[cache_key] = claims

        # Logging
        duration = time.time() - start_time
        security_logger.info(f"Authentication success: user={claims.get('sub')}, duration={duration:.3f}s")

        return claims

    except jwt.ExpiredSignatureError:
        security_logger.warning("Token validation failed: expired")
        raise AuthenticationError("Token has expired. Please log in again.")
    except jwt.InvalidAudienceError:
        security_logger.error(f"Token validation failed: audience mismatch (expected: {okta_config.audience})")
        raise AuthenticationError("Token audience mismatch")
    except jwt.InvalidIssuerError:
        security_logger.error(f"Token validation failed: issuer mismatch (expected: {okta_config.issuer})")
        raise AuthenticationError("Token from untrusted issuer")
    except jwt.InvalidSignatureError:
        security_logger.error("Token validation failed: invalid signature")
        raise AuthenticationError("Token signature invalid")
    except Exception as e:
        security_logger.exception(f"Token validation error: {e}")
        raise AuthenticationError(f"Token validation failed: {str(e)}")


def get_user_permissions(groups: List[str]) -> List[str]:
    """
    Get list of allowed tools based on user's groups.

    Args:
        groups: List of Okta groups user belongs to

    Returns:
        List of tool names user can access
    """
    allowed_tools = set()

    for group in groups:
        if group in ROLE_DEFINITIONS:
            tools = ROLE_DEFINITIONS[group]["allowed_tools"]
            if "*" in tools:
                return ["*"]  # Admin has access to everything
            allowed_tools.update(tools)

    return list(allowed_tools)


def require_role(*allowed_roles: str) -> Callable:
    """
    Check if user has required role.

    Args:
        allowed_roles: Roles that can access the resource

    Returns:
        Function that checks if auth context has required role
    """
    def check_access(auth_context: Dict[str, Any]) -> bool:
        if not okta_config.is_configured:
            # If Okta not configured, allow access (dev mode)
            logger.warning(f"Okta not configured - allowing access to tool requiring roles: {allowed_roles}")
            return True

        user_groups = auth_context.get('groups', [])

        # Admins have access to everything
        if "mcp_admin" in user_groups:
            return True

        # Check if user has any of the allowed roles
        has_access = any(role in user_groups for role in allowed_roles)

        if not has_access:
            logger.warning(f"Access denied: user groups {user_groups} do not match required roles {allowed_roles}")

        return has_access

    return check_access


def require_scope(*required_scopes: str) -> Callable:
    """
    Check if user has required OAuth scopes.

    Args:
        required_scopes: Scopes needed to access the resource

    Returns:
        Function that checks if auth context has required scopes
    """
    def check_access(auth_context: Dict[str, Any]) -> bool:
        if not okta_config.is_configured:
            return True

        token_scopes = auth_context.get('scp', [])
        has_scopes = all(scope in token_scopes for scope in required_scopes)

        if not has_scopes:
            logger.warning(f"Access denied: token scopes {token_scopes} missing required scopes {required_scopes}")

        return has_scopes

    return check_access


def can_access_tool(tool_name: str, groups: List[str]) -> bool:
    """
    Check if user with given groups can access a specific tool.

    Args:
        tool_name: Name of the tool
        groups: User's Okta groups

    Returns:
        True if user can access the tool
    """
    if not okta_config.is_configured:
        return True

    permissions = get_user_permissions(groups)

    # Admin has access to everything
    if "*" in permissions:
        return True

    return tool_name in permissions


class OktaAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate Okta tokens on all requests.
    """

    def __init__(self, app, public_paths: Optional[List[str]] = None):
        super().__init__(app)
        self.public_paths = public_paths or ["/", "/health", "/metrics", "/.well-known"]

    async def dispatch(self, request: Request, call_next):
        # Skip authentication for public paths
        if any(request.url.path.startswith(path) for path in self.public_paths):
            return await call_next(request)

        # If Okta not configured, allow all requests (dev mode)
        if not okta_config.is_configured:
            logger.debug("Okta not configured - allowing unauthenticated request")
            request.state.user = {"sub": "dev-user", "email": "dev@localhost", "groups": ["mcp_admin"]}
            request.state.authenticated = False
            return await call_next(request)

        # Extract Authorization header
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Missing or invalid Authorization header",
                headers={"WWW-Authenticate": "Bearer"}
            )

        token = auth_header.replace("Bearer ", "")

        try:
            # Validate token
            claims = await validate_okta_token(token)

            # Attach user info to request state
            request.state.user = claims
            request.state.user_id = claims.get('sub')
            request.state.email = claims.get('email', '')
            request.state.groups = claims.get('groups', [])
            request.state.scopes = claims.get('scp', [])
            request.state.permissions = get_user_permissions(claims.get('groups', []))
            request.state.authenticated = True

            logger.debug(f"Request authenticated: user={claims.get('sub')}, groups={claims.get('groups', [])}")

        except AuthenticationError as e:
            security_logger.warning(f"Authentication failed: {e}")
            raise HTTPException(
                status_code=401,
                detail=str(e),
                headers={"WWW-Authenticate": f'Bearer error="invalid_token", error_description="{e}"'}
            )
        except Exception as e:
            logger.exception(f"Authentication middleware error: {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal authentication error"
            )

        return await call_next(request)


def get_auth_context_from_request(request: Request) -> Dict[str, Any]:
    """
    Extract authentication context from request state.

    Args:
        request: FastAPI request object

    Returns:
        Dict with user authentication info
    """
    if not hasattr(request, 'state'):
        return {}

    return {
        'sub': getattr(request.state, 'user_id', None),
        'email': getattr(request.state, 'email', ''),
        'groups': getattr(request.state, 'groups', []),
        'scp': getattr(request.state, 'scopes', []),
        'authenticated': getattr(request.state, 'authenticated', False)
    }
