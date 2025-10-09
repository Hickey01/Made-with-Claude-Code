"""
NPPES NPI Registry FastMCP Server

This server provides access to the National Plan and Provider Enumeration System (NPPES)
NPI Registry API, allowing users to search and retrieve healthcare provider information.
"""

from fastmcp import FastMCP
import httpx
from typing import Optional, Dict, Any, List

# Create server
mcp = FastMCP("NPPES NPI Registry")

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
    mcp.run()
