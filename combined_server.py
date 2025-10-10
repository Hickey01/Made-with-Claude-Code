"""
Combined FastMCP Server - Echo & NPPES NPI Registry with Okta Authentication

This server provides both simple echo functionality and access to the
National Plan and Provider Enumeration System (NPPES) NPI Registry API.

Features:
- Okta OAuth 2.0 authentication
- Role-Based Access Control (RBAC)
- JWT token validation
- Secure tool access management
"""

import os
import time
import logging
from typing import Optional, Dict, Any, List, Callable
from fastmcp import FastMCP
import httpx

# Load environment variables (optional - uses system env if not available)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not available, will use system environment variables

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
security_logger = logging.getLogger('mcp.security')

# ============================================================================
# OKTA AUTHENTICATION & RBAC
# ============================================================================

# Try to import FastMCP's native JWT verifier
try:
    from fastmcp.server.auth.verifiers import JWTVerifier
    JWT_VERIFIER_AVAILABLE = True
except ImportError:
    logger.warning("FastMCP JWTVerifier not available. Authentication will be disabled.")
    JWT_VERIFIER_AVAILABLE = False


class OktaConfig:
    """Okta configuration"""
    def __init__(self):
        self.issuer = os.getenv('OKTA_ISSUER')
        self.audience = os.getenv('OKTA_AUDIENCE')
        self.jwks_uri = f"{self.issuer}/v1/keys" if self.issuer else None
        self.client_id = os.getenv('OKTA_CLIENT_ID')

    @property
    def is_configured(self) -> bool:
        """Check if Okta is properly configured."""
        return bool(self.issuer and self.audience and self.jwks_uri and JWT_VERIFIER_AVAILABLE)


# Global config instance
okta_config = OktaConfig()


# RBAC Role Definitions
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


# JWT Verifier instance (None if not available)
jwt_verifier = None
if okta_config.is_configured:
    try:
        jwt_verifier = JWTVerifier(
            jwks_uri=okta_config.jwks_uri,
            issuer=okta_config.issuer,
            audience=okta_config.audience,
            algorithm="RS256"
        )
        logger.info(f"JWT Verifier initialized for Okta issuer: {okta_config.issuer}")
    except Exception as e:
        logger.error(f"Failed to initialize JWT verifier: {e}")
        jwt_verifier = None


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
    Create a canAccess function that checks if user has required role from Okta token.

    This works with FastMCP's tool.canAccess mechanism.

    Args:
        allowed_roles: Roles that can access the resource (e.g., "mcp_viewer", "mcp_admin")

    Returns:
        Function that FastMCP calls with auth_context to check access
    """
    def check_access(auth_context: Dict[str, Any]) -> bool:
        # If Okta not configured, allow access (dev mode)
        if not okta_config.is_configured or jwt_verifier is None:
            logger.debug(f"Okta not configured - allowing access in dev mode")
            return True

        # Extract groups from the validated token claims
        # FastMCP passes the validated JWT claims as auth_context
        user_groups = auth_context.get('groups', [])
        user_sub = auth_context.get('sub', 'unknown')

        # Admins have access to everything
        if "mcp_admin" in user_groups:
            logger.debug(f"Admin access granted for user {user_sub}")
            return True

        # Check if user has any of the allowed roles
        has_access = any(role in user_groups for role in allowed_roles)

        if has_access:
            logger.debug(f"Access granted for user {user_sub} with groups {user_groups}")
        else:
            logger.warning(f"Access denied for user {user_sub}: groups {user_groups} do not match required roles {allowed_roles}")

        return has_access

    return check_access


# No custom middleware needed - FastMCP handles JWT verification natively!


# ============================================================================
# FASTMCP SERVER INITIALIZATION
# ============================================================================

# Create server with JWT verifier if available
if jwt_verifier:
    mcp = FastMCP(
        "CHG Healthcare Echo & NPPES Combined Server",
        token_verifier=jwt_verifier
    )
    logger.info("✅ Okta authentication ENABLED - JWT verifier active")
    logger.info(f"   Issuer: {okta_config.issuer}")
    logger.info(f"   Audience: {okta_config.audience}")
    OKTA_ENABLED = True
else:
    mcp = FastMCP("CHG Healthcare Echo & NPPES Combined Server")
    logger.warning("⚠️  Okta authentication NOT configured - running in development mode")
    logger.warning("   All tools accessible without authentication")
    OKTA_ENABLED = False


# ============================================================================
# ECHO TOOLS
# ============================================================================

@mcp.tool
def echo_tool(text: str) -> str:
    """Echo the input text - available to all authenticated users"""
    return text


@mcp.resource("echo://static")
def echo_resource() -> str:
    """Static echo resource"""
    return "Echo!"


@mcp.resource("echo://{text}")
def echo_template(text: str) -> str:
    """Echo the input text as a resource"""
    return f"Echo: {text}"


@mcp.prompt()
def echo_prompt(text: str) -> str:
    """Echo prompt that returns the input text"""
    return text


# ============================================================================
# NPPES NPI REGISTRY TOOLS
# ============================================================================

# Base URL for NPPES API
NPPES_BASE_URL = "https://npiregistry.cms.hhs.gov/api/"


async def make_nppes_request(params: Dict[str, Any]) -> Dict[str, Any]:
    """Make a request to the NPPES API with error handling"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(NPPES_BASE_URL, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            return {"error": f"HTTP error occurred: {str(e)}"}
        except Exception as e:
            return {"error": f"An error occurred: {str(e)}"}


def format_provider_result(result: Dict[str, Any]) -> str:
    """Format a single provider result for display"""
    try:
        number = result.get("number", "N/A")
        enumeration_type = result.get("enumeration_type", "N/A")

        # Get basic info
        basic = result.get("basic", {})
        name = basic.get("name", "N/A")
        first_name = basic.get("first_name", "")
        last_name = basic.get("last_name", "")
        credential = basic.get("credential", "")

        if first_name or last_name:
            name = f"{first_name} {last_name}".strip()
            if credential:
                name += f", {credential}"

        # Get primary address
        addresses = result.get("addresses", [])
        address_info = "N/A"
        if addresses:
            primary = next((addr for addr in addresses if addr.get("address_purpose") == "LOCATION"), addresses[0])
            city = primary.get("city", "")
            state = primary.get("state", "")
            postal_code = primary.get("postal_code", "")
            address_info = f"{city}, {state} {postal_code}".strip()

        # Get primary taxonomy
        taxonomies = result.get("taxonomies", [])
        taxonomy_info = "N/A"
        if taxonomies:
            primary = next((tax for tax in taxonomies if tax.get("primary")), taxonomies[0])
            taxonomy_info = primary.get("desc", "N/A")

        return f"""NPI: {number}
Type: {enumeration_type}
Name: {name}
Location: {address_info}
Primary Taxonomy: {taxonomy_info}
"""
    except Exception as e:
        return f"Error formatting result: {str(e)}"


@mcp.tool()
async def lookup_npi(npi_number: str) -> str:
    """
    Look up a healthcare provider by their NPI number.

    Args:
        npi_number: The 10-digit National Provider Identifier (NPI) number

    Returns:
        Detailed information about the provider including name, address, and credentials
    """
    params = {"number": npi_number, "version": "2.1"}

    data = await make_nppes_request(params)

    if "error" in data:
        return f"Error: {data['error']}"

    result_count = data.get("result_count", 0)
    if result_count == 0:
        return f"No provider found with NPI number: {npi_number}"

    results = data.get("results", [])
    if not results:
        return "No results returned"

    return format_provider_result(results[0])


@mcp.tool()
async def search_providers(
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    postal_code: Optional[str] = None,
    limit: int = 10
) -> str:
    """
    Search for individual healthcare providers (NPI-1).

    Args:
        first_name: Provider's first name
        last_name: Provider's last name
        city: City name
        state: Two-letter state abbreviation (e.g., CA, NY)
        postal_code: 5-digit ZIP code
        limit: Maximum number of results to return (default 10, max 200)

    Returns:
        List of matching providers with their details
    """
    params = {
        "version": "2.1",
        "enumeration_type": "NPI-1",
        "limit": min(limit, 200)
    }

    if first_name:
        params["first_name"] = first_name
    if last_name:
        params["last_name"] = last_name
    if city:
        params["city"] = city
    if state:
        params["state"] = state
    if postal_code:
        params["postal_code"] = postal_code

    data = await make_nppes_request(params)

    if "error" in data:
        return f"Error: {data['error']}"

    result_count = data.get("result_count", 0)
    if result_count == 0:
        return "No providers found matching the search criteria"

    results = data.get("results", [])
    output = [f"Found {result_count} provider(s):\n"]

    for i, result in enumerate(results[:limit], 1):
        output.append(f"\n--- Provider {i} ---")
        output.append(format_provider_result(result))

    return "\n".join(output)


@mcp.tool()
async def search_organizations(
    organization_name: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    postal_code: Optional[str] = None,
    limit: int = 10
) -> str:
    """
    Search for healthcare organizations (NPI-2).

    Args:
        organization_name: Name of the healthcare organization
        city: City name
        state: Two-letter state abbreviation (e.g., CA, NY)
        postal_code: 5-digit ZIP code
        limit: Maximum number of results to return (default 10, max 200)

    Returns:
        List of matching organizations with their details
    """
    params = {
        "version": "2.1",
        "enumeration_type": "NPI-2",
        "limit": min(limit, 200)
    }

    if organization_name:
        params["organization_name"] = organization_name
    if city:
        params["city"] = city
    if state:
        params["state"] = state
    if postal_code:
        params["postal_code"] = postal_code

    data = await make_nppes_request(params)

    if "error" in data:
        return f"Error: {data['error']}"

    result_count = data.get("result_count", 0)
    if result_count == 0:
        return "No organizations found matching the search criteria"

    results = data.get("results", [])
    output = [f"Found {result_count} organization(s):\n"]

    for i, result in enumerate(results[:limit], 1):
        output.append(f"\n--- Organization {i} ---")
        output.append(format_provider_result(result))

    return "\n".join(output)


@mcp.tool()
async def advanced_search(
    taxonomy_description: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    organization_name: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    postal_code: Optional[str] = None,
    country_code: Optional[str] = None,
    limit: int = 10
) -> str:
    """
    Perform an advanced search with multiple criteria.

    Args:
        taxonomy_description: Provider specialty or taxonomy description (e.g., "Family Medicine", "Cardiology")
        first_name: Provider's first name (for individuals)
        last_name: Provider's last name (for individuals)
        organization_name: Organization name (for organizations)
        city: City name
        state: Two-letter state abbreviation (e.g., CA, NY)
        postal_code: 5-digit ZIP code
        country_code: Two-letter country code (default US)
        limit: Maximum number of results to return (default 10, max 200)

    Returns:
        List of matching providers/organizations with their details
    """
    params = {
        "version": "2.1",
        "limit": min(limit, 200)
    }

    if taxonomy_description:
        params["taxonomy_description"] = taxonomy_description
    if first_name:
        params["first_name"] = first_name
    if last_name:
        params["last_name"] = last_name
    if organization_name:
        params["organization_name"] = organization_name
    if city:
        params["city"] = city
    if state:
        params["state"] = state
    if postal_code:
        params["postal_code"] = postal_code
    if country_code:
        params["country_code"] = country_code

    data = await make_nppes_request(params)

    if "error" in data:
        return f"Error: {data['error']}"

    result_count = data.get("result_count", 0)
    if result_count == 0:
        return "No results found matching the search criteria"

    results = data.get("results", [])
    output = [f"Found {result_count} result(s):\n"]

    for i, result in enumerate(results[:limit], 1):
        output.append(f"\n--- Result {i} ---")
        output.append(format_provider_result(result))

    return "\n".join(output)


# ============================================================================
# RESOURCES
# ============================================================================

@mcp.resource("npi://{npi_number}")
async def npi_resource(npi_number: str) -> str:
    """
    Resource for looking up provider information by NPI number.

    Access provider details using: npi://1234567890
    """
    return await lookup_npi(npi_number)


@mcp.resource("npi://search/providers")
async def provider_search_resource() -> str:
    """Resource showing example provider searches."""
    return """NPPES Provider Search Resource

Available search parameters:
- first_name: Provider's first name
- last_name: Provider's last name
- city: City name
- state: Two-letter state code
- postal_code: 5-digit ZIP code

Use the search_providers tool to perform searches.

Example: search_providers(last_name="Smith", state="CA", limit=5)
"""


@mcp.resource("npi://search/organizations")
async def organization_search_resource() -> str:
    """Resource showing example organization searches."""
    return """NPPES Organization Search Resource

Available search parameters:
- organization_name: Name of the healthcare organization
- city: City name
- state: Two-letter state code
- postal_code: 5-digit ZIP code

Use the search_organizations tool to perform searches.

Example: search_organizations(organization_name="Hospital", city="Boston", state="MA")
"""


# ============================================================================
# PROMPTS
# ============================================================================

@mcp.prompt()
def find_provider_prompt(criteria: str) -> str:
    """
    Generate a prompt for finding healthcare providers.

    Args:
        criteria: Description of what you're looking for (e.g., "cardiologist in New York")
    """
    return f"""Help me find healthcare providers matching these criteria: {criteria}

Please use the NPPES NPI Registry tools to search for providers. Consider:
1. Whether to search for individuals (search_providers) or organizations (search_organizations)
2. What search parameters are available (name, location, specialty)
3. How to refine the search if too many results are returned

Provide the search results in a clear, organized format."""


@mcp.prompt()
def explain_npi_prompt(npi_number: str) -> str:
    """
    Generate a prompt for explaining NPI information.

    Args:
        npi_number: The NPI number to look up and explain
    """
    return f"""Look up NPI number {npi_number} and provide a comprehensive explanation of:
1. The provider's name and credentials
2. Their primary specialty/taxonomy
3. Their practice location(s)
4. The type of provider (individual vs organization)
5. Any other relevant information from the NPI registry

Use the lookup_npi tool to retrieve this information."""


# ============================================================================
# SECURITY & RBAC CONFIGURATION
# ============================================================================

# Apply role-based access control using FastMCP's canAccess mechanism
# Note: In FastMCP, we apply canAccess directly to the decorated functions
# The decorator creates the tool object and we can set canAccess on it
if OKTA_ENABLED:
    logger.info("Applying RBAC to tools...")

    # Echo tool - available to all authenticated users (no restriction needed)

    # NPPES tools - require viewer role or higher
    lookup_npi.canAccess = require_role("mcp_viewer", "mcp_analyst", "mcp_clinician", "mcp_admin")
    search_providers.canAccess = require_role("mcp_viewer", "mcp_analyst", "mcp_clinician", "mcp_admin")
    search_organizations.canAccess = require_role("mcp_viewer", "mcp_analyst", "mcp_clinician", "mcp_admin")
    logger.info("   ✓ lookup_npi, search_providers, search_organizations: viewer, analyst, clinician, or admin")

    # Advanced search - requires analyst role or higher
    advanced_search.canAccess = require_role("mcp_analyst", "mcp_clinician", "mcp_admin")
    logger.info("   ✓ advanced_search: analyst, clinician, or admin")

    logger.info("✅ RBAC configuration complete")
else:
    logger.warning("⚠️  Running without RBAC - all tools accessible")


# ============================================================================
# SERVER STARTUP
# ============================================================================

if __name__ == "__main__":
    # Run the server
    host = os.getenv('MCP_SERVER_HOST', '0.0.0.0')
    port = int(os.getenv('MCP_SERVER_PORT', 8000))

    logger.info(f"Starting MCP server on {host}:{port}")
    logger.info("=" * 60)
    logger.info("SECURITY STATUS:")
    logger.info(f"  - Authentication: {'ENABLED' if OKTA_ENABLED else 'DISABLED (DEV MODE)'}")
    logger.info(f"  - RBAC: {'ENABLED' if OKTA_ENABLED else 'DISABLED'}")
    if OKTA_ENABLED:
        logger.info(f"  - Okta Issuer: {okta_config.issuer}")
        logger.info(f"  - Audience: {okta_config.audience}")
    logger.info("=" * 60)

    mcp.run()
