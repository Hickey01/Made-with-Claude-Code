# Snowflake MCP Integration Guide

This guide shows how to use the official **Snowflake MCP Server** from Snowflake Labs alongside the CHG Healthcare Combined Server.

## Overview

The [Snowflake MCP Server](https://github.com/Snowflake-Labs/mcp) provides comprehensive access to Snowflake's data platform, including:

- **Cortex Search** - Query unstructured data for RAG applications
- **Cortex Analyst** - Query structured data with semantic modeling
- **Cortex Agent** - Agentic orchestration across data types
- **Object Management** - Create, drop, and manage Snowflake objects
- **SQL Execution** - Execute LLM-generated SQL with permission controls
- **Semantic Views** - Discover and query semantic views

## Architecture

Both servers run independently and can be used together:

```
┌─────────────────────────────────────────┐
│  Claude Desktop / MCP Client            │
└─────────────────┬───────────────────────┘
                  │
        ┌─────────┴──────────┐
        │                    │
┌───────▼──────────┐  ┌──────▼────────────┐
│ CHG Combined     │  │ Snowflake MCP     │
│ Server           │  │ Server            │
│                  │  │                   │
│ - Echo           │  │ - Cortex Search   │
│ - NPPES          │  │ - Cortex Analyst  │
│ - dbt Cloud      │  │ - SQL Execution   │
│                  │  │ - Object Mgmt     │
│ + Okta RBAC      │  │                   │
└──────────────────┘  └───────────────────┘
```

## Installation

### 1. Install Snowflake MCP

```bash
# Using pip
pip install snowflake-mcp

# Or using uv (recommended by Snowflake)
uv pip install snowflake-mcp
```

### 2. Install Snowflake Python Connector

The Snowflake MCP requires the Snowflake connector:

```bash
pip install snowflake-connector-python
```

## Configuration

### Authentication Options

The Snowflake MCP supports all Snowflake authentication methods:

#### Option 1: Username/Password (Development)

```bash
export SNOWFLAKE_ACCOUNT="your_account"
export SNOWFLAKE_USER="your_username"
export SNOWFLAKE_PASSWORD="your_password"
export SNOWFLAKE_WAREHOUSE="your_warehouse"
export SNOWFLAKE_DATABASE="your_database"
export SNOWFLAKE_SCHEMA="your_schema"
export SNOWFLAKE_ROLE="your_role"
```

#### Option 2: Key Pair Authentication (Recommended)

```bash
# Generate key pair (if not already done)
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out rsa_key.p8 -nocrypt
openssl rsa -in rsa_key.p8 -pubout -out rsa_key.pub

# Configure Snowflake to use your public key
# In Snowflake: ALTER USER <username> SET RSA_PUBLIC_KEY='<public_key>';

# Set environment variables
export SNOWFLAKE_ACCOUNT="your_account"
export SNOWFLAKE_USER="your_username"
export SNOWFLAKE_PRIVATE_KEY_PATH="/path/to/rsa_key.p8"
export SNOWFLAKE_WAREHOUSE="your_warehouse"
export SNOWFLAKE_DATABASE="your_database"
export SNOWFLAKE_SCHEMA="your_schema"
export SNOWFLAKE_ROLE="your_role"
```

#### Option 3: OAuth / SSO (Enterprise)

For Okta SSO integration with Snowflake:

```bash
export SNOWFLAKE_ACCOUNT="your_account"
export SNOWFLAKE_AUTHENTICATOR="oauth"
export SNOWFLAKE_TOKEN="<okta_access_token>"
export SNOWFLAKE_WAREHOUSE="your_warehouse"
export SNOWFLAKE_DATABASE="your_database"
export SNOWFLAKE_SCHEMA="your_schema"
export SNOWFLAKE_ROLE="your_role"
```

**For Okta SSO (External Browser):**

```bash
export SNOWFLAKE_ACCOUNT="your_account"
export SNOWFLAKE_AUTHENTICATOR="externalbrowser"
export SNOWFLAKE_USER="your_username"
export SNOWFLAKE_WAREHOUSE="your_warehouse"
export SNOWFLAKE_DATABASE="your_database"
export SNOWFLAKE_SCHEMA="your_schema"
export SNOWFLAKE_ROLE="your_role"
```

### CHG Healthcare Configuration

For CHG Healthcare with Okta integration:

```bash
# Snowflake Connection
export SNOWFLAKE_ACCOUNT="chghealthcare"
export SNOWFLAKE_AUTHENTICATOR="externalbrowser"  # Okta SSO
export SNOWFLAKE_USER="your.email@chghealthcare.com"
export SNOWFLAKE_WAREHOUSE="ANALYTICS_WH"
export SNOWFLAKE_DATABASE="HEALTHCARE_DATA"
export SNOWFLAKE_SCHEMA="PUBLIC"
export SNOWFLAKE_ROLE="ANALYST_ROLE"
```

## Running the Snowflake MCP Server

### Standalone Mode

```bash
# Run with environment variables
snowflake-mcp

# Or with command-line arguments
snowflake-mcp \
  --account your_account \
  --user your_username \
  --warehouse your_warehouse \
  --database your_database \
  --schema your_schema \
  --role your_role
```

### With Claude Desktop

Add to your Claude Desktop configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "chg-combined": {
      "command": "python",
      "args": ["/path/to/Made-with-Claude-Code/combined_server.py"],
      "env": {
        "OKTA_ISSUER": "https://chghealthcare.okta.com/oauth2/default",
        "OKTA_AUDIENCE": "api://mcp-server",
        "OKTA_CLIENT_ID": "your_okta_client_id"
      }
    },
    "snowflake": {
      "command": "snowflake-mcp",
      "env": {
        "SNOWFLAKE_ACCOUNT": "chghealthcare",
        "SNOWFLAKE_AUTHENTICATOR": "externalbrowser",
        "SNOWFLAKE_USER": "your.email@chghealthcare.com",
        "SNOWFLAKE_WAREHOUSE": "ANALYTICS_WH",
        "SNOWFLAKE_DATABASE": "HEALTHCARE_DATA",
        "SNOWFLAKE_SCHEMA": "PUBLIC",
        "SNOWFLAKE_ROLE": "ANALYST_ROLE"
      }
    }
  }
}
```

## Cortex AI Features

### Cortex Search

Query unstructured data for RAG applications:

```python
# The Snowflake MCP provides tools for:
# - Creating Cortex Search services
# - Querying search services
# - Managing search indexes
```

### Cortex Analyst

Query structured data with natural language:

```python
# Use semantic models to:
# - Ask business questions in natural language
# - Get SQL-backed answers automatically
# - Leverage semantic understanding of your data
```

### Cortex Agent

Orchestrate complex data workflows:

```python
# Agentic capabilities include:
# - Multi-step data retrieval
# - Cross-database queries
# - Intelligent query planning
```

## Security & RBAC

### Snowflake-Level Security

The Snowflake MCP respects all Snowflake RBAC settings:

- **Role-Based Access** - Uses the specified Snowflake role
- **Object Permissions** - Honors table, schema, and database grants
- **Row-Level Security** - Applies row access policies
- **Column Masking** - Respects column masking policies

### Integration with Okta RBAC

While the Snowflake MCP uses Snowflake's native RBAC, you can layer additional access control:

1. **Okta Groups** → Determines if user can access Snowflake MCP
2. **Snowflake Roles** → Determines what the user can do in Snowflake
3. **CHG Combined Server** → Separate RBAC for NPPES and dbt Cloud

### Example Access Control Flow

```
User authenticates with Okta
    ↓
Okta group: "mcp_analyst"
    ↓
    ├─→ CHG Combined Server: Can access dbt Cloud tools
    └─→ Snowflake MCP: Authenticates to Snowflake with assigned role
            ↓
        Snowflake RBAC determines data access
```

## Best Practices

### 1. Use Service Accounts for Automation

For automated workflows, use key pair authentication with a dedicated service account:

```bash
# Service account configuration
export SNOWFLAKE_USER="svc_mcp_server"
export SNOWFLAKE_PRIVATE_KEY_PATH="/secure/path/to/key.p8"
export SNOWFLAKE_ROLE="MCP_SERVICE_ROLE"
```

### 2. Separate Roles for Different Access Levels

Define Snowflake roles that align with your use cases:

```sql
-- Read-only analyst role
CREATE ROLE MCP_ANALYST_ROLE;
GRANT USAGE ON WAREHOUSE ANALYTICS_WH TO ROLE MCP_ANALYST_ROLE;
GRANT USAGE ON DATABASE HEALTHCARE_DATA TO ROLE MCP_ANALYST_ROLE;
GRANT SELECT ON ALL TABLES IN SCHEMA HEALTHCARE_DATA.PUBLIC TO ROLE MCP_ANALYST_ROLE;

-- Data engineer role with write access
CREATE ROLE MCP_ENGINEER_ROLE;
GRANT USAGE ON WAREHOUSE TRANSFORM_WH TO ROLE MCP_ENGINEER_ROLE;
GRANT CREATE TABLE, CREATE VIEW ON SCHEMA HEALTHCARE_DATA.STAGING TO ROLE MCP_ENGINEER_ROLE;
```

### 3. Use Warehouses Appropriately

Configure different warehouses for different workloads:

```bash
# For development/testing
export SNOWFLAKE_WAREHOUSE="DEV_WH"  # X-Small warehouse

# For production analytics
export SNOWFLAKE_WAREHOUSE="ANALYTICS_WH"  # Medium warehouse

# For heavy transformations
export SNOWFLAKE_WAREHOUSE="TRANSFORM_WH"  # Large warehouse
```

### 4. Enable Query Tagging

Add query tags for better monitoring:

```python
# The Snowflake MCP automatically tags queries with:
# - Source: "mcp_server"
# - Tool: specific tool name
# - Timestamp: query execution time
```

## Example Workflows

### Workflow 1: Healthcare Analytics Pipeline

1. **Use dbt Cloud** (CHG Combined Server) to run transformations
2. **Query results** in Snowflake (Snowflake MCP)
3. **Look up providers** in NPPES (CHG Combined Server)

### Workflow 2: RAG Application

1. **Index healthcare documents** in Snowflake Cortex Search
2. **Query unstructured data** for relevant context
3. **Combine with structured data** from Snowflake tables
4. **Enrich with provider data** from NPPES

### Workflow 3: Natural Language Analytics

1. **Create semantic model** in Snowflake
2. **Ask business questions** via Cortex Analyst
3. **Trigger dbt jobs** if data needs refresh
4. **Monitor job status** via dbt Cloud MCP tools

## Troubleshooting

### Connection Issues

```bash
# Test Snowflake connection
python -c "import snowflake.connector;
conn = snowflake.connector.connect(
    account='your_account',
    user='your_user',
    authenticator='externalbrowser'
)"
```

### Authentication Errors

- **External Browser SSO**: Ensure browser popups are allowed
- **OAuth Token**: Verify token hasn't expired
- **Key Pair**: Check private key format and permissions

### Permission Errors

```sql
-- Check current role and grants
SELECT CURRENT_ROLE();
SHOW GRANTS TO ROLE YOUR_ROLE;

-- Check warehouse access
SHOW GRANTS ON WAREHOUSE YOUR_WAREHOUSE;
```

## Additional Resources

- [Snowflake MCP GitHub Repository](https://github.com/Snowflake-Labs/mcp)
- [Snowflake Cortex Documentation](https://docs.snowflake.com/en/user-guide/snowflake-cortex)
- [Snowflake Authentication Guide](https://docs.snowflake.com/en/user-guide/admin-security-fed-auth-overview)
- [Snowflake RBAC Best Practices](https://docs.snowflake.com/en/user-guide/security-access-control-considerations)

## Support

For issues with:
- **Snowflake MCP Server**: [Open an issue on GitHub](https://github.com/Snowflake-Labs/mcp/issues)
- **CHG Combined Server**: Contact your IT team or open an issue in this repository
- **Snowflake Platform**: [Snowflake Support Portal](https://community.snowflake.com/)
