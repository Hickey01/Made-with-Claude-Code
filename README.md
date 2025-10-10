# Made with Claude Code

A collection of FastMCP servers built with the help of Claude Code, demonstrating AI-assisted development of MCP (Model Context Protocol) tools.

## What's Inside

This repository contains FastMCP servers for echo testing and comprehensive healthcare provider data access:

### 1. Echo Server (`echo.py`)
A simple demonstration server that showcases the basic capabilities of FastMCP:
- **Echo Tool**: Returns any text you send to it
- **Static Resource**: Provides a static "Echo!" message at `echo://static`
- **Template Resource**: Dynamic echoing using URL templates `echo://{text}`
- **Echo Prompt**: A basic prompt that returns your input text

Perfect for testing MCP integrations and understanding the FastMCP framework.

### 2. Multi-Tool Server (`multi_tool.py`) ⭐ **RECOMMENDED**
A comprehensive healthcare provider lookup system with **COMPLETE DATA ACCESS** to all NPPES fields. This server combines echo functionality with full National Plan and Provider Enumeration System (NPPES) NPI Registry API access:

#### Echo Tools
- `echo_tool(text)` - Simple echo for testing
- Echo resources at `echo://static` and `echo://{text}`
- Echo prompt support

#### NPPES Tools with COMPLETE Data Access
- `lookup_npi(npi_number)` - Look up a provider by their 10-digit NPI number
- `search_providers()` - Search for individual healthcare providers (NPI-1) by name and location
- `search_organizations()` - Search for healthcare organizations (NPI-2)
- `advanced_search()` - Multi-criteria search with taxonomy/specialty filtering

**All tools return COMPLETE provider information including:**
- ✅ Basic Information (names, credentials, gender, enumeration dates)
- ✅ All Addresses (practice locations, mailing addresses, phone/fax)
- ✅ All Taxonomies/Specialties (codes, descriptions, state licenses)
- ✅ All Identifiers (state licenses, DEA numbers, etc.)
- ✅ Practice Locations (complete location details)
- ✅ Electronic Endpoints (FHIR, Direct messaging, etc.)
- ✅ Other Names/Aliases (DBAs, former names)

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

**Multi-Tool Server (Recommended):**
```bash
fastmcp run multi_tool.py
```

**Simple Echo Server:**
```bash
fastmcp run echo.py
```

**Legacy NPPES Server:**
```bash
fastmcp run nppes_server.py
```

**Legacy Combined Server:**
```bash
fastmcp run combined_server.py
```

### Usage Examples

#### Multi-Tool Server Examples
```python
# Test echo functionality
echo_tool("Hello, FastMCP!")
# Returns: "Hello, FastMCP!"

# Look up a specific NPI with COMPLETE details
lookup_npi("1234567890")
# Returns: ALL fields including addresses, taxonomies, identifiers, endpoints, etc.

# Search for providers with full data
search_providers(last_name="Smith", state="CA", limit=5)
# Returns: Complete information for each matching provider

# Search for organizations with full data
search_organizations(organization_name="Mayo Clinic", state="MN")
# Returns: Complete organization details including all locations and endpoints

# Advanced search with specialty - full details returned
advanced_search(taxonomy_description="Cardiology", state="NY", limit=10)
# Returns: Comprehensive data for all matching cardiologists
```

## Deployment

All servers are ready for deployment to FastMCP Cloud:

### Quick Deployment Steps
1. Push this repository to GitHub
2. Create a [FastMCP Cloud account](http://fastmcp.cloud/signup)
3. Connect your GitHub account
4. Select this repository
5. Choose which server to deploy (recommended: `multi_tool.py`)

### GitHub Setup
```bash
# Initialize git repository (if not already done)
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit: Multi-tool server with complete NPPES data access"

# Add your GitHub remote
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git

# Push to GitHub
git push -u origin main
```

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
