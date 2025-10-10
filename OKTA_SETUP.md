# Okta Authentication Setup Guide

This guide explains how to configure Okta authentication and role-based access control (RBAC) for the CHG Healthcare MCP Server.

**🏢 Enterprise SSO Setup:** This guide focuses on configuring **individual user authentication** where each CHG employee logs in with their own Okta credentials. This is the recommended approach for enterprise deployment.

**✨ Single-File Architecture:** All authentication and RBAC code is built into `combined_server.py` - no separate modules or dependencies required! The server automatically enables Okta when configured, or runs in development mode when not configured.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Okta Configuration](#okta-configuration)
3. [Server Configuration](#server-configuration)
4. [Role Definitions](#role-definitions)
5. [Testing Authentication](#testing-authentication)
6. [Troubleshooting](#troubleshooting)

## Prerequisites

- Okta account with admin access (CHG Healthcare Okta instance)
- Python 3.10+ installed
- Access to create applications and authorization servers in Okta

## Okta Configuration

### Step 1: Create an Authorization Server

1. Log in to your Okta Admin Console
2. Navigate to **Security → API → Authorization Servers**
3. Click **Add Authorization Server**
4. Configure:
   - **Name**: `MCP Server Authorization`
   - **Audience**: `https://mcp.chghealthcare.com` (or your server URL)
   - **Description**: `Authorization server for MCP tool access`
5. Click **Save**
6. Note the **Issuer URI** (e.g., `https://chghealthcare.okta.com/oauth2/aus1234567`)

### Step 2: Create Custom Scopes

1. In your Authorization Server, click the **Scopes** tab
2. Click **Add Scope** for each of these:
   - **Name**: `mcp:access`, **Description**: `Access to MCP tools`
   - **Name**: `mcp:read`, **Description**: `Read-only access to MCP data`
   - **Name**: `mcp:write`, **Description**: `Write access to MCP data` (for future tools)
3. Check **Include in public metadata** for all scopes

### Step 3: Create Claims for Groups

1. Click the **Claims** tab
2. Click **Add Claim**
3. Configure the groups claim:
   - **Name**: `groups`
   - **Include in token type**: Access Token
   - **Value type**: Expression
   - **Value**: `getFilteredGroups(app.profile.groups, "mcp_", 100)`
   - **Include in**: Any scope
4. This will include all groups starting with "mcp_" in the access token

### Step 4: Create Groups in Okta

1. Navigate to **Directory → Groups**
2. Create the following groups:
   - **mcp_viewer**: Read-only access to public data
   - **mcp_analyst**: Data analyst access with advanced search
   - **mcp_clinician**: Healthcare provider access
   - **mcp_admin**: Full administrative access
3. Assign users to appropriate groups

### Step 5: Create an Application (IMPORTANT - Web Application for Enterprise)

**⚠️ IMPORTANT FOR CHG:** Use **Web Application** for enterprise deployment, not API Services!

#### Option A: Web Application (RECOMMENDED for CHG Enterprise)

This allows individual CHG employees to authenticate with SSO:

1. Navigate to **Applications → Applications**
2. Click **Create App Integration**
3. Select:
   - **Sign-in method**: **OIDC - OpenID Connect**
   - **Application type**: **Web Application**
4. Configure:
   - **App integration name**: `CHG MCP Server`
   - **Grant type**:
     - ✅ Authorization Code
     - ✅ Refresh Token
     - ✅ Implicit (Hybrid) - optional for web UI
   - **Sign-in redirect URIs**:
     - `https://mcp.chghealthcare.com/callback` (production)
     - `http://localhost:8080/callback` (local dev)
     - `claudedesktop://callback` (if using Claude Desktop)
   - **Sign-out redirect URIs**:
     - `https://mcp.chghealthcare.com/logout`
   - **Controlled Access**:
     - Select groups that can access (e.g., Engineering, Analytics)
     - OR allow all CHG users (control access via mcp_* groups instead)
5. **Enable Proof Key for Code Exchange (PKCE)** - for enhanced security
6. Click **Save**
7. Note the **Client ID** (you'll need this)
8. Note the **Client Secret** (only if your integration requires it)

**Benefits:**
- ✅ Each user logs in individually
- ✅ User's actual Okta groups used for RBAC
- ✅ Full audit trail of who accessed what
- ✅ MFA support
- ✅ Token refresh for long sessions

#### Option B: API Services (FOR TESTING ONLY - Not Recommended)

For development/testing with service account:

1. Navigate to **Applications → Applications**
2. Click **Create App Integration**
3. Select:
   - **Sign-in method**: API Services (OAuth 2.0 client credentials)
4. Configure:
   - **App integration name**: `MCP Server Dev`
5. Click **Save**
6. Note the **Client ID** and **Client Secret**

**⚠️ LIMITATIONS:**
- ❌ Shared service account (all users appear as one)
- ❌ Cannot track individual user activity
- ❌ Not suitable for production/enterprise use
- ✅ OK for local development and testing

### Step 6: Assign Application to Authorization Server

1. Go back to **Security → API → Authorization Servers**
2. Select your authorization server
3. Click the **Access Policies** tab
4. Create a new policy or edit the default policy
5. Add a rule:
   - **Rule Name**: `MCP Access Rule`
   - **Grant type**: Client Credentials, Authorization Code
   - **Scopes**: `openid`, `profile`, `email`, `groups`, `mcp:access`
   - **User**: Any user assigned to the application
6. Click **Create Rule**

## Server Configuration

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` with your Okta configuration:
```env
# Okta Configuration
OKTA_ISSUER=https://chghealthcare.okta.com/oauth2/aus1234567
OKTA_AUDIENCE=https://mcp.chghealthcare.com
OKTA_CLIENT_ID=0oa1234567890abcdef
OKTA_CLIENT_SECRET=your_secret_here

# Server Configuration
MCP_SERVER_HOST=0.0.0.0
MCP_SERVER_PORT=8000
LOG_LEVEL=INFO
```

**IMPORTANT**: Never commit `.env` to version control!

### Step 3: Verify Configuration

Run the server to verify Okta is configured:

```bash
python combined_server.py
```

You should see:
```
INFO - Okta authentication ENABLED
INFO - SECURITY STATUS:
INFO -   - Authentication: ENABLED
INFO -   - RBAC: ENABLED
INFO -   - Okta Issuer: https://chghealthcare.okta.com/oauth2/...
INFO -   - Audience: https://mcp.chghealthcare.com
```

## Role Definitions

The server implements the following role hierarchy:

### mcp_viewer (Read-Only)
**Access**: Basic read access to public data
**Allowed Tools**:
- `echo_tool` - Test connectivity
- `search_providers` - Search healthcare providers
- `search_organizations` - Search organizations
- `lookup_npi` - Look up provider by NPI number

### mcp_analyst (Data Analyst)
**Access**: Enhanced search capabilities
**Allowed Tools**: All viewer tools, plus:
- `advanced_search` - Multi-criteria advanced search

### mcp_clinician (Healthcare Provider)
**Access**: Clinical data access
**Allowed Tools**: All analyst tools, plus:
- Future clinical tools (patient data, records, etc.)

### mcp_admin (Administrator)
**Access**: Full administrative access
**Allowed Tools**: ALL tools (*)

## Testing Authentication

### Test 1: Without Authentication (Should Fail)

```bash
curl -X POST http://localhost:8000/mcp/tools/search_providers \
  -H "Content-Type: application/json" \
  -d '{"last_name": "Smith"}'
```

Expected response: `401 Unauthorized`

### Test 2: Get Access Token (Client Credentials)

```bash
curl -X POST https://chghealthcare.okta.com/oauth2/aus1234567/v1/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&scope=mcp:access" \
  -u "CLIENT_ID:CLIENT_SECRET"
```

Save the `access_token` from the response.

### Test 3: Call Tool with Token

```bash
curl -X POST http://localhost:8000/mcp/tools/search_providers \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"last_name": "Smith", "state": "CA"}'
```

Expected response: Provider search results

### Test 4: Verify RBAC

Try accessing `advanced_search` with a viewer token:

```bash
curl -X POST http://localhost:8000/mcp/tools/advanced_search \
  -H "Authorization: Bearer VIEWER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"taxonomy_description": "Cardiology"}'
```

Expected response: `403 Forbidden` (viewers don't have access to advanced_search)

## Security Best Practices

### 1. Token Lifecycle
- Access tokens expire after 1 hour (default Okta setting)
- Implement token refresh using refresh tokens for long-running sessions
- Never store tokens in version control or logs

### 2. HTTPS in Production
Always use HTTPS in production. Use nginx or similar reverse proxy:

```nginx
server {
    listen 443 ssl http2;
    server_name mcp.chghealthcare.com;

    ssl_certificate /etc/ssl/certs/mcp.chghealthcare.com.crt;
    ssl_certificate_key /etc/ssl/private/mcp.chghealthcare.com.key;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header Authorization $http_authorization;
    }
}
```

### 3. Least Privilege
- Assign users to the minimum role needed
- Start with `mcp_viewer` and escalate only when necessary
- Regularly audit group memberships

### 4. Monitoring
Monitor authentication failures:
```bash
tail -f logs/security.log | grep "authentication_failure"
```

### 5. Secret Management
For production, use a secret management service:
- Azure Key Vault
- AWS Secrets Manager
- HashiCorp Vault

Never hardcode secrets in code or commit `.env` files.

## Troubleshooting

### Issue: "Token audience mismatch"

**Cause**: The `aud` claim in the token doesn't match `OKTA_AUDIENCE`

**Solution**:
1. Verify `OKTA_AUDIENCE` in `.env` matches the audience configured in your Authorization Server
2. Check the token claims: Decode at [jwt.io](https://jwt.io)
3. Ensure the client is requesting tokens from the correct authorization server

### Issue: "Token from untrusted issuer"

**Cause**: The `iss` claim doesn't match `OKTA_ISSUER`

**Solution**:
1. Verify `OKTA_ISSUER` includes the full authorization server path
2. Format: `https://{domain}/oauth2/{authServerId}`
3. Do not use the org URL (ending in `-admin.okta.com`)

### Issue: "Groups not appearing in token"

**Cause**: Groups claim not configured or user not in groups

**Solution**:
1. Verify the groups claim exists in Authorization Server → Claims
2. Ensure claim expression is: `getFilteredGroups(app.profile.groups, "mcp_", 100)`
3. Verify user is assigned to groups starting with `mcp_`
4. Check user is assigned to the application

### Issue: "403 Forbidden" when calling tools

**Cause**: User doesn't have required role for the tool

**Solution**:
1. Check user's groups in Okta
2. Verify group membership: Check token at jwt.io
3. Review role definitions in `okta_auth.py` → `ROLE_DEFINITIONS`
4. Assign user to appropriate group (e.g., `mcp_analyst` for advanced_search)

### Issue: "Running without authentication"

**Cause**: Okta environment variables not set

**Solution**:
1. Verify `.env` file exists in project root
2. Check all required variables are set:
   - `OKTA_ISSUER`
   - `OKTA_AUDIENCE`
3. Restart the server after updating `.env`

## Development Mode

For local development without Okta:

1. Don't set Okta environment variables (or leave them blank)
2. Server will run in development mode with authentication disabled
3. All tools will be accessible without tokens
4. You'll see: `Okta authentication NOT configured - running in development mode`

**WARNING**: Never deploy to production without authentication!

## Next Steps

After setting up Okta authentication:

1. **Add more tools**: New tools automatically inherit RBAC
2. **Integrate with Tableau**: Use `mcp_analyst` role for Tableau users
3. **Integrate with dbt**: Use service-to-service (client credentials) auth
4. **Integrate with Snowflake**: Implement Snowflake-specific tools with appropriate RBAC
5. **Audit logging**: Add comprehensive audit trails for compliance

## Support

For issues with:
- **Okta configuration**: Contact CHG IT Security team
- **Server issues**: Check logs in `logs/` directory
- **Code issues**: Review `okta_auth.py` and `combined_server.py`

## Additional Resources

- [Okta Developer Documentation](https://developer.okta.com/docs/)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [OAuth 2.0 RFC](https://datatracker.ietf.org/doc/html/rfc6749)
- [JWT Best Practices](https://datatracker.ietf.org/doc/html/rfc8725)
