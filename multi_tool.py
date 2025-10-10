"""
CHG Healthcare Multi-Tool FastMCP Server - Echo & Complete NPPES Data Access

This server provides:
1. Simple echo functionality for testing
2. Full access to all NPPES (National Provider Identifier) data fields
"""

from fastmcp import FastMCP
import httpx
from typing import Optional, List, Dict, Any

# Initialize FastMCP server
mcp = FastMCP("CHG Multi-Tool Server")

# Base URL for NPPES API
NPPES_BASE_URL = "https://npiregistry.cms.hhs.gov/api/"
API_VERSION = "2.1"


# ============================================================================
# ECHO TOOLS
# ============================================================================

@mcp.tool()
def echo_tool(text: str) -> str:
    """Echo the input text back to you - useful for testing"""
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
# NPPES NPI REGISTRY TOOLS - COMPLETE DATA ACCESS
# ============================================================================

def format_provider_full(result: Dict[str, Any]) -> str:
    """Format complete provider information with ALL available fields"""

    output = []

    # Basic header info
    output.append(f"NPI: {result.get('number', 'N/A')}")
    output.append(f"Type: {result.get('enumeration_type', 'N/A')}")
    output.append(f"Last Updated: {result.get('last_updated_epoch', 'N/A')}")
    output.append(f"Created: {result.get('created_epoch', 'N/A')}")
    output.append("")

    # Basic Information
    basic = result.get('basic', {})
    if basic:
        output.append("=== BASIC INFORMATION ===")

        # Handle individual (NPI-1) vs organization (NPI-2)
        if result.get('enumeration_type') == 'NPI-1':
            output.append(f"First Name: {basic.get('first_name', 'N/A')}")
            output.append(f"Middle Name: {basic.get('middle_name', 'N/A')}")
            output.append(f"Last Name: {basic.get('last_name', 'N/A')}")
            output.append(f"Name Prefix: {basic.get('name_prefix', 'N/A')}")
            output.append(f"Name Suffix: {basic.get('name_suffix', 'N/A')}")
            output.append(f"Credential: {basic.get('credential', 'N/A')}")
            output.append(f"Gender: {basic.get('gender', 'N/A')}")
            output.append(f"Sole Proprietor: {basic.get('sole_proprietor', 'N/A')}")
        else:
            output.append(f"Organization Name: {basic.get('organization_name', 'N/A')}")
            output.append(f"Authorized Official First Name: {basic.get('authorized_official_first_name', 'N/A')}")
            output.append(f"Authorized Official Last Name: {basic.get('authorized_official_last_name', 'N/A')}")
            output.append(f"Authorized Official Title: {basic.get('authorized_official_title_or_position', 'N/A')}")
            output.append(f"Authorized Official Phone: {basic.get('authorized_official_telephone_number', 'N/A')}")

        output.append(f"Enumeration Date: {basic.get('enumeration_date', 'N/A')}")
        output.append(f"Last Updated: {basic.get('last_updated', 'N/A')}")
        output.append(f"Status: {basic.get('status', 'N/A')}")
        output.append(f"Certification Date: {basic.get('certification_date', 'N/A')}")
        output.append("")

    # Other Names
    other_names = result.get('other_names', [])
    if other_names:
        output.append("=== OTHER NAMES ===")
        for idx, name in enumerate(other_names, 1):
            output.append(f"\nOther Name #{idx}:")
            output.append(f"  Type: {name.get('type', 'N/A')}")
            output.append(f"  Code: {name.get('code', 'N/A')}")
            if name.get('type') == 'Organization':
                output.append(f"  Name: {name.get('organization_name', 'N/A')}")
            else:
                output.append(f"  First Name: {name.get('first_name', 'N/A')}")
                output.append(f"  Last Name: {name.get('last_name', 'N/A')}")
                output.append(f"  Middle Name: {name.get('middle_name', 'N/A')}")
                output.append(f"  Credential: {name.get('credential', 'N/A')}")
        output.append("")

    # Addresses
    addresses = result.get('addresses', [])
    if addresses:
        output.append("=== ADDRESSES ===")
        for idx, addr in enumerate(addresses, 1):
            purpose = addr.get('address_purpose', 'N/A')
            output.append(f"\nAddress #{idx} ({purpose}):")
            output.append(f"  Address Line 1: {addr.get('address_1', 'N/A')}")
            output.append(f"  Address Line 2: {addr.get('address_2', 'N/A')}")
            output.append(f"  City: {addr.get('city', 'N/A')}")
            output.append(f"  State: {addr.get('state', 'N/A')}")
            output.append(f"  Postal Code: {addr.get('postal_code', 'N/A')}")
            output.append(f"  Country Code: {addr.get('country_code', 'N/A')}")
            output.append(f"  Country Name: {addr.get('country_name', 'N/A')}")
            output.append(f"  Telephone: {addr.get('telephone_number', 'N/A')}")
            output.append(f"  Fax: {addr.get('fax_number', 'N/A')}")
        output.append("")

    # Taxonomies
    taxonomies = result.get('taxonomies', [])
    if taxonomies:
        output.append("=== TAXONOMIES (SPECIALTIES) ===")
        for idx, tax in enumerate(taxonomies, 1):
            output.append(f"\nTaxonomy #{idx}:")
            output.append(f"  Code: {tax.get('code', 'N/A')}")
            output.append(f"  Description: {tax.get('desc', 'N/A')}")
            output.append(f"  Primary: {tax.get('primary', 'N/A')}")
            output.append(f"  State: {tax.get('state', 'N/A')}")
            output.append(f"  License: {tax.get('license', 'N/A')}")
            taxonomy_group = tax.get('taxonomy_group', 'N/A')
            output.append(f"  Taxonomy Group: {taxonomy_group}")
        output.append("")

    # Identifiers (State Licenses, etc.)
    identifiers = result.get('identifiers', [])
    if identifiers:
        output.append("=== IDENTIFIERS ===")
        for idx, ident in enumerate(identifiers, 1):
            output.append(f"\nIdentifier #{idx}:")
            output.append(f"  Code: {ident.get('code', 'N/A')}")
            output.append(f"  Description: {ident.get('desc', 'N/A')}")
            output.append(f"  Identifier: {ident.get('identifier', 'N/A')}")
            output.append(f"  State: {ident.get('state', 'N/A')}")
            output.append(f"  Issuer: {ident.get('issuer', 'N/A')}")
        output.append("")

    # Practice Locations
    practice_locations = result.get('practice_locations', [])
    if practice_locations:
        output.append("=== PRACTICE LOCATIONS ===")
        for idx, loc in enumerate(practice_locations, 1):
            output.append(f"\nPractice Location #{idx}:")
            output.append(f"  Address Line 1: {loc.get('address_1', 'N/A')}")
            output.append(f"  Address Line 2: {loc.get('address_2', 'N/A')}")
            output.append(f"  City: {loc.get('city', 'N/A')}")
            output.append(f"  State: {loc.get('state', 'N/A')}")
            output.append(f"  Postal Code: {loc.get('postal_code', 'N/A')}")
            output.append(f"  Country Code: {loc.get('country_code', 'N/A')}")
            output.append(f"  Telephone: {loc.get('telephone_number', 'N/A')}")
            output.append(f"  Fax: {loc.get('fax_number', 'N/A')}")
        output.append("")

    # Endpoints
    endpoints = result.get('endpoints', [])
    if endpoints:
        output.append("=== ENDPOINTS ===")
        for idx, endpoint in enumerate(endpoints, 1):
            output.append(f"\nEndpoint #{idx}:")
            output.append(f"  Type: {endpoint.get('endpointType', 'N/A')}")
            output.append(f"  Type Description: {endpoint.get('endpointTypeDescription', 'N/A')}")
            output.append(f"  Endpoint: {endpoint.get('endpoint', 'N/A')}")
            output.append(f"  Affiliation: {endpoint.get('affiliation', 'N/A')}")
            output.append(f"  Use: {endpoint.get('use', 'N/A')}")
            output.append(f"  Content Type: {endpoint.get('contentType', 'N/A')}")
            output.append(f"  Description: {endpoint.get('endpointDescription', 'N/A')}")
        output.append("")

    return "\n".join(output)


@mcp.tool()
async def lookup_npi(npi_number: str) -> str:
    """
    Look up a healthcare provider by their NPI number with FULL details.

    Args:
        npi_number: The 10-digit National Provider Identifier (NPI) number

    Returns:
        Complete detailed information about the provider including all fields:
        - Basic information (name, gender, credentials, dates)
        - All addresses (practice and mailing)
        - All taxonomies/specialties
        - State licenses and identifiers
        - Practice locations
        - Electronic endpoints
        - Other names/aliases
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        params = {
            "version": API_VERSION,
            "number": npi_number
        }

        response = await client.get(NPPES_BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()

        if data.get("result_count", 0) == 0:
            return f"No provider found with NPI: {npi_number}"

        result = data["results"][0]
        return format_provider_full(result)


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
    Search for individual healthcare providers (NPI-1) with FULL details.

    Args:
        first_name: Provider's first name
        last_name: Provider's last name
        city: City name
        state: Two-letter state abbreviation (e.g., CA, NY)
        postal_code: 5-digit ZIP code
        limit: Maximum number of results to return (default 10, max 200)

    Returns:
        Complete list of matching providers with ALL available details for each
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        params = {
            "version": API_VERSION,
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

        response = await client.get(NPPES_BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()

        result_count = data.get("result_count", 0)

        if result_count == 0:
            return "No providers found matching the search criteria."

        output = [f"Found {result_count} provider(s):\n"]

        for idx, result in enumerate(data.get("results", []), 1):
            output.append(f"\n{'='*60}")
            output.append(f"--- Provider {idx} ---")
            output.append(f"{'='*60}\n")
            output.append(format_provider_full(result))

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
    Search for healthcare organizations (NPI-2) with FULL details.

    Args:
        organization_name: Name of the healthcare organization
        city: City name
        state: Two-letter state abbreviation (e.g., CA, NY)
        postal_code: 5-digit ZIP code
        limit: Maximum number of results to return (default 10, max 200)

    Returns:
        Complete list of matching organizations with ALL available details
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        params = {
            "version": API_VERSION,
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

        response = await client.get(NPPES_BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()

        result_count = data.get("result_count", 0)

        if result_count == 0:
            return "No organizations found matching the search criteria."

        output = [f"Found {result_count} organization(s):\n"]

        for idx, result in enumerate(data.get("results", []), 1):
            output.append(f"\n{'='*60}")
            output.append(f"--- Organization {idx} ---")
            output.append(f"{'='*60}\n")
            output.append(format_provider_full(result))

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
    Perform an advanced search with multiple criteria and return FULL details.

    Args:
        taxonomy_description: Provider specialty or taxonomy description
            (e.g., "Family Medicine", "Cardiology", "Nurse Practitioner")
        first_name: Provider's first name (for individuals)
        last_name: Provider's last name (for individuals)
        organization_name: Organization name (for organizations)
        city: City name
        state: Two-letter state abbreviation (e.g., CA, NY)
        postal_code: 5-digit ZIP code
        country_code: Two-letter country code (default US)
        limit: Maximum number of results to return (default 10, max 200)

    Returns:
        Complete list of matching providers/organizations with ALL fields
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        params = {
            "version": API_VERSION,
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

        response = await client.get(NPPES_BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()

        result_count = data.get("result_count", 0)

        if result_count == 0:
            return "No providers/organizations found matching the search criteria."

        output = [f"Found {result_count} result(s):\n"]

        for idx, result in enumerate(data.get("results", []), 1):
            output.append(f"\n{'='*60}")
            output.append(f"--- Result {idx} ---")
            output.append(f"{'='*60}\n")
            output.append(format_provider_full(result))

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
    """
    Resource showing example provider searches.
    """
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
    """
    Resource showing example organization searches.
    """
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


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
