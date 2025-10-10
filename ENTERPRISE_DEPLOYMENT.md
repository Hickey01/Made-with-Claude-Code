# CHG Healthcare Enterprise Deployment Guide

## Overview

This guide is for deploying the MCP server for **enterprise-wide use** at CHG Healthcare, where **individual employees authenticate with their own Okta credentials** (not a shared service account).

## Architecture: User-Level Authentication

```
┌──────────────────────────────────────────────────────────────┐
│ CHG Employee (user@chghealthcare.com)                        │
│ Uses: Claude Desktop, Web Browser, or API Client             │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     │ 1. User initiates login
                     ↓
┌──────────────────────────────────────────────────────────────┐
│ Okta SSO (chghealthcare.okta.com)                            │
│ - User logs in with CHG credentials                          │
│ - MFA challenge (if required)                                │
│ - Returns access token with user's groups                    │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     │ 2. Access token includes:
                     │    - sub: user ID (00u...)
                     │    - email: user@chghealthcare.com
                     │    - groups: ["mcp_analyst", "Engineering"]
                     │    - exp: token expiration
                     ↓
┌──────────────────────────────────────────────────────────────┐
│ MCP Server (FastMCP + JWTVerifier)                           │
│                                                               │
│ 3. For each request:                                         │
│    ✓ Validate JWT signature (Okta JWKS)                     │
│    ✓ Check expiration                                        │
│    ✓ Verify issuer & audience                               │
│    ✓ Extract user's groups                                   │
│    ✓ Apply RBAC (tool.canAccess)                            │
│    ✓ Log: "user@chghealthcare.com accessed X"               │
│                                                               │
│ 4. If authorized, access backend:                            │
│    ├─ NPPES API (public data)                               │
│    ├─ Tableau (CHG Online - server credentials)             │
│    └─ Other CHG data sources                                 │
└──────────────────────────────────────────────────────────────┘
```

## Key Principles

### ✅ Individual User Authentication
- **Each CHG employee** authenticates with their own Okta credentials
- **No shared passwords** or service account tokens
- **Token contains user identity** (email, user ID, groups)
- **Audit trail** shows exactly who accessed what data

### ✅ Role-Based Access Control (RBAC)
- User's **Okta group membership** determines tool access
- Groups: `mcp_viewer`, `mcp_analyst`, `mcp_clinician`, `mcp_admin`
- Access decisions made **per user, per request**
- Easy to grant/revoke access via Okta groups

### ✅ Separation of Concerns
- **Okta SSO**: Authenticates the CHG employee
- **RBAC**: Determines what tools the user can access
- **Backend credentials**: Separate service accounts for Tableau, databases, etc.
- **Audit logs**: Track which user requested what

## Deployment Options

### Option 1: Self-Hosted (Recommended for Production)

**Best for:**
- Full control over infrastructure
- Custom networking/security requirements
- Integration with CHG internal systems
- Production workloads

**Architecture:**
```
Users → Load Balancer (HTTPS) → MCP Server (multiple instances)
                                       ↓
                                  Okta (JWT validation)
                                       ↓
                                  Backend Systems (Tableau, DBs)
```

**Setup:**
1. Deploy to CHG infrastructure (AWS, Azure, on-prem)
2. Configure HTTPS with CHG SSL certificates
3. Set up load balancer for high availability
4. Configure Okta Web Application
5. Deploy behind CHG firewall/VPN

### Option 2: FastMCP Cloud with Okta

**Best for:**
- Quick deployment
- Lower operational overhead
- Development/staging environments

**Requirements:**
- Verify FastMCP Cloud supports JWTVerifier
- Configure Okta Native Application
- Set environment variables in FastMCP Cloud dashboard

### Option 3: Hybrid (Recommended for CHG)

**Development:**
- Use FastMCP Cloud for dev/test
- Individual developer testing with Okta

**Production:**
- Self-hosted on CHG infrastructure
- Enterprise-grade monitoring and logging
- Full integration with CHG systems

## Okta Configuration for Enterprise SSO

### Step 1: Create Okta Web Application

1. **Log into Okta Admin Console**
   - URL: https://chghealthcare.okta.com/admin

2. **Navigate to Applications**
   - Applications → Applications → Create App Integration

3. **Select Application Type**
   - Sign-in method: **OIDC - OpenID Connect**
   - Application type: **Web Application** (for server-side)
     OR **Native Application** (for Claude Desktop)

4. **Configure Application**
   ```
   Name: CHG Healthcare MCP Server

   Grant types:
   ✅ Authorization Code
   ✅ Refresh Token
   ☑️ Implicit (Hybrid) - if needed for web app

   Sign-in redirect URIs:
   - https://mcp.chghealthcare.com/callback
   - http://localhost:8080/callback (for local dev)
   - claudedesktop://callback (if Claude Desktop supports)

   Sign-out redirect URIs:
   - https://mcp.chghealthcare.com/logout

   Controlled access:
   - Allow specific groups: Engineering, Analytics, IT
   OR
   - Allow all users to access (control via RBAC groups instead)
   ```

5. **Note the credentials**
   - Client ID: `0oa...` (copy this)
   - Client Secret: Only for web apps with backend
   - Save these securely

### Step 2: Configure Authorization Server

1. **Navigate to Security → API → Authorization Servers**

2. **Select "default" or create new**
   - Name: CHG MCP Authorization Server

3. **Configure Audience**
   ```
   Audience URI: api://mcp-server
   (or https://mcp.chghealthcare.com)
   ```

4. **Add Groups Claim**
   - Claims tab → Add Claim
   ```
   Name: groups
   Include in token type: Access Token
   Value type: Groups
   Filter: Regex .*
   Include in: Any scope
   ```

5. **Configure Scopes**
   ```
   ✅ openid (default)
   ✅ profile (default)
   ✅ email (default)
   ✅ groups (custom - add if needed)
   ✅ offline_access (for refresh tokens)
   ```

### Step 3: Create Okta Groups for RBAC

1. **Navigate to Directory → Groups**

2. **Create MCP groups:**
   ```
   Group: mcp_viewer
   Description: Read-only access to public NPPES data

   Group: mcp_analyst
   Description: Data analysts with Tableau access

   Group: mcp_clinician
   Description: Healthcare providers and clinical staff

   Group: mcp_admin
   Description: Full administrative access to all tools
   ```

3. **Assign CHG employees to groups**
   - Engineering team → `mcp_analyst` + `mcp_admin`
   - Analytics team → `mcp_analyst`
   - Clinical team → `mcp_clinician`
   - General users → `mcp_viewer`

### Step 4: Test Authorization Flow

**Authorization URL:**
```
https://chghealthcare.okta.com/oauth2/default/v1/authorize?
  client_id=YOUR_CLIENT_ID&
  response_type=code&
  scope=openid%20profile%20email%20groups&
  redirect_uri=http://localhost:8080/callback&
  state=random_state_string
```

**User Flow:**
1. User opens URL in browser
2. Redirected to Okta login
3. User enters CHG credentials (firstname.lastname@chghealthcare.com)
4. MFA challenge (if required)
5. User consents to sharing profile info
6. Redirected back with authorization code
7. Exchange code for access token

**Token Exchange:**
```bash
curl -X POST https://chghealthcare.okta.com/oauth2/default/v1/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code" \
  -d "code=AUTHORIZATION_CODE_FROM_STEP_6" \
  -d "redirect_uri=http://localhost:8080/callback" \
  -d "client_id=YOUR_CLIENT_ID" \
  -d "client_secret=YOUR_CLIENT_SECRET"
```

**Response:**
```json
{
  "token_type": "Bearer",
  "expires_in": 3600,
  "access_token": "eyJraWQiOi...",
  "refresh_token": "...",
  "id_token": "...",
  "scope": "openid profile email groups"
}
```

## Server Configuration

### Environment Variables (.env)

```bash
# Okta Configuration
OKTA_ISSUER=https://chghealthcare.okta.com/oauth2/default
OKTA_AUDIENCE=api://mcp-server
OKTA_CLIENT_ID=0oaXXXXXXXXXXXXXXXXX

# Tableau Configuration (CHG Healthcare)
TABLEAU_SERVER_URL=https://10ay.online.tableau.com
TABLEAU_SITE_ID=chghealthcare
TABLEAU_TOKEN_NAME=mcp-server-token
TABLEAU_TOKEN_VALUE=your_tableau_token_here

# Server Configuration
MCP_SERVER_HOST=0.0.0.0
MCP_SERVER_PORT=8000
LOG_LEVEL=INFO
```

### Server Startup

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with CHG values

# Run server
python combined_server.py

# Expected output:
# INFO - JWT Verifier initialized for Okta issuer: https://chghealthcare.okta.com/oauth2/default
# INFO - ✅ Okta authentication ENABLED - JWT verifier active
# INFO -    Issuer: https://chghealthcare.okta.com/oauth2/default
# INFO -    Audience: api://mcp-server
# INFO - Applying RBAC to tools...
# INFO - ✅ RBAC configuration complete
```

## Client Integration

### Claude Desktop Configuration

**Location:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "chg-healthcare": {
      "url": "https://mcp.chghealthcare.com",
      "auth": {
        "type": "oauth2",
        "authorizationEndpoint": "https://chghealthcare.okta.com/oauth2/default/v1/authorize",
        "tokenEndpoint": "https://chghealthcare.okta.com/oauth2/default/v1/token",
        "clientId": "YOUR_CLIENT_ID",
        "scopes": ["openid", "profile", "email", "groups"],
        "redirectUri": "claudedesktop://callback"
      }
    }
  }
}
```

**Note:** Check Claude Desktop documentation for exact OAuth configuration format.

### Web Application

If building a web wrapper:

1. **User visits:** https://mcp.chghealthcare.com
2. **Redirect to Okta:** Authorization Code flow
3. **User logs in** with CHG credentials
4. **App receives token**, stores in session
5. **All MCP requests** include user's access token
6. **Token refresh** handled automatically

### API/Programmatic Access

For scripts or automation:

```python
import requests

# Step 1: Get user to authorize
auth_url = f"https://chghealthcare.okta.com/oauth2/default/v1/authorize?client_id={CLIENT_ID}&response_type=code&scope=openid profile email groups&redirect_uri={REDIRECT_URI}&state=xyz"
print(f"Visit: {auth_url}")

# Step 2: Exchange code for token
code = input("Enter authorization code: ")
token_response = requests.post(
    "https://chghealthcare.okta.com/oauth2/default/v1/token",
    data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
)
access_token = token_response.json()["access_token"]

# Step 3: Call MCP server with user's token
response = requests.post(
    "http://localhost:8000/tool/list_tableau_workbooks",
    headers={"Authorization": f"Bearer {access_token}"},
    json={"limit": 10}
)
print(response.json())
```

## Security & Compliance

### Audit Logging

The server logs all authentication and authorization events:

```
INFO - JWT Verifier initialized for Okta issuer: https://chghealthcare.okta.com/oauth2/default
DEBUG - Access granted for user 00u5a7b8c9d0e1f2g3h4 (analyst@chghealthcare.com) with groups ['mcp_analyst']
INFO - Tool access: list_tableau_workbooks by analyst@chghealthcare.com
WARNING - Access denied for user 00u9x8y7z6w5v4u3t2s1 (viewer@chghealthcare.com): groups ['mcp_viewer'] do not match required roles ['mcp_analyst', 'mcp_admin']
```

### Log Forwarding

Integrate with CHG's logging infrastructure:

```python
# Send logs to Splunk, Datadog, CloudWatch, etc.
import logging
from logging.handlers import SysLogHandler

# Example: Splunk HEC
handler = SysLogHandler(address=('splunk.chghealthcare.com', 514))
logger.addHandler(handler)
```

### Token Security

- **Never log full tokens** - only log first 20 characters
- **Tokens expire** - Default 1 hour, refresh automatically
- **Refresh tokens** - Allow seamless re-authentication
- **Revocation** - Tokens can be revoked in Okta Admin

### Compliance Considerations

- **HIPAA**: Audit logs track all data access
- **SOC 2**: User authentication and authorization logged
- **Access Control**: Group-based permissions
- **Data Minimization**: Users only see what they need (RBAC)

## User Management

### Adding New Users

1. **Add user to Okta** (if not already present)
2. **Assign to appropriate MCP group**
   - Directory → Groups → [group] → Add People
3. **User can immediately access** MCP server
4. **No server restart needed**

### Changing User Permissions

1. **Add/remove from Okta groups**
2. **Changes take effect on next login**
3. **Old tokens still valid until expiration**
4. **Force logout**: Revoke user's sessions in Okta

### Removing User Access

1. **Remove from all MCP groups**
2. **Or deactivate user in Okta**
3. **Existing tokens remain valid until expiration**
4. **For immediate revocation**: Revoke sessions in Okta Admin

## Monitoring & Operations

### Health Checks

```bash
# Server health
curl http://mcp.chghealthcare.com/health

# Okta connectivity
curl https://chghealthcare.okta.com/.well-known/openid-configuration
```

### Metrics to Monitor

- **Authentication success rate**
- **Token validation failures**
- **RBAC denials by user/group**
- **API response times**
- **Error rates by tool**
- **Concurrent users**

### Alerting

Configure alerts for:
- High authentication failure rate (possible attack)
- Unusual access patterns (security incident)
- Service downtime
- Okta API errors

## Troubleshooting

### User Can't Authenticate

1. **Check user exists in Okta**
2. **Verify user assigned to MCP application**
3. **Check MFA status** (if required)
4. **Check application status** (active, not suspended)

### User Can't Access Tool (403 Forbidden)

1. **Check user's Okta groups**
   - Okta Admin → Directory → People → [user] → Groups
2. **Verify group names match** RBAC configuration
3. **Get new token** (old token has old groups)
4. **Check server logs** for specific denial reason

### Token Validation Fails

1. **Check token expiration**
   ```bash
   echo $TOKEN | cut -d. -f2 | base64 -d | jq '.exp'
   date +%s  # Compare to current time
   ```
2. **Verify issuer and audience** match configuration
3. **Check Okta JWKS** is accessible
4. **Review server logs** for specific error

### Groups Not in Token

1. **Add groups claim** to Authorization Server
2. **Verify claim includes "Any scope"**
3. **Check user is actually in groups**
4. **Get new token** after adding claim

## Rollout Plan for CHG

### Phase 1: Development (Week 1-2)
- [ ] Configure Okta Web Application
- [ ] Deploy server to dev environment
- [ ] Test with pilot users (Engineering team)
- [ ] Validate RBAC with different roles

### Phase 2: Staging (Week 3-4)
- [ ] Deploy to staging environment
- [ ] Expand pilot to Analytics team
- [ ] Load testing with multiple concurrent users
- [ ] Security review with CHG InfoSec

### Phase 3: Production (Week 5-6)
- [ ] Deploy to production infrastructure
- [ ] Configure monitoring and alerting
- [ ] Document runbooks for IT operations
- [ ] Roll out to all CHG employees

### Phase 4: Ongoing
- [ ] Monitor usage and performance
- [ ] Gather user feedback
- [ ] Add additional data sources/tools
- [ ] Regular security audits

## Support & Documentation

### For CHG Employees
- **Getting Started**: Share QUICK_START.md
- **Requesting Access**: Contact IT Help Desk
- **Reporting Issues**: Submit ticket with server logs

### For CHG IT/Operations
- **Deployment**: This document
- **Okta Setup**: OKTA_SETUP.md
- **Troubleshooting**: OKTA_TESTING_GUIDE.md
- **Tableau**: TABLEAU_INTEGRATION.md

---

**Questions?** Contact the MCP Server team or CHG IT Infrastructure.
