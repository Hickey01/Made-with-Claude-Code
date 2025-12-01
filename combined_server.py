"""
Combined FastMCP Server - Echo, NPPES, dbt Cloud & Snowflake with Okta Authentication

This server provides simple echo functionality, access to the
National Plan and Provider Enumeration System (NPPES) NPI Registry API,
dbt Cloud integration, and Snowflake data platform access.

Features:
- Okta OAuth 2.0 authentication
- Role-Based Access Control (RBAC)
- JWT token validation
- Secure tool access management
- dbt Cloud API integration with OAuth
- Snowflake data platform integration
"""

import os
import time
import logging
from typing import Optional, Dict, Any, List, Callable
from fastmcp import FastMCP, Context
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
        "description": "Data analyst access with advanced search, dbt Cloud, and Snowflake",
        "allowed_tools": ["echo_tool", "search_providers", "search_organizations", "lookup_npi", "advanced_search",
                          "list_dbt_projects", "list_dbt_jobs", "trigger_dbt_job", "get_dbt_run_status",
                          "query_dbt_models", "execute_snowflake_query", "list_snowflake_databases",
                          "list_snowflake_schemas", "list_snowflake_tables", "describe_snowflake_table",
                          "list_snowflake_warehouses"]
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
        "CHG Healthcare Multi-Tool Server (Echo, NPPES, dbt Cloud, Snowflake)",
        token_verifier=jwt_verifier
    )
    logger.info("✅ Okta authentication ENABLED - JWT verifier active")
    logger.info(f"   Issuer: {okta_config.issuer}")
    logger.info(f"   Audience: {okta_config.audience}")
    OKTA_ENABLED = True
else:
    mcp = FastMCP("CHG Healthcare Multi-Tool Server (Echo, NPPES, dbt Cloud, Snowflake)")
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


@mcp.tool
def snowflake_diagnostics() -> str:
    """Diagnostic tool to check Snowflake OAuth configuration."""
    import os
    lines = ["=== Snowflake Diagnostics ==="]
    lines.append("SNOWFLAKE_AVAILABLE: " + str(SNOWFLAKE_AVAILABLE))
    lines.append("OAUTH_ENABLED env: " + str(os.getenv("SNOWFLAKE_OAUTH_ENABLED", "NOT SET")))
    lines.append("ACCOUNT env: " + str(os.getenv("SNOWFLAKE_ACCOUNT", "NOT SET")))
    lines.append("oauth_enabled: " + str(snowflake_config.oauth_enabled))
    lines.append("is_oauth_mode: " + str(snowflake_config.is_oauth_mode))
    lines.append("is_configured: " + str(snowflake_config.is_configured))
    if snowflake_config.is_oauth_mode:
        lines.append("Status: OAuth ACTIVE")
    elif not SNOWFLAKE_AVAILABLE:
        lines.append("Status: DEMO - snowflake package missing")
    else:
        lines.append("Status: DEMO MODE")
    sep = chr(10)
    return sep.join(lines)



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


@mcp.tool
def snowflake_diagnostics() -> str:
    """Diagnostic tool to check Snowflake OAuth configuration."""
    import os
    lines = ["=== Snowflake Diagnostics ==="]
    lines.append("SNOWFLAKE_AVAILABLE: " + str(SNOWFLAKE_AVAILABLE))
    lines.append("OAUTH_ENABLED env: " + str(os.getenv("SNOWFLAKE_OAUTH_ENABLED", "NOT SET")))
    lines.append("ACCOUNT env: " + str(os.getenv("SNOWFLAKE_ACCOUNT", "NOT SET")))
    lines.append("oauth_enabled: " + str(snowflake_config.oauth_enabled))
    lines.append("is_oauth_mode: " + str(snowflake_config.is_oauth_mode))
    lines.append("is_configured: " + str(snowflake_config.is_configured))
    if snowflake_config.is_oauth_mode:
        lines.append("Status: OAuth ACTIVE")
    elif not SNOWFLAKE_AVAILABLE:
        lines.append("Status: DEMO - snowflake package missing")
    else:
        lines.append("Status: DEMO MODE")
    sep = chr(10)
    return sep.join(lines)



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
# DBT CLOUD INTEGRATION
# ============================================================================

class DbtCloudConfig:
    """dbt Cloud configuration"""
    def __init__(self):
        self.api_url = os.getenv('DBT_CLOUD_API_URL', 'https://cloud.getdbt.com/api/v2')
        self.account_id = os.getenv('DBT_CLOUD_ACCOUNT_ID')
        self.service_token = os.getenv('DBT_CLOUD_SERVICE_TOKEN')  # Service account token
        # OAuth configuration for user-level authentication
        self.oauth_client_id = os.getenv('DBT_CLOUD_OAUTH_CLIENT_ID')
        self.oauth_client_secret = os.getenv('DBT_CLOUD_OAUTH_CLIENT_SECRET')

    @property
    def is_configured(self) -> bool:
        """Check if dbt Cloud is properly configured."""
        has_base = bool(self.api_url and self.account_id)
        has_auth = bool(self.service_token or (self.oauth_client_id and self.oauth_client_secret))
        return has_base and has_auth


# Global dbt Cloud config
dbt_config = DbtCloudConfig()


async def make_dbt_request(
    endpoint: str,
    method: str = "GET",
    params: Optional[Dict[str, Any]] = None,
    json_data: Optional[Dict[str, Any]] = None,
    user_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Make a request to the dbt Cloud API.

    Args:
        endpoint: API endpoint path (e.g., "accounts/{account_id}/projects")
        method: HTTP method (GET, POST, etc.)
        params: Query parameters
        json_data: JSON body for POST/PATCH requests
        user_token: Optional user OAuth token for user-level requests

    Returns:
        API response as dictionary
    """
    if not dbt_config.is_configured:
        return {"error": "dbt Cloud not configured. Set DBT_CLOUD_ACCOUNT_ID and authentication credentials."}

    url = f"{dbt_config.api_url}/{endpoint}"

    # Use user token if provided, otherwise fall back to service token
    token = user_token if user_token else dbt_config.service_token

    if not token:
        return {"error": "No authentication token available"}

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"dbt Cloud API error: {e}")
            return {"error": f"HTTP error occurred: {str(e)}"}
        except Exception as e:
            logger.error(f"dbt Cloud request error: {e}")
            return {"error": f"An error occurred: {str(e)}"}


@mcp.tool()
async def list_dbt_projects(limit: int = 20) -> str:
    """
    List dbt Cloud projects in the account.

    Requires: mcp_analyst, mcp_admin roles

    Args:
        limit: Maximum number of projects to return (default 20)

    Returns:
        List of dbt Cloud projects with details
    """
    if not dbt_config.is_configured:
        return """dbt Cloud Projects (Demo Mode - dbt Cloud not configured):

--- Project 1 ---
ID: 12345
Name: Healthcare Analytics
Repository: github.com/company/healthcare-dbt
State: Active
Created: 2024-01-15

--- Project 2 ---
Name: Provider Data Warehouse
Repository: github.com/company/provider-dbt
State: Active
Created: 2024-02-10

ℹ️  To connect to real dbt Cloud, configure:
   - DBT_CLOUD_ACCOUNT_ID
   - DBT_CLOUD_SERVICE_TOKEN or OAuth credentials
"""

    endpoint = f"accounts/{dbt_config.account_id}/projects/"
    data = await make_dbt_request(endpoint, params={"limit": limit})

    if "error" in data:
        return f"Error: {data['error']}"

    projects = data.get("data", [])
    if not projects:
        return "No projects found in dbt Cloud account"

    output = [f"Found {len(projects)} dbt Cloud project(s):\n"]

    for i, project in enumerate(projects, 1):
        output.append(f"\n--- Project {i} ---")
        output.append(f"ID: {project.get('id', 'N/A')}")
        output.append(f"Name: {project.get('name', 'N/A')}")
        output.append(f"Repository: {project.get('repository', {}).get('remote_url', 'N/A')}")
        output.append(f"State: {project.get('state', 'N/A')}")
        output.append(f"Created: {project.get('created_at', 'N/A')}")

    return "\n".join(output)


@mcp.tool()
async def list_dbt_jobs(project_id: Optional[int] = None, limit: int = 20) -> str:
    """
    List dbt Cloud jobs, optionally filtered by project.

    Requires: mcp_analyst, mcp_admin roles

    Args:
        project_id: Optional project ID to filter jobs
        limit: Maximum number of jobs to return (default 20)

    Returns:
        List of dbt Cloud jobs with schedules and status
    """
    if not dbt_config.is_configured:
        return """dbt Cloud Jobs (Demo Mode):

--- Job 1 ---
ID: 67890
Name: Daily Production Run
Project: Healthcare Analytics
Schedule: 0 6 * * * (daily at 6am)
State: Active
Last Run: Success (2024-03-15 06:15:00)

--- Job 2 ---
Name: Hourly Refresh
Project: Provider Data Warehouse
Schedule: 0 * * * * (every hour)
State: Active
Last Run: Success (2024-03-15 14:00:00)

ℹ️  Configure dbt Cloud to access real jobs.
"""

    endpoint = f"accounts/{dbt_config.account_id}/jobs/"
    params = {"limit": limit}
    if project_id:
        params["project_id"] = project_id

    data = await make_dbt_request(endpoint, params=params)

    if "error" in data:
        return f"Error: {data['error']}"

    jobs = data.get("data", [])
    if not jobs:
        return "No jobs found"

    output = [f"Found {len(jobs)} dbt Cloud job(s):\n"]

    for i, job in enumerate(jobs, 1):
        output.append(f"\n--- Job {i} ---")
        output.append(f"ID: {job.get('id', 'N/A')}")
        output.append(f"Name: {job.get('name', 'N/A')}")
        output.append(f"Project ID: {job.get('project_id', 'N/A')}")
        output.append(f"Environment ID: {job.get('environment_id', 'N/A')}")
        output.append(f"State: {job.get('state', 'N/A')}")

        schedule = job.get("schedule", {})
        if schedule.get("cron"):
            output.append(f"Schedule: {schedule.get('cron')}")

        execute_steps = job.get("execute_steps", [])
        if execute_steps:
            output.append(f"Steps: {', '.join(execute_steps)}")

    return "\n".join(output)


@mcp.tool()
async def trigger_dbt_job(job_id: int, cause: str = "Triggered via MCP") -> str:
    """
    Trigger a dbt Cloud job run.

    Requires: mcp_analyst, mcp_admin roles

    Args:
        job_id: The ID of the job to trigger
        cause: Optional description of why the job was triggered

    Returns:
        Run details including run ID and status
    """
    if not dbt_config.is_configured:
        return f"""dbt Cloud Job Trigger (Demo Mode):

Job ID: {job_id}
Cause: {cause}

Mock Run Started:
- Run ID: 999888
- Status: Queued
- Trigger: Manual (via MCP)
- Created: 2024-03-15 15:30:00

ℹ️  Configure dbt Cloud to trigger real job runs.
"""

    endpoint = f"accounts/{dbt_config.account_id}/jobs/{job_id}/run/"
    json_data = {"cause": cause}

    data = await make_dbt_request(endpoint, method="POST", json_data=json_data)

    if "error" in data:
        return f"Error: {data['error']}"

    run = data.get("data", {})
    if not run:
        return "Job triggered but no run data returned"

    output = [f"dbt Cloud Job Run Triggered:\n"]
    output.append(f"Run ID: {run.get('id', 'N/A')}")
    output.append(f"Job ID: {run.get('job_id', 'N/A')}")
    output.append(f"Status: {run.get('status_humanized', run.get('status', 'N/A'))}")
    output.append(f"Trigger: {run.get('trigger', {}).get('cause', 'N/A')}")
    output.append(f"Created: {run.get('created_at', 'N/A')}")

    if run.get("href"):
        output.append(f"\nView run: {run.get('href')}")

    return "\n".join(output)


@mcp.tool()
async def get_dbt_run_status(run_id: int) -> str:
    """
    Get the status and details of a dbt Cloud run.

    Requires: mcp_analyst, mcp_admin roles

    Args:
        run_id: The ID of the run to check

    Returns:
        Run status, duration, and test results
    """
    if not dbt_config.is_configured:
        return f"""dbt Cloud Run Status (Demo Mode):

Run ID: {run_id}

Status: Success
Duration: 3m 42s
Started: 2024-03-15 15:30:00
Finished: 2024-03-15 15:33:42

Results:
- Models: 45 passed
- Tests: 127 passed, 2 warnings
- Snapshots: 3 passed

ℹ️  Configure dbt Cloud to check real run status.
"""

    endpoint = f"accounts/{dbt_config.account_id}/runs/{run_id}/"
    data = await make_dbt_request(endpoint)

    if "error" in data:
        return f"Error: {data['error']}"

    run = data.get("data", {})
    if not run:
        return f"Run {run_id} not found"

    output = [f"dbt Cloud Run Status:\n"]
    output.append(f"Run ID: {run.get('id', 'N/A')}")
    output.append(f"Job ID: {run.get('job_id', 'N/A')}")
    output.append(f"Status: {run.get('status_humanized', run.get('status', 'N/A'))}")
    output.append(f"Started: {run.get('started_at', 'N/A')}")

    if run.get("finished_at"):
        output.append(f"Finished: {run.get('finished_at')}")

    if run.get("duration"):
        output.append(f"Duration: {run.get('duration')}")

    # Add run results summary
    run_steps = run.get("run_steps", [])
    if run_steps:
        output.append(f"\nSteps:")
        for step in run_steps:
            step_name = step.get("name", "Unknown")
            step_status = step.get("status_humanized", step.get("status", "N/A"))
            output.append(f"  - {step_name}: {step_status}")

    if run.get("href"):
        output.append(f"\nView run: {run.get('href')}")

    return "\n".join(output)


@mcp.tool()
async def query_dbt_models(project_id: int, search: Optional[str] = None, limit: int = 20) -> str:
    """
    Query dbt models in a project from the Discovery API.

    Requires: mcp_analyst, mcp_admin roles

    Args:
        project_id: The project ID to query models from
        search: Optional search term to filter models
        limit: Maximum number of models to return (default 20)

    Returns:
        List of dbt models with metadata
    """
    if not dbt_config.is_configured:
        return f"""dbt Models (Demo Mode):

Project ID: {project_id}
Search: {search or 'None'}

--- Model 1 ---
Name: stg_patients
Type: staging
Database: analytics
Schema: staging
Description: Staging table for patient demographics

--- Model 2 ---
Name: fct_encounters
Type: fact
Database: analytics
Schema: marts
Description: Fact table for patient encounters

--- Model 3 ---
Name: dim_providers
Type: dimension
Database: analytics
Schema: marts
Description: Dimension table for healthcare providers

ℹ️  Configure dbt Cloud to query real models.
"""

    # Note: The Discovery API requires GraphQL and is more complex
    # For now, we'll use the standard API to list models via metadata
    endpoint = f"accounts/{dbt_config.account_id}/projects/{project_id}/"
    data = await make_dbt_request(endpoint)

    if "error" in data:
        return f"Error: {data['error']}"

    project = data.get("data", {})
    if not project:
        return f"Project {project_id} not found"

    output = [f"dbt Project: {project.get('name', 'N/A')}\n"]
    output.append("ℹ️  Note: Full model metadata requires dbt Cloud Discovery API (GraphQL)")
    output.append(f"Project ID: {project.get('id', 'N/A')}")
    output.append(f"Repository: {project.get('repository', {}).get('remote_url', 'N/A')}")
    output.append(f"\nTo query specific model metadata, use the dbt Cloud web interface or Discovery API.")

    return "\n".join(output)


# ============================================================================
# SNOWFLAKE INTEGRATION
# ============================================================================

# Snowflake configuration
try:
    import snowflake.connector
    from snowflake.connector import DictCursor
    SNOWFLAKE_AVAILABLE = True
except ImportError:
    logger.warning("snowflake-connector-python not available. Snowflake tools will return mock data.")
    SNOWFLAKE_AVAILABLE = False


class SnowflakeConfig:
    """Snowflake configuration"""
    def __init__(self):
        self.account = os.getenv('SNOWFLAKE_ACCOUNT')
        self.user = os.getenv('SNOWFLAKE_USER')
        self.password = os.getenv('SNOWFLAKE_PASSWORD')
        self.warehouse = os.getenv('SNOWFLAKE_WAREHOUSE')
        self.database = os.getenv('SNOWFLAKE_DATABASE')
        self.schema = os.getenv('SNOWFLAKE_SCHEMA', 'PUBLIC')
        self.role = os.getenv('SNOWFLAKE_ROLE')
        self.authenticator = os.getenv('SNOWFLAKE_AUTHENTICATOR')  # e.g., 'externalbrowser' for SSO, 'oauth' for Okta
        self.private_key_path = os.getenv('SNOWFLAKE_PRIVATE_KEY_PATH')
        # OAuth-specific configuration for Okta token passthrough
        self.oauth_enabled = os.getenv('SNOWFLAKE_OAUTH_ENABLED', 'false').lower() == 'true'

    @property
    def is_configured(self) -> bool:
        """Check if Snowflake is properly configured."""
        has_account = bool(self.account)
        # For OAuth mode, we don't need a static user - it comes from the token
        if self.oauth_enabled:
            return has_account and SNOWFLAKE_AVAILABLE
        # For non-OAuth modes, we need user and some form of auth
        has_user = bool(self.user)
        has_auth = bool(
            self.password or
            self.authenticator == 'externalbrowser' or
            self.private_key_path
        )
        return has_account and has_user and has_auth and SNOWFLAKE_AVAILABLE

    @property
    def is_oauth_mode(self) -> bool:
        """Check if running in OAuth passthrough mode."""
        return self.oauth_enabled and SNOWFLAKE_AVAILABLE


# Global Snowflake config
snowflake_config = SnowflakeConfig()

# Thread-local storage for OAuth token (set by tools before calling get_snowflake_connection)
import threading
_snowflake_oauth_token = threading.local()


def set_snowflake_oauth_token(token: str):
    """Set the OAuth token for the current thread/request."""
    _snowflake_oauth_token.value = token


def get_snowflake_oauth_token():
    """Get the OAuth token for the current thread/request."""
    return getattr(_snowflake_oauth_token, 'value', None)


def get_snowflake_connection(oauth_token: str = None):
    """
    Get Snowflake connection with configured authentication.

    Args:
        oauth_token: Optional OAuth access token for Okta SSO authentication.
                    Required when SNOWFLAKE_OAUTH_ENABLED=true.
                    If not provided, will check thread-local storage.

    Returns:
        Snowflake connection object
    """
    # OAuth mode - use the passed token or thread-local token
    if snowflake_config.is_oauth_mode:
        token = oauth_token or get_snowflake_oauth_token()
        if not token:
            raise Exception("OAuth mode enabled but no token provided. Ensure user is authenticated via Okta.")

        conn_params = {
            'account': snowflake_config.account,
            'authenticator': 'oauth',
            'token': token,
            'warehouse': snowflake_config.warehouse,
            'database': snowflake_config.database,
            'schema': snowflake_config.schema,
        }

        if snowflake_config.role:
            conn_params['role'] = snowflake_config.role

        logger.debug(f"Connecting to Snowflake via OAuth (account: {snowflake_config.account})")
        return snowflake.connector.connect(**conn_params)

    # Non-OAuth modes
    if not snowflake_config.is_configured:
        raise Exception("Snowflake not configured. Set SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, and authentication credentials.")

    conn_params = {
        'account': snowflake_config.account,
        'user': snowflake_config.user,
        'warehouse': snowflake_config.warehouse,
        'database': snowflake_config.database,
        'schema': snowflake_config.schema,
    }

    if snowflake_config.role:
        conn_params['role'] = snowflake_config.role

    # Authentication options
    if snowflake_config.authenticator:
        conn_params['authenticator'] = snowflake_config.authenticator
    elif snowflake_config.private_key_path:
        # Key pair authentication
        with open(snowflake_config.private_key_path, 'rb') as key_file:
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives import serialization

            private_key = serialization.load_pem_private_key(
                key_file.read(),
                password=None,
                backend=default_backend()
            )
            conn_params['private_key'] = private_key.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
    elif snowflake_config.password:
        conn_params['password'] = snowflake_config.password

    return snowflake.connector.connect(**conn_params)


def extract_oauth_token_from_context(ctx: Context) -> str:
    """
    Extract OAuth token from FastMCP context.
    
    The token can come from:
    1. The Authorization header (Bearer token)
    2. The validated JWT claims in auth_info
    
    Args:
        ctx: FastMCP Context object
        
    Returns:
        OAuth access token string or None
    """
    if ctx is None:
        return None
    
    # Try to get the raw token from request headers
    # FastMCP stores the original token in the context
    try:
        # Check if there's a request object with headers
        if hasattr(ctx, 'request') and ctx.request:
            auth_header = ctx.request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                return auth_header[7:]  # Remove 'Bearer ' prefix
        
        # Check for token in auth_info (some FastMCP versions store it here)
        if hasattr(ctx, 'auth_info') and ctx.auth_info:
            if isinstance(ctx.auth_info, dict) and 'token' in ctx.auth_info:
                return ctx.auth_info['token']
                
    except Exception as e:
        logger.debug(f"Could not extract OAuth token from context: {e}")
    
    return None


def get_snowflake_connection_with_context(ctx: Context = None):
    """
    Get Snowflake connection, automatically extracting OAuth token from context if in OAuth mode.
    
    Args:
        ctx: Optional FastMCP Context for OAuth token extraction
        
    Returns:
        Snowflake connection object
    """
    if snowflake_config.is_oauth_mode and ctx:
        token = extract_oauth_token_from_context(ctx)
        if token:
            return get_snowflake_connection(oauth_token=token)
    
    return get_snowflake_connection()


@mcp.tool()
async def execute_snowflake_query(query: str, limit: int = 100, ctx: Context = None) -> str:
    """
    Execute a SQL query on Snowflake.

    Requires: mcp_analyst, mcp_admin roles

    Args:
        query: SQL query to execute
        limit: Maximum number of rows to return (default 100)
        ctx: FastMCP context (injected automatically)

    Returns:
        Query results formatted as a table
    """
    if not snowflake_config.is_configured and not snowflake_config.is_oauth_mode:
        return f"""Snowflake Query (Demo Mode):

Query: {query}
Limit: {limit}

Mock Results:
┌────────────┬─────────────┬──────────┐
│ PATIENT_ID │ PROVIDER_NPI│ AMOUNT   │
├────────────┼─────────────┼──────────┤
│ P001       │ 1234567890  │ $1,250.00│
│ P002       │ 1234567891  │ $850.50  │
│ P003       │ 1234567890  │ $2,100.75│
└────────────┴─────────────┴──────────┘

ℹ️  To execute real queries, configure:
   - SNOWFLAKE_ACCOUNT
   - SNOWFLAKE_USER
   - Authentication (password, SSO, or key pair)
"""

    try:
        conn = get_snowflake_connection_with_context(ctx)
        cursor = conn.cursor(DictCursor)

        # Add limit to query if not already present
        query_lower = query.lower()
        if 'limit' not in query_lower:
            query = f"{query.rstrip(';')} LIMIT {limit}"

        cursor.execute(query)
        results = cursor.fetchall()

        if not results:
            return "Query executed successfully. No rows returned."

        # Format results
        output = [f"Query Results ({len(results)} rows):\n"]

        # Get column names
        columns = list(results[0].keys())

        # Simple table formatting
        output.append(" | ".join(columns))
        output.append("-" * (len(" | ".join(columns))))

        for row in results:
            output.append(" | ".join(str(row.get(col, "")) for col in columns))

        cursor.close()
        conn.close()

        return "\n".join(output)

    except Exception as e:
        logger.error(f"Snowflake query error: {e}")
        return f"Error executing query: {str(e)}"


@mcp.tool()
async def list_snowflake_databases(ctx: Context = None) -> str:
    """
    List databases in Snowflake account.

    Requires: mcp_analyst, mcp_admin roles

    Args:
        ctx: FastMCP context (injected automatically)

    Returns:
        List of databases with details
    """
    if not snowflake_config.is_configured and not snowflake_config.is_oauth_mode:
        return """Snowflake Databases (Demo Mode):

--- Database 1 ---
Name: HEALTHCARE_DATA
Owner: SYSADMIN
Created: 2024-01-15
Size: 523 GB

--- Database 2 ---
Name: ANALYTICS_PROD
Owner: SYSADMIN
Created: 2024-02-20
Size: 1.2 TB

--- Database 3 ---
Name: STAGING
Owner: SYSADMIN
Created: 2024-03-01
Size: 89 GB

ℹ️  Configure Snowflake to access real databases.
"""

    try:
        conn = get_snowflake_connection_with_context(ctx)
        cursor = conn.cursor(DictCursor)

        cursor.execute("SHOW DATABASES")
        results = cursor.fetchall()

        output = [f"Found {len(results)} database(s):\n"]

        for i, db in enumerate(results, 1):
            output.append(f"\n--- Database {i} ---")
            output.append(f"Name: {db.get('name', 'N/A')}")
            output.append(f"Owner: {db.get('owner', 'N/A')}")
            output.append(f"Created: {db.get('created_on', 'N/A')}")
            output.append(f"Comment: {db.get('comment', 'N/A')}")

        cursor.close()
        conn.close()

        return "\n".join(output)

    except Exception as e:
        logger.error(f"Snowflake error: {e}")
        return f"Error listing databases: {str(e)}"


@mcp.tool()
async def list_snowflake_schemas(database: Optional[str] = None, ctx: Context = None) -> str:
    """
    List schemas in a Snowflake database.

    Requires: mcp_analyst, mcp_admin roles

    Args:
        database: Database name (uses configured database if not specified)
        ctx: FastMCP context (injected automatically)

    Returns:
        List of schemas
    """
    if not snowflake_config.is_configured and not snowflake_config.is_oauth_mode:
        return f"""Snowflake Schemas (Demo Mode):

Database: {database or 'HEALTHCARE_DATA'}

--- Schema 1 ---
Name: PUBLIC
Owner: SYSADMIN
Tables: 45

--- Schema 2 ---
Name: STAGING
Owner: DATA_ENGINEER
Tables: 23

--- Schema 3 ---
Name: ANALYTICS
Owner: ANALYST_ROLE
Tables: 67

ℹ️  Configure Snowflake to access real schemas.
"""

    try:
        conn = get_snowflake_connection_with_context(ctx)
        cursor = conn.cursor(DictCursor)

        if database:
            cursor.execute(f"SHOW SCHEMAS IN DATABASE {database}")
        else:
            cursor.execute("SHOW SCHEMAS")

        results = cursor.fetchall()

        output = [f"Found {len(results)} schema(s):\n"]

        for i, schema in enumerate(results, 1):
            output.append(f"\n--- Schema {i} ---")
            output.append(f"Name: {schema.get('name', 'N/A')}")
            output.append(f"Database: {schema.get('database_name', 'N/A')}")
            output.append(f"Owner: {schema.get('owner', 'N/A')}")
            output.append(f"Created: {schema.get('created_on', 'N/A')}")

        cursor.close()
        conn.close()

        return "\n".join(output)

    except Exception as e:
        logger.error(f"Snowflake error: {e}")
        return f"Error listing schemas: {str(e)}"


@mcp.tool()
async def list_snowflake_tables(schema: Optional[str] = None, database: Optional[str] = None, ctx: Context = None) -> str:
    """
    List tables in a Snowflake schema.

    Requires: mcp_analyst, mcp_admin roles

    Args:
        schema: Schema name (uses configured schema if not specified)
        database: Database name (uses configured database if not specified)
        ctx: FastMCP context (injected automatically)

    Returns:
        List of tables with row counts
    """
    if not snowflake_config.is_configured and not snowflake_config.is_oauth_mode:
        return f"""Snowflake Tables (Demo Mode):

Database: {database or 'HEALTHCARE_DATA'}
Schema: {schema or 'PUBLIC'}

--- Table 1 ---
Name: PATIENTS
Type: TABLE
Rows: 1,234,567
Size: 45 GB

--- Table 2 ---
Name: ENCOUNTERS
Type: TABLE
Rows: 5,678,901
Size: 123 GB

--- Table 3 ---
Name: PROVIDERS
Type: TABLE
Rows: 45,678
Size: 2.1 GB

ℹ️  Configure Snowflake to access real tables.
"""

    try:
        conn = get_snowflake_connection_with_context(ctx)
        cursor = conn.cursor(DictCursor)

        if database and schema:
            cursor.execute(f"SHOW TABLES IN {database}.{schema}")
        elif schema:
            cursor.execute(f"SHOW TABLES IN SCHEMA {schema}")
        else:
            cursor.execute("SHOW TABLES")

        results = cursor.fetchall()

        output = [f"Found {len(results)} table(s):\n"]

        for i, table in enumerate(results, 1):
            output.append(f"\n--- Table {i} ---")
            output.append(f"Name: {table.get('name', 'N/A')}")
            output.append(f"Database: {table.get('database_name', 'N/A')}")
            output.append(f"Schema: {table.get('schema_name', 'N/A')}")
            output.append(f"Type: {table.get('kind', 'N/A')}")
            output.append(f"Rows: {table.get('rows', 'N/A')}")
            output.append(f"Bytes: {table.get('bytes', 'N/A')}")
            output.append(f"Created: {table.get('created_on', 'N/A')}")

        cursor.close()
        conn.close()

        return "\n".join(output)

    except Exception as e:
        logger.error(f"Snowflake error: {e}")
        return f"Error listing tables: {str(e)}"


@mcp.tool()
async def describe_snowflake_table(table_name: str, schema: Optional[str] = None, database: Optional[str] = None, ctx: Context = None) -> str:
    """
    Describe the structure of a Snowflake table.

    Requires: mcp_analyst, mcp_admin roles

    Args:
        table_name: Name of the table
        schema: Schema name (uses configured schema if not specified)
        database: Database name (uses configured database if not specified)
        ctx: FastMCP context (injected automatically)

    Returns:
        Table structure with column details
    """
    if not snowflake_config.is_configured and not snowflake_config.is_oauth_mode:
        return f"""Table Structure (Demo Mode):

Table: {table_name}
Database: {database or 'HEALTHCARE_DATA'}
Schema: {schema or 'PUBLIC'}

Columns:
┌─────────────────┬──────────┬──────────┬─────────┐
│ Column Name     │ Type     │ Nullable │ Default │
├─────────────────┼──────────┼──────────┼─────────┤
│ PATIENT_ID      │ VARCHAR  │ NO       │ NULL    │
│ FIRST_NAME      │ VARCHAR  │ YES      │ NULL    │
│ LAST_NAME       │ VARCHAR  │ YES      │ NULL    │
│ DATE_OF_BIRTH   │ DATE     │ YES      │ NULL    │
│ CREATED_AT      │ TIMESTAMP│ NO       │ CURRENT │
└─────────────────┴──────────┴──────────┴─────────┘

ℹ️  Configure Snowflake to access real table structures.
"""

    try:
        conn = get_snowflake_connection_with_context(ctx)
        cursor = conn.cursor(DictCursor)

        # Build fully qualified table name
        if database and schema:
            full_table = f"{database}.{schema}.{table_name}"
        elif schema:
            full_table = f"{schema}.{table_name}"
        else:
            full_table = table_name

        cursor.execute(f"DESCRIBE TABLE {full_table}")
        results = cursor.fetchall()

        output = [f"Table Structure: {full_table}\n"]
        output.append(f"Columns ({len(results)}):\n")

        for col in results:
            output.append(f"- {col.get('name', 'N/A')}")
            output.append(f"  Type: {col.get('type', 'N/A')}")
            output.append(f"  Nullable: {col.get('null?', 'N/A')}")
            output.append(f"  Default: {col.get('default', 'N/A')}")
            if col.get('comment'):
                output.append(f"  Comment: {col.get('comment')}")
            output.append("")

        cursor.close()
        conn.close()

        return "\n".join(output)

    except Exception as e:
        logger.error(f"Snowflake error: {e}")
        return f"Error describing table: {str(e)}"


@mcp.tool()
async def list_snowflake_warehouses(ctx: Context = None) -> str:
    """
    List Snowflake warehouses.

    Requires: mcp_analyst, mcp_admin roles

    Args:
        ctx: FastMCP context (injected automatically)

    Returns:
        List of warehouses with status and size
    """
    if not snowflake_config.is_configured and not snowflake_config.is_oauth_mode:
        return """Snowflake Warehouses (Demo Mode):

--- Warehouse 1 ---
Name: ANALYTICS_WH
Size: MEDIUM
State: STARTED
Auto-suspend: 600s

--- Warehouse 2 ---
Name: TRANSFORM_WH
Size: LARGE
State: SUSPENDED
Auto-suspend: 300s

--- Warehouse 3 ---
Name: DEV_WH
Size: X-SMALL
State: STARTED
Auto-suspend: 120s

ℹ️  Configure Snowflake to access real warehouses.
"""

    try:
        conn = get_snowflake_connection_with_context(ctx)
        cursor = conn.cursor(DictCursor)

        cursor.execute("SHOW WAREHOUSES")
        results = cursor.fetchall()

        output = [f"Found {len(results)} warehouse(s):\n"]

        for i, wh in enumerate(results, 1):
            output.append(f"\n--- Warehouse {i} ---")
            output.append(f"Name: {wh.get('name', 'N/A')}")
            output.append(f"Size: {wh.get('size', 'N/A')}")
            output.append(f"State: {wh.get('state', 'N/A')}")
            output.append(f"Type: {wh.get('type', 'N/A')}")
            output.append(f"Auto-suspend: {wh.get('auto_suspend', 'N/A')}s")
            output.append(f"Auto-resume: {wh.get('auto_resume', 'N/A')}")
            output.append(f"Owner: {wh.get('owner', 'N/A')}")

        cursor.close()
        conn.close()

        return "\n".join(output)

    except Exception as e:
        logger.error(f"Snowflake error: {e}")
        return f"Error listing warehouses: {str(e)}"


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

    # dbt Cloud tools - require analyst role or admin
    list_dbt_projects.canAccess = require_role("mcp_analyst", "mcp_admin")
    list_dbt_jobs.canAccess = require_role("mcp_analyst", "mcp_admin")
    trigger_dbt_job.canAccess = require_role("mcp_analyst", "mcp_admin")
    get_dbt_run_status.canAccess = require_role("mcp_analyst", "mcp_admin")
    query_dbt_models.canAccess = require_role("mcp_analyst", "mcp_admin")
    logger.info("   ✓ dbt Cloud tools (list_dbt_projects, list_dbt_jobs, trigger_dbt_job, get_dbt_run_status, query_dbt_models): analyst or admin")

    # Snowflake tools - require analyst role or admin
    execute_snowflake_query.canAccess = require_role("mcp_analyst", "mcp_admin")
    list_snowflake_databases.canAccess = require_role("mcp_analyst", "mcp_admin")
    list_snowflake_schemas.canAccess = require_role("mcp_analyst", "mcp_admin")
    list_snowflake_tables.canAccess = require_role("mcp_analyst", "mcp_admin")
    describe_snowflake_table.canAccess = require_role("mcp_analyst", "mcp_admin")
    list_snowflake_warehouses.canAccess = require_role("mcp_analyst", "mcp_admin")
    logger.info("   ✓ Snowflake tools (execute_snowflake_query, list_snowflake_databases, list_snowflake_schemas, list_snowflake_tables, describe_snowflake_table, list_snowflake_warehouses): analyst or admin")

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
