# Made with Claude Code

A collection of FastMCP servers built with the help of Claude Code, demonstrating AI-assisted development of MCP (Model Context Protocol) tools.

## What's Inside

This repository contains a combined FastMCP server for echo testing, healthcare provider data access, and dbt Cloud integration:

### Combined Server (`combined_server.py`) ⭐ **MAIN SERVER**
A comprehensive server that combines echo functionality, National Plan and Provider Enumeration System (NPPES) NPI Registry API access, and dbt Cloud integration:

#### Echo Tools
- `echo_tool(text)` - Simple echo for testing
- Echo resources at `echo://static` and `echo://{text}`
- Echo prompt support

#### NPPES Tools
- `lookup_npi(npi_number)` - Look up a provider by their 10-digit NPI number
- `search_providers()` - Search for individual healthcare providers (NPI-1) by name and location
- `search_organizations()` - Search for healthcare organizations (NPI-2)
- `advanced_search()` - Multi-criteria search with taxonomy/specialty filtering

#### dbt Cloud Tools
- `list_dbt_projects(limit)` - List dbt Cloud projects in your account
- `list_dbt_jobs(project_id, limit)` - List dbt Cloud jobs with schedules
- `trigger_dbt_job(job_id, cause)` - Trigger a dbt Cloud job run
- `get_dbt_run_status(run_id)` - Get status and results of a dbt Cloud run
- `query_dbt_models(project_id, search, limit)` - Query dbt models metadata

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

# List dbt Cloud projects
list_dbt_projects(limit=10)
# Returns: List of dbt Cloud projects

# Trigger a dbt Cloud job
trigger_dbt_job(job_id=12345, cause="Manual trigger from MCP")
# Returns: Run ID and status

# Check dbt Cloud run status
get_dbt_run_status(run_id=67890)
# Returns: Run status, duration, and test results
```

## Deployment

This server is ready for deployment to FastMCP Cloud:

### Quick Deployment Steps
1. Create a [FastMCP Cloud account](http://fastmcp.cloud/signup)
2. Connect your GitHub account
3. Select this repository: `Hickey01/Made-with-Claude-Code`
4. Set entry point to: `combined_server.py` or `combined_server:mcp`
5. Deploy!

## Security & Authentication

This server supports **Okta OAuth 2.0 authentication** with role-based access control (RBAC).

### Authentication Features
- ✅ JWT token validation
- ✅ Role-Based Access Control (RBAC)
- ✅ Secure tool access management
- ✅ Development mode (no auth) for local testing

### Quick Start (Development Mode)

To run without authentication (development only):
```bash
python combined_server.py
```

### Production Setup with Okta

For production deployment with authentication:

1. **Configure Okta** - See [OKTA_SETUP.md](OKTA_SETUP.md) for detailed instructions
2. **Set environment variables**:
```bash
cp .env.example .env
# Edit .env with your Okta credentials
```

3. **Run with authentication**:
```bash
python combined_server.py
```

### Role Definitions

- **mcp_viewer**: Read-only access to public data (NPPES search and lookup)
- **mcp_analyst**: Data analyst with advanced search and dbt Cloud access
- **mcp_clinician**: Healthcare provider access with advanced search
- **mcp_admin**: Full administrative access to all tools

See [OKTA_SETUP.md](OKTA_SETUP.md) for complete setup instructions.

### dbt Cloud Configuration

To enable dbt Cloud integration, add these environment variables to your `.env` file:

```bash
# dbt Cloud Configuration
DBT_CLOUD_ACCOUNT_ID=your_account_id
DBT_CLOUD_SERVICE_TOKEN=your_service_token

# Optional: OAuth configuration for user-level authentication
DBT_CLOUD_OAUTH_CLIENT_ID=your_oauth_client_id
DBT_CLOUD_OAUTH_CLIENT_SECRET=your_oauth_client_secret
```

**Authentication Options:**
1. **Service Token** - Use a dbt Cloud service account token for all API requests
2. **OAuth** - Enable OAuth 2.0 for user-level authentication (integrates with Okta SSO)

The server will work in demo mode if dbt Cloud is not configured, returning mock data for testing.

## Dependencies

- `fastmcp>=0.1.0` - The FastMCP framework
- `httpx>=0.27.0` - Async HTTP client for API requests (NPPES servers and dbt Cloud)
- `PyJWT>=2.8.0` - JWT token validation
- `cryptography>=41.0.0` - Cryptographic operations
- `cachetools>=5.3.0` - Token caching
- `python-dotenv>=1.0.0` - Environment variable management

## About This Project

This project was created with assistance from **Claude Code**, an AI-powered development assistant. It demonstrates:
- Rapid prototyping of MCP servers
- Integration with external APIs
- Best practices for FastMCP development
- Complete tool, resource, and prompt implementations

## Snowflake Integration

This repository uses the **official Snowflake MCP Server** from Snowflake Labs for Snowflake data platform access.

The Snowflake MCP provides:
- **Cortex Search** - Query unstructured data for RAG applications
- **Cortex Analyst** - Natural language queries on structured data
- **Cortex Agent** - Agentic orchestration across data types
- **SQL Execution** - Execute queries with permission controls
- **Object Management** - Create and manage Snowflake objects

### Quick Start

```bash
# Install Snowflake MCP
pip install snowflake-mcp snowflake-connector-python

# Run alongside this server
snowflake-mcp --account your_account --user your_user --warehouse your_warehouse
```

See [SNOWFLAKE_MCP_SETUP.md](SNOWFLAKE_MCP_SETUP.md) for detailed configuration, Okta SSO integration, and usage examples.

## Learn More

- [FastMCP Documentation](https://gofastmcp.com/)
- [MCP Protocol](https://modelcontextprotocol.io/)
- [NPPES NPI Registry](https://npiregistry.cms.hhs.gov/)
- [Snowflake MCP Server](https://github.com/Snowflake-Labs/mcp)
- [dbt Cloud API](https://docs.getdbt.com/dbt-cloud/api-v2)
- [Claude Code](https://claude.com/claude-code)

## License

Feel free to use and modify these servers for your own projects!

---

*Built with Claude Code - AI-assisted development at its best*
