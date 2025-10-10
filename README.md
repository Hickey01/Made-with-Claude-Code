# Made with Claude Code

A collection of FastMCP servers built with the help of Claude Code, demonstrating AI-assisted development of MCP (Model Context Protocol) tools.

## What's Inside

This repository contains a combined FastMCP server for echo testing and comprehensive healthcare provider data access:

### Combined Server (`combined_server.py`) ⭐ **MAIN SERVER**
A comprehensive server that combines echo functionality with full National Plan and Provider Enumeration System (NPPES) NPI Registry API access:

#### Echo Tools
- `echo_tool(text)` - Simple echo for testing
- Echo resources at `echo://static` and `echo://{text}`
- Echo prompt support

#### NPPES Tools
- `lookup_npi(npi_number)` - Look up a provider by their 10-digit NPI number
- `search_providers()` - Search for individual healthcare providers (NPI-1) by name and location
- `search_organizations()` - Search for healthcare organizations (NPI-2)
- `advanced_search()` - Multi-criteria search with taxonomy/specialty filtering

**Provider information includes:**
- Basic Information (names, credentials, enumeration dates)
- Addresses (practice locations, mailing addresses)
- Taxonomies/Specialties (primary specialty and descriptions)
- Contact information (phone/fax)

#### Resources
- `npi://{npi_number}` - Direct access to provider information
- `npi://search/providers` - Documentation for provider searches
- `npi://search/organizations` - Documentation for organization searches

#### Prompts
- `find_provider_prompt(criteria)` - Generate search prompts for finding providers
- `explain_npi_prompt(npi_number)` - Generate explanation prompts for NPI lookups

## Getting Started

### Installation

1. Clone this repository:
```bash
git clone https://github.com/YOUR_USERNAME/Made-with-Claude-Code.git
cd Made-with-Claude-Code
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

### Running the Server

```bash
fastmcp run combined_server.py
```

### Usage Examples

```python
# Test echo functionality
echo_tool("Hello, FastMCP!")
# Returns: "Hello, FastMCP!"

# Look up a specific NPI
lookup_npi("1234567890")
# Returns: Provider details including name, address, specialty

# Search for providers
search_providers(last_name="Smith", state="CA", limit=5)
# Returns: List of matching providers

# Search for organizations
search_organizations(organization_name="Mayo Clinic", state="MN")
# Returns: Organization details

# Advanced search with specialty
advanced_search(taxonomy_description="Cardiology", state="NY", limit=10)
# Returns: Matching cardiologists in New York
```

## Deployment

This server is ready for deployment to FastMCP Cloud:

### Quick Deployment Steps
1. Create a [FastMCP Cloud account](http://fastmcp.cloud/signup)
2. Connect your GitHub account
3. Select this repository: `Hickey01/Made-with-Claude-Code`
4. Set entry point to: `combined_server.py` or `combined_server:mcp`
5. Deploy!

## Dependencies

- `fastmcp>=0.1.0` - The FastMCP framework
- `httpx>=0.27.0` - Async HTTP client for API requests (NPPES servers)

## About This Project

This project was created with assistance from **Claude Code**, an AI-powered development assistant. It demonstrates:
- Rapid prototyping of MCP servers
- Integration with external APIs
- Best practices for FastMCP development
- Complete tool, resource, and prompt implementations

## Learn More

- [FastMCP Documentation](https://gofastmcp.com/)
- [MCP Protocol](https://modelcontextprotocol.io/)
- [NPPES NPI Registry](https://npiregistry.cms.hhs.gov/)
- [Claude Code](https://claude.com/claude-code)

## License

Feel free to use and modify these servers for your own projects!

---

*Built with Claude Code - AI-assisted development at its best*
