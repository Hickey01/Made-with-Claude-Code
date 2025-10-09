# Made with Claude Code

A collection of FastMCP servers built with the help of Claude Code, demonstrating AI-assisted development of MCP (Model Context Protocol) tools.

## What's Inside

This repository contains two fully-functional FastMCP servers:

### 1. Echo Server (`echo.py`)
A simple demonstration server that showcases the basic capabilities of FastMCP:
- **Echo Tool**: Returns any text you send to it
- **Static Resource**: Provides a static "Echo!" message at `echo://static`
- **Template Resource**: Dynamic echoing using URL templates `echo://{text}`
- **Echo Prompt**: A basic prompt that returns your input text

Perfect for testing MCP integrations and understanding the FastMCP framework.

### 2. NPPES NPI Registry Server (`nppes_server.py`)
A comprehensive healthcare provider lookup system that interfaces with the National Plan and Provider Enumeration System (NPPES) NPI Registry API:

#### Tools
- `lookup_npi(npi_number)` - Look up a provider by their 10-digit NPI number
- `search_providers()` - Search for individual healthcare providers (NPI-1) by name and location
- `search_organizations()` - Search for healthcare organizations (NPI-2)
- `advanced_search()` - Multi-criteria search with taxonomy/specialty filtering

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

### Running the Servers

**Echo Server:**
```bash
fastmcp run echo.py
```

**NPPES NPI Registry Server:**
```bash
fastmcp run nppes_server.py
```

### Usage Examples

#### Echo Server
```python
# Use the echo tool
echo_tool("Hello, FastMCP!")
# Returns: "Hello, FastMCP!"
```

#### NPPES Server
```python
# Look up a specific NPI
lookup_npi("1234567890")

# Search for providers
search_providers(last_name="Smith", state="CA", limit=5)

# Search for organizations
search_organizations(organization_name="Mayo Clinic", state="MN")

# Advanced search with specialty
advanced_search(taxonomy_description="Cardiology", state="NY", limit=10)
```

## Deployment

Both servers are ready for deployment to FastMCP Cloud:

1. Create a [FastMCP Cloud account](http://fastmcp.cloud/signup)
2. Connect your GitHub account
3. Select this repository
4. Choose which server to deploy (`echo.py` or `nppes_server.py`)

## Dependencies

- `fastmcp` - The FastMCP framework
- `httpx` - Async HTTP client for API requests (NPPES server)
- `snowflake-connector-python` - Snowflake connectivity (if needed)

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
