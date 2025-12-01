# Snowflake External OAuth with Okta Setup Guide

This guide explains how to configure Snowflake External OAuth integration with Okta, enabling users to access Snowflake using their Okta SSO credentials through the MCP server.

## Overview

With this setup:
- Users authenticate to the MCP server using their Okta credentials
- The MCP server passes the user's Okta token to Snowflake
- Snowflake validates the token and grants access based on the user's identity
- Full audit trail shows which user executed each query

```
User → Okta Login → MCP Server → Snowflake (OAuth)
         ↓              ↓              ↓
    Get Token    Validate Token   Execute Query
                                  (as user identity)
```

## Prerequisites

- Okta admin access (to configure OAuth application)
- Snowflake ACCOUNTADMIN role (to create security integration)
- MCP server with Okta authentication already configured

## Step 1: Configure Okta Authorization Server

### 1.1 Create or Use Existing Authorization Server

1. Log in to Okta Admin Console
2. Navigate to **Security → API → Authorization Servers**
3. Either use your existing MCP authorization server or create a new one for Snowflake

### 1.2 Add Snowflake Audience

1. Select your authorization server
2. Go to **Settings** tab
3. Note the **Issuer URI** (e.g., `https://chghealthcare.okta.com/oauth2/aus1234567`)
4. Add Snowflake audience if needed (can be same as MCP audience)

### 1.3 Create Snowflake Scopes (Optional)

1. Click **Scopes** tab
2. Add scope: `snowflake:session` (optional, for additional security)

### 1.4 Ensure Groups Claim is Configured

1. Click **Claims** tab
2. Verify `groups` claim exists and is included in Access Token
3. If not, add claim:
   - Name: `groups`
   - Include in: Access Token
   - Value type: Expression
   - Value: `getFilteredGroups(app.profile.groups, ".*", 100)` or filter for specific groups

## Step 2: Configure Snowflake Security Integration

### 2.1 Get Okta JWKS URL

Your JWKS URL follows this pattern:
```
https://{your-okta-domain}/oauth2/{authServerId}/v1/keys
```

Example: `https://chghealthcare.okta.com/oauth2/default/v1/keys`

### 2.2 Create External OAuth Integration in Snowflake

Run this SQL as ACCOUNTADMIN:

```sql
-- Create the External OAuth Security Integration
CREATE OR REPLACE SECURITY INTEGRATION okta_external_oauth
    TYPE = EXTERNAL_OAUTH
    ENABLED = TRUE
    EXTERNAL_OAUTH_TYPE = OKTA
    EXTERNAL_OAUTH_ISSUER = 'https://chghealthcare.okta.com/oauth2/default'
    EXTERNAL_OAUTH_JWS_KEYS_URL = 'https://chghealthcare.okta.com/oauth2/default/v1/keys'
    EXTERNAL_OAUTH_AUDIENCE_LIST = ('api://snowflake', 'api://mcp-server')
    EXTERNAL_OAUTH_TOKEN_USER_MAPPING_CLAIM = 'sub'
    EXTERNAL_OAUTH_SNOWFLAKE_USER_MAPPING_ATTRIBUTE = 'login_name'
    EXTERNAL_OAUTH_ANY_ROLE_MODE = 'ENABLE';

-- Verify the integration was created
DESCRIBE SECURITY INTEGRATION okta_external_oauth;
```

### 2.3 Understanding the Parameters

| Parameter | Description | Example Value |
|-----------|-------------|---------------|
| `EXTERNAL_OAUTH_ISSUER` | Your Okta authorization server URL | `https://chghealthcare.okta.com/oauth2/default` |
| `EXTERNAL_OAUTH_JWS_KEYS_URL` | JWKS endpoint for token validation | `{issuer}/v1/keys` |
| `EXTERNAL_OAUTH_AUDIENCE_LIST` | Valid audience values in tokens | `('api://snowflake')` |
| `EXTERNAL_OAUTH_TOKEN_USER_MAPPING_CLAIM` | JWT claim containing username | `sub` (email) or `preferred_username` |
| `EXTERNAL_OAUTH_SNOWFLAKE_USER_MAPPING_ATTRIBUTE` | Snowflake user attribute to match | `login_name` or `email_address` |

### 2.4 Configure User Mapping

Ensure Snowflake users exist with matching identities:

```sql
-- Option A: Create users with login_name matching Okta sub claim
CREATE USER john_doe
    LOGIN_NAME = 'john.doe@chghealthcare.com'
    EMAIL = 'john.doe@chghealthcare.com'
    DEFAULT_ROLE = 'ANALYST_ROLE'
    DEFAULT_WAREHOUSE = 'ANALYTICS_WH';

-- Option B: If using email for mapping
ALTER USER john_doe SET EMAIL = 'john.doe@chghealthcare.com';

-- Grant necessary roles
GRANT ROLE ANALYST_ROLE TO USER john_doe;
```

### 2.5 (Optional) Configure Role Mapping from Okta Groups

You can map Okta groups to Snowflake roles:

```sql
-- Create a mapping table (optional but recommended)
CREATE OR REPLACE TABLE security.okta_role_mapping (
    okta_group VARCHAR,
    snowflake_role VARCHAR
);

INSERT INTO security.okta_role_mapping VALUES
    ('mcp_admin', 'ACCOUNTADMIN'),
    ('mcp_analyst', 'ANALYST_ROLE'),
    ('mcp_viewer', 'PUBLIC');
```

## Step 3: Configure MCP Server

### 3.1 Update Environment Variables

In your `.env` file:

```env
# Enable Snowflake OAuth mode
SNOWFLAKE_OAUTH_ENABLED=true

# Snowflake account (required)
SNOWFLAKE_ACCOUNT=chghealthcare

# Connection settings
SNOWFLAKE_WAREHOUSE=ANALYTICS_WH
SNOWFLAKE_DATABASE=HEALTHCARE_DATA
SNOWFLAKE_SCHEMA=PUBLIC

# Optional: Default role (user can also get role from Okta token)
SNOWFLAKE_ROLE=ANALYST_ROLE

# DO NOT SET these when using OAuth:
# SNOWFLAKE_USER=
# SNOWFLAKE_PASSWORD=
# SNOWFLAKE_AUTHENTICATOR=
```

### 3.2 Verify Configuration

Start the MCP server and check logs:

```bash
python combined_server.py
```

You should see:
```
INFO - Snowflake OAuth mode ENABLED
INFO - Account: chghealthcare
INFO - Warehouse: ANALYTICS_WH
```

## Step 4: Testing

### 4.1 Test with curl

```bash
# Get Okta token (replace with your Okta details)
TOKEN=$(curl -s -X POST \
  'https://chghealthcare.okta.com/oauth2/default/v1/token' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'grant_type=client_credentials&scope=openid' \
  -u 'CLIENT_ID:CLIENT_SECRET' | jq -r '.access_token')

# Test Snowflake query via MCP
curl -X POST http://localhost:8000/mcp/tools/list_snowflake_databases \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"
```

### 4.2 Test with Claude Desktop

Once configured, Claude Desktop should be able to:
1. Authenticate via Okta
2. List Snowflake databases
3. Execute queries as the authenticated user

### 4.3 Verify User Identity in Snowflake

Run this query to see current session info:

```sql
SELECT
    CURRENT_USER() as user,
    CURRENT_ROLE() as role,
    CURRENT_SESSION() as session_id,
    CURRENT_TIMESTAMP() as timestamp;
```

## Troubleshooting

### Error: "OAuth access token is invalid"

**Causes:**
- Token expired (default 1 hour)
- Audience mismatch
- Issuer mismatch

**Solutions:**
1. Verify `EXTERNAL_OAUTH_AUDIENCE_LIST` includes your token's audience
2. Check token issuer matches `EXTERNAL_OAUTH_ISSUER`
3. Decode token at jwt.io to verify claims

### Error: "User not found"

**Causes:**
- Snowflake user doesn't exist
- User mapping attribute mismatch

**Solutions:**
1. Create user in Snowflake with matching login_name/email
2. Verify `EXTERNAL_OAUTH_TOKEN_USER_MAPPING_CLAIM` matches your token's username claim
3. Check `EXTERNAL_OAUTH_SNOWFLAKE_USER_MAPPING_ATTRIBUTE`

### Error: "No OAuth token provided"

**Causes:**
- Token not being passed from MCP server
- FastMCP context not available

**Solutions:**
1. Verify Okta authentication is configured for MCP server
2. Check MCP server logs for token extraction
3. Ensure `SNOWFLAKE_OAUTH_ENABLED=true` is set

### Error: "Role not authorized"

**Causes:**
- User doesn't have the requested role granted
- `EXTERNAL_OAUTH_ANY_ROLE_MODE` is disabled

**Solutions:**
1. Grant the role to the user: `GRANT ROLE role_name TO USER username;`
2. Enable any role mode in security integration

## Security Best Practices

### 1. Token Lifetime
- Keep Okta token lifetime short (1 hour max)
- Implement token refresh in long-running sessions

### 2. Role Management
- Use `EXTERNAL_OAUTH_ANY_ROLE_MODE = 'DISABLE'` in production
- Map Okta groups to specific Snowflake roles
- Follow principle of least privilege

### 3. Audit Logging
Enable query logging in Snowflake:
```sql
ALTER ACCOUNT SET ENABLE_QUERY_HISTORY = TRUE;
```

Query audit logs:
```sql
SELECT
    USER_NAME,
    ROLE_NAME,
    QUERY_TEXT,
    START_TIME
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE START_TIME > DATEADD(day, -7, CURRENT_TIMESTAMP())
ORDER BY START_TIME DESC;
```

### 4. Network Policies
Restrict Snowflake access by IP:
```sql
CREATE NETWORK POLICY mcp_server_policy
    ALLOWED_IP_LIST = ('10.0.0.0/8', '192.168.1.100');

ALTER SECURITY INTEGRATION okta_external_oauth
    SET NETWORK_POLICY = mcp_server_policy;
```

## Next Steps

After setting up Snowflake OAuth:

1. **Test thoroughly** with different user roles
2. **Document user provisioning** process for new employees
3. **Set up monitoring** for authentication failures
4. **Configure alerts** for suspicious query patterns
5. **Plan token refresh** strategy for long sessions

## References

- [Snowflake External OAuth Documentation](https://docs.snowflake.com/en/user-guide/oauth-ext-overview)
- [Okta OAuth 2.0 Documentation](https://developer.okta.com/docs/concepts/oauth-openid/)
- [Snowflake Security Integration](https://docs.snowflake.com/en/sql-reference/sql/create-security-integration-oauth-external)
