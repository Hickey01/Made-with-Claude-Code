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
        "description": "Data analyst access with advanced search and Tableau",
        "allowed_tools": ["echo_tool", "search_providers", "search_organizations", "lookup_npi", "advanced_search",
                          "list_tableau_workbooks", "query_tableau_view", "get_tableau_datasource"]
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
        "CHG Healthcare Multi-Tool Server (Echo, NPPES, Tableau)",
        token_verifier=jwt_verifier
    )
    logger.info("✅ Okta authentication ENABLED - JWT verifier active")
    logger.info(f"   Issuer: {okta_config.issuer}")
    logger.info(f"   Audience: {okta_config.audience}")
    OKTA_ENABLED = True
else:
    mcp = FastMCP("CHG Healthcare Multi-Tool Server (Echo, NPPES, Tableau)")
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
# TABLEAU INTEGRATION
# ============================================================================

# Tableau configuration (optional - for demo purposes)
try:
    import tableauserverclient as TSC
    TABLEAU_AVAILABLE = True
except ImportError:
    logger.warning("tableauserverclient not available. Tableau tools will return mock data.")
    TABLEAU_AVAILABLE = False


class TableauConfig:
    """Tableau Server configuration"""
    def __init__(self):
        self.server_url = os.getenv('TABLEAU_SERVER_URL')
        self.site_id = os.getenv('TABLEAU_SITE_ID', '')
        self.token_name = os.getenv('TABLEAU_TOKEN_NAME')
        self.token_value = os.getenv('TABLEAU_TOKEN_VALUE')
        self.username = os.getenv('TABLEAU_USERNAME')
        self.password = os.getenv('TABLEAU_PASSWORD')

    @property
    def is_configured(self) -> bool:
        """Check if Tableau is properly configured."""
        has_server = bool(self.server_url)
        has_auth = bool((self.token_name and self.token_value) or (self.username and self.password))
        return has_server and has_auth and TABLEAU_AVAILABLE


# Global Tableau config
tableau_config = TableauConfig()


def get_tableau_server():
    """Get authenticated Tableau Server connection."""
    if not tableau_config.is_configured:
        raise Exception("Tableau not configured. Set TABLEAU_SERVER_URL and authentication credentials.")

    server = TSC.Server(tableau_config.server_url, use_server_version=True)

    # Authenticate with token or username/password
    if tableau_config.token_name and tableau_config.token_value:
        auth = TSC.PersonalAccessTokenAuth(
            tableau_config.token_name,
            tableau_config.token_value,
            tableau_config.site_id
        )
    else:
        auth = TSC.TableauAuth(
            tableau_config.username,
            tableau_config.password,
            tableau_config.site_id
        )

    server.auth.sign_in(auth)
    return server


@mcp.tool()
async def list_tableau_workbooks(limit: int = 20) -> str:
    """
    List Tableau workbooks available on the server.

    Requires: mcp_analyst, mcp_admin roles

    Args:
        limit: Maximum number of workbooks to return (default 20)

    Returns:
        List of workbooks with names, projects, and view counts
    """
    if not tableau_config.is_configured:
        # Return mock data for demo
        return """Tableau Workbooks (Demo Mode - Tableau not configured):

--- Workbook 1 ---
Name: Healthcare Analytics Dashboard
Project: Executive Reports
Views: 12
Owner: analytics-team
Created: 2024-01-15
URL: https://tableau.example.com/workbooks/healthcare-analytics

--- Workbook 2 ---
Name: Provider Performance Metrics
Project: Operations
Views: 8
Owner: ops-team
Created: 2024-02-20
URL: https://tableau.example.com/workbooks/provider-performance

--- Workbook 3 ---
Name: Financial Summary Q1 2024
Project: Finance
Views: 5
Owner: finance-team
Created: 2024-03-10
URL: https://tableau.example.com/workbooks/financial-summary

ℹ️  To connect to real Tableau server, configure:
   - TABLEAU_SERVER_URL
   - TABLEAU_TOKEN_NAME and TABLEAU_TOKEN_VALUE
   (or TABLEAU_USERNAME and TABLEAU_PASSWORD)
"""

    try:
        server = get_tableau_server()
        workbooks, pagination = server.workbooks.get()

        output = [f"Found {pagination.total_available} Tableau workbooks:\n"]

        for i, wb in enumerate(list(workbooks)[:limit], 1):
            output.append(f"\n--- Workbook {i} ---")
            output.append(f"Name: {wb.name}")
            output.append(f"Project: {wb.project_name}")
            output.append(f"Views: {len(list(server.workbooks.get_views(wb.id)))}")
            output.append(f"Owner: {wb.owner_id}")
            output.append(f"Created: {wb.created_at}")
            output.append(f"URL: {wb.webpage_url}")

        server.auth.sign_out()
        return "\n".join(output)

    except Exception as e:
        logger.error(f"Tableau error: {e}")
        return f"Error accessing Tableau: {str(e)}"


@mcp.tool()
async def query_tableau_view(
    workbook_name: str,
    view_name: str,
    filters: Optional[str] = None
) -> str:
    """
    Query a specific Tableau view/dashboard.

    Requires: mcp_analyst, mcp_admin roles

    Args:
        workbook_name: Name of the workbook
        view_name: Name of the view/dashboard within the workbook
        filters: Optional filters in format "field1:value1,field2:value2"

    Returns:
        View details and data summary
    """
    if not tableau_config.is_configured:
        # Return mock data for demo
        return f"""Tableau View Query (Demo Mode):

Workbook: {workbook_name}
View: {view_name}
Filters: {filters or 'None'}

Mock Results:
- Total Records: 1,247
- Date Range: 2024-01-01 to 2024-03-31
- Regions: West (42%), East (31%), Central (27%)
- Top Metric: $2.3M revenue

ℹ️  To query real Tableau data, configure Tableau server credentials.
"""

    try:
        server = get_tableau_server()

        # Find the workbook
        req_option = TSC.RequestOptions()
        req_option.filter.add(TSC.Filter(TSC.RequestOptions.Field.Name,
                                        TSC.RequestOptions.Operator.Equals,
                                        workbook_name))
        workbooks, _ = server.workbooks.get(req_option)

        if not workbooks:
            return f"Workbook '{workbook_name}' not found"

        workbook = workbooks[0]

        # Get views in the workbook
        server.workbooks.populate_views(workbook)
        views = [v for v in workbook.views if v.name == view_name]

        if not views:
            return f"View '{view_name}' not found in workbook '{workbook_name}'"

        view = views[0]

        # Build output
        output = [f"Tableau View: {view.name}"]
        output.append(f"Workbook: {workbook.name}")
        output.append(f"URL: {view.webpage_url}")
        output.append(f"ID: {view.id}")
        if filters:
            output.append(f"Filters: {filters}")

        # Note: Actual data extraction requires Tableau's REST API or Hyper API
        output.append("\nℹ️  Use Tableau's web interface to view full data and visualizations")

        server.auth.sign_out()
        return "\n".join(output)

    except Exception as e:
        logger.error(f"Tableau error: {e}")
        return f"Error querying Tableau view: {str(e)}"


@mcp.tool()
async def get_tableau_datasource(datasource_name: str) -> str:
    """
    Get information about a Tableau data source.

    Requires: mcp_analyst, mcp_admin roles

    Args:
        datasource_name: Name of the data source

    Returns:
        Data source details including connections, fields, and metadata
    """
    if not tableau_config.is_configured:
        return f"""Tableau Data Source (Demo Mode):

Name: {datasource_name}
Type: Published Data Source
Connection: Snowflake
Database: PROD_ANALYTICS
Schema: HEALTHCARE

Fields:
- patient_id (String)
- provider_npi (String)
- visit_date (Date)
- diagnosis_code (String)
- charge_amount (Number)
- insurance_type (String)

Last Updated: 2024-03-15 14:30:00
Owner: data-team
Certified: Yes

ℹ️  Configure Tableau server to access real data sources.
"""

    try:
        server = get_tableau_server()

        req_option = TSC.RequestOptions()
        req_option.filter.add(TSC.Filter(TSC.RequestOptions.Field.Name,
                                        TSC.RequestOptions.Operator.Equals,
                                        datasource_name))
        datasources, _ = server.datasources.get(req_option)

        if not datasources:
            return f"Data source '{datasource_name}' not found"

        ds = datasources[0]

        output = [f"Tableau Data Source: {ds.name}"]
        output.append(f"ID: {ds.id}")
        output.append(f"Project: {ds.project_name}")
        output.append(f"Type: {ds.datasource_type}")
        output.append(f"Created: {ds.created_at}")
        output.append(f"Updated: {ds.updated_at}")
        output.append(f"Certified: {ds.certified}")
        if ds.certification_note:
            output.append(f"Certification Note: {ds.certification_note}")

        server.auth.sign_out()
        return "\n".join(output)

    except Exception as e:
        logger.error(f"Tableau error: {e}")
        return f"Error getting data source: {str(e)}"


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

    # Tableau tools - require analyst role or admin
    list_tableau_workbooks.canAccess = require_role("mcp_analyst", "mcp_admin")
    query_tableau_view.canAccess = require_role("mcp_analyst", "mcp_admin")
    get_tableau_datasource.canAccess = require_role("mcp_analyst", "mcp_admin")
    logger.info("   ✓ Tableau tools (list_tableau_workbooks, query_tableau_view, get_tableau_datasource): analyst or admin")

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
