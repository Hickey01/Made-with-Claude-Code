# Tableau Integration with RBAC

## Overview
The server now includes Tableau integration tools that allow analysts and admins to query Tableau workbooks, views, and data sources through the MCP interface.

**Important:** Tableau tools are protected by Okta RBAC and require the `mcp_analyst` or `mcp_admin` role.

## Features

### 🔧 Available Tools

1. **list_tableau_workbooks** - List all workbooks on Tableau Server
2. **query_tableau_view** - Query a specific view/dashboard
3. **get_tableau_datasource** - Get data source information

### 🔐 RBAC Configuration

| Tool | mcp_viewer | mcp_analyst | mcp_clinician | mcp_admin |
|------|------------|-------------|---------------|-----------|
| list_tableau_workbooks | ❌ | ✅ | ❌ | ✅ |
| query_tableau_view | ❌ | ✅ | ❌ | ✅ |
| get_tableau_datasource | ❌ | ✅ | ❌ | ✅ |

**Why this RBAC structure?**
- **Viewers**: Should only see public NPPES data, not internal business analytics
- **Analysts**: Need access to Tableau for data analysis and reporting
- **Clinicians**: Focus on provider/patient data, not business metrics
- **Admins**: Full access to all tools

## Configuration

### Step 1: Install Tableau Client Library

```bash
pip install tableauserverclient>=0.30
```

### Step 2: Configure Tableau Server Credentials

Add to your `.env` file:

```bash
# Tableau Server URL
TABLEAU_SERVER_URL=https://tableau.chghealthcare.com

# Site ID (leave empty for default site)
TABLEAU_SITE_ID=

# Option 1: Personal Access Token (Recommended)
TABLEAU_TOKEN_NAME=my-token-name
TABLEAU_TOKEN_VALUE=abc123xyz...

# Option 2: Username/Password (Alternative)
TABLEAU_USERNAME=your-username
TABLEAU_PASSWORD=your-password
```

### Step 3: Create Tableau Personal Access Token

1. **Log into Tableau Server** as your user
2. **Navigate to**: My Account Settings → Personal Access Tokens
3. **Click**: "Create New Token"
4. **Token Name**: `mcp-server-access`
5. **Copy token value** - You'll only see this once!
6. **Add to .env file**

### Step 4: Configure Okta Groups

Ensure your Okta users are in the correct groups:

```bash
# Analysts who need Tableau access
mcp_analyst
```

Add users to this group in:
Okta Admin → Directory → Groups → mcp_analyst → Add People

## Demo Mode

If Tableau is not configured (no credentials or library not installed), the tools will return **mock data** for demonstration purposes.

**Mock data includes:**
- Sample workbook names and metadata
- Example view structures
- Simulated data source information

This allows you to test the authentication and RBAC without a Tableau server connection.

## Testing Tableau RBAC

### Test 1: Viewer Should Be Denied

```bash
# Get a token for a user in mcp_viewer group
VIEWER_TOKEN=$(curl -X POST "https://your-domain.okta.com/oauth2/default/v1/token" \
  -u "CLIENT_ID:CLIENT_SECRET" \
  -d "grant_type=password" \
  -d "username=viewer@example.com" \
  -d "password=Password123!" \
  -d "scope=openid profile groups" | jq -r '.access_token')

# Try to list workbooks
curl http://localhost:8000/tool/list_tableau_workbooks \
  -H "Authorization: Bearer $VIEWER_TOKEN" \
  -H "Content-Type: application/json"

# Expected: 403 Forbidden
# Message: "Access denied: user groups ['mcp_viewer'] do not match required roles ['mcp_analyst', 'mcp_admin']"
```

### Test 2: Analyst Should Be Allowed

```bash
# Get a token for a user in mcp_analyst group
ANALYST_TOKEN=$(curl -X POST "https://your-domain.okta.com/oauth2/default/v1/token" \
  -u "CLIENT_ID:CLIENT_SECRET" \
  -d "grant_type=password" \
  -d "username=analyst@example.com" \
  -d "password=Password123!" \
  -d "scope=openid profile groups" | jq -r '.access_token')

# List workbooks
curl http://localhost:8000/tool/list_tableau_workbooks \
  -H "Authorization: Bearer $ANALYST_TOKEN" \
  -H "Content-Type: application/json"

# Expected: 200 OK with workbook list (mock or real data)
```

### Test 3: Admin Should Be Allowed

```bash
# Get admin token
ADMIN_TOKEN=$(curl -X POST "https://your-domain.okta.com/oauth2/default/v1/token" \
  -u "CLIENT_ID:CLIENT_SECRET" \
  -d "grant_type=password" \
  -d "username=admin@example.com" \
  -d "password=Password123!" \
  -d "scope=openid profile groups" | jq -r '.access_token')

# Query a specific view
curl http://localhost:8000/tool/query_tableau_view \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workbook_name": "Healthcare Analytics Dashboard",
    "view_name": "Monthly Metrics",
    "filters": "region:West,year:2024"
  }'

# Expected: 200 OK with view details
```

## Using Tableau Tools

### Example 1: List All Workbooks

```bash
curl http://localhost:8000/tool/list_tableau_workbooks \
  -H "Authorization: Bearer $ANALYST_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"limit": 10}'
```

**Response (Demo Mode):**
```
Tableau Workbooks (Demo Mode - Tableau not configured):

--- Workbook 1 ---
Name: Healthcare Analytics Dashboard
Project: Executive Reports
Views: 12
Owner: analytics-team
Created: 2024-01-15
URL: https://tableau.example.com/workbooks/healthcare-analytics

--- Workbook 2 ---
Name: Provider Performance Metrics
Project: Operations
Views: 8
Owner: ops-team
Created: 2024-02-20
URL: https://tableau.example.com/workbooks/provider-performance

ℹ️  To connect to real Tableau server, configure:
   - TABLEAU_SERVER_URL
   - TABLEAU_TOKEN_NAME and TABLEAU_TOKEN_VALUE
```

### Example 2: Query a Specific View

```bash
curl http://localhost:8000/tool/query_tableau_view \
  -H "Authorization: Bearer $ANALYST_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workbook_name": "Provider Performance Metrics",
    "view_name": "Quarterly Summary"
  }'
```

### Example 3: Get Data Source Info

```bash
curl http://localhost:8000/tool/get_tableau_datasource \
  -H "Authorization: Bearer $ANALYST_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "datasource_name": "PROD_ANALYTICS"
  }'
```

## Security Logs

The server logs all authentication and authorization events:

### Successful Access:
```
DEBUG - Access granted for user 00u5a7b8c9d0e1f2g3h4 with groups ['mcp_analyst']
INFO - list_tableau_workbooks called by user 00u5a7b8c9d0e1f2g3h4
```

### Denied Access:
```
WARNING - Access denied for user 00u5a7b8c9d0e1f2g3h4: groups ['mcp_viewer'] do not match required roles ('mcp_analyst', 'mcp_admin')
```

## Troubleshooting

### Issue: "Access denied" for Tableau tools

**Symptom:**
```json
{
  "error": "Access denied: user groups ['mcp_viewer'] do not match required roles ['mcp_analyst', 'mcp_admin']"
}
```

**Solution:**
1. Check user's Okta groups: Okta Admin → Directory → People → [User] → Groups
2. Add user to `mcp_analyst` group
3. Get a new token (old token has old groups claim)
4. Retry request

### Issue: "Tableau not configured"

**Symptom:**
Tools return mock data with message "Demo Mode - Tableau not configured"

**Solution:**
1. Install tableauserverclient: `pip install tableauserverclient>=0.30`
2. Add Tableau credentials to `.env` file
3. Restart server
4. Verify server logs show: "Tableau configured successfully"

### Issue: "Failed to connect to Tableau Server"

**Symptom:**
```
Error accessing Tableau: Failed to sign in
```

**Solution:**
1. Verify `TABLEAU_SERVER_URL` is correct and accessible
2. Check token or username/password credentials
3. Ensure token hasn't expired (regenerate in Tableau if needed)
4. Verify network connectivity to Tableau Server
5. Check Tableau Server logs for authentication failures

### Issue: Token doesn't have groups claim

**Symptom:**
```
WARNING - Access denied for user: groups [] do not match required roles
```

**Solution:**
1. Add groups claim to Okta Authorization Server:
   - Okta Admin → Security → API → Authorization Servers → [Your Server]
   - Claims tab → Add Claim
   - Name: `groups`
   - Include in token type: Access Token
   - Value type: Groups
   - Filter: Regex `.*` (matches all groups)
2. Get new token
3. Verify groups in token: `echo $TOKEN | cut -d. -f2 | base64 -d | jq '.groups'`

## Real Tableau Integration

When connected to a real Tableau Server, the tools provide:

### Real Data Features:
- List all workbooks with actual metadata
- Access view details and URLs
- Query data source information
- View certifications and ownership
- Access project hierarchies

### Limitations:
- Cannot extract raw data (use Tableau's Hyper API for that)
- Cannot modify workbooks or permissions
- Read-only access to metadata and structure

## Next Steps

1. ✅ Configure Tableau credentials
2. ✅ Test with analyst token
3. ✅ Verify RBAC denies viewers
4. ✅ Monitor authentication logs
5. ✅ Add more Tableau tools as needed (export data, create views, etc.)

## Additional Tableau Tools (Future)

Potential future additions:
- Export view as PDF/PNG
- Extract data from Hyper files
- Query Tableau metadata API
- Trigger extract refreshes
- Manage workbook permissions

---

*For Okta authentication testing, see [OKTA_TESTING_GUIDE.md](OKTA_TESTING_GUIDE.md)*
