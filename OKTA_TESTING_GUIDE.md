# Okta Authentication Testing Guide

## Overview
This guide shows you how to test Okta authentication with your FastMCP server, including how to get tokens and test RBAC.

## Prerequisites

1. **Okta Account Access**
   - Admin access to your Okta tenant (e.g., `https://chghealthcare.okta.com`)
   - Authorization Server configured (see [OKTA_SETUP.md](OKTA_SETUP.md))

2. **Environment Variables Set**
   ```bash
   OKTA_ISSUER=https://your-domain.okta.com/oauth2/default
   OKTA_AUDIENCE=api://default
   OKTA_CLIENT_ID=your_client_id_here
   OKTA_CLIENT_SECRET=your_client_secret_here
   ```

## Step 1: Get an Okta Access Token

### Option A: Using Client Credentials Flow (Service-to-Service)

This is ideal for testing from command line or scripts.

```bash
# Get token using client credentials
curl -X POST "https://your-domain.okta.com/oauth2/default/v1/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -d "scope=mcp:access" \
  -u "CLIENT_ID:CLIENT_SECRET"
```

**Response:**
```json
{
  "token_type": "Bearer",
  "expires_in": 3600,
  "access_token": "eyJraWQiOiJ...",
  "scope": "mcp:access"
}
```

**Save the token:**
```bash
export ACCESS_TOKEN="eyJraWQiOiJ..."
```

### Option B: Using Authorization Code Flow (User Login)

This simulates a user logging in through a browser.

1. **Get the authorization URL:**
   ```
   https://your-domain.okta.com/oauth2/default/v1/authorize?
     client_id=YOUR_CLIENT_ID&
     response_type=code&
     scope=openid%20profile%20email%20groups&
     redirect_uri=http://localhost:8080/callback&
     state=random_state_string
   ```

2. **Open in browser** - User logs in with Okta credentials

3. **Okta redirects to:**
   ```
   http://localhost:8080/callback?code=AUTHORIZATION_CODE&state=random_state_string
   ```

4. **Exchange code for token:**
   ```bash
   curl -X POST "https://your-domain.okta.com/oauth2/default/v1/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "grant_type=authorization_code" \
     -d "code=AUTHORIZATION_CODE" \
     -d "redirect_uri=http://localhost:8080/callback" \
     -u "CLIENT_ID:CLIENT_SECRET"
   ```

### Option C: Using Okta CLI (Easiest for Testing)

```bash
# Install Okta CLI
brew install okta  # macOS
# or download from https://cli.okta.com

# Login to Okta
okta login

# Get a token
okta apps get-token --client-id YOUR_CLIENT_ID --scope "mcp:access"
```

## Step 2: Inspect Your Token

Before testing, verify your token has the correct claims:

### Decode JWT (without verification)
```bash
# Using jwt.io website
# Copy token to https://jwt.io

# Or using command line
echo $ACCESS_TOKEN | cut -d. -f2 | base64 -d | jq
```

### Expected Claims:
```json
{
  "ver": 1,
  "jti": "AT.xyz123...",
  "iss": "https://your-domain.okta.com/oauth2/default",
  "aud": "api://default",
  "iat": 1696234567,
  "exp": 1696238167,
  "sub": "00u5a7b8c9d0e1f2g3h4",
  "groups": [
    "mcp_viewer",
    "mcp_analyst"
  ],
  "scp": ["mcp:access"]
}
```

**Important Claims:**
- `iss` - Must match your `OKTA_ISSUER`
- `aud` - Must match your `OKTA_AUDIENCE`
- `exp` - Token expiration (Unix timestamp)
- `groups` - Your Okta groups for RBAC
- `sub` - User/service account ID

## Step 3: Test Tool Access

### Test Echo Tool (Public - No Auth Required)

```bash
# Test without token (should work in dev mode)
curl http://localhost:8000/tool/echo_tool \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello World"}'
```

### Test NPPES Tools (Requires mcp_viewer or higher)

```bash
# With valid token
curl http://localhost:8000/tool/lookup_npi \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"npi_number": "1234567893"}'

# Expected: ✅ Success with provider data

# Without token
curl http://localhost:8000/tool/lookup_npi \
  -H "Content-Type: application/json" \
  -d '{"npi_number": "1234567893"}'

# Expected: ❌ 401 Unauthorized (if Okta enabled)
```

### Test Tableau Tools (Requires mcp_analyst or higher)

```bash
# With analyst token
curl http://localhost:8000/tool/list_tableau_workbooks \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json"

# Expected: ✅ Success if user has mcp_analyst group

# With viewer token (insufficient permissions)
curl http://localhost:8000/tool/list_tableau_workbooks \
  -H "Authorization: Bearer $VIEWER_TOKEN" \
  -H "Content-Type: application/json"

# Expected: ❌ 403 Forbidden
```

## Step 4: Test RBAC Roles

### Setup: Create Test Users with Different Roles

1. **Go to Okta Admin Console** → Directory → Groups
2. **Create test users:**
   - `viewer@test.com` - Add to `mcp_viewer` group
   - `analyst@test.com` - Add to `mcp_analyst` group
   - `admin@test.com` - Add to `mcp_admin` group

### Get Tokens for Each User

```bash
# Get viewer token
VIEWER_TOKEN=$(curl -X POST "https://your-domain.okta.com/oauth2/default/v1/token" \
  -u "CLIENT_ID:CLIENT_SECRET" \
  -d "grant_type=password" \
  -d "username=viewer@test.com" \
  -d "password=Password123!" \
  -d "scope=openid profile groups" | jq -r '.access_token')

# Get analyst token
ANALYST_TOKEN=$(curl -X POST "https://your-domain.okta.com/oauth2/default/v1/token" \
  -u "CLIENT_ID:CLIENT_SECRET" \
  -d "grant_type=password" \
  -d "username=analyst@test.com" \
  -d "password=Password123!" \
  -d "scope=openid profile groups" | jq -r '.access_token')

# Get admin token
ADMIN_TOKEN=$(curl -X POST "https://your-domain.okta.com/oauth2/default/v1/token" \
  -u "CLIENT_ID:CLIENT_SECRET" \
  -d "grant_type=password" \
  -d "username=admin@test.com" \
  -d "password=Password123!" \
  -d "scope=openid profile groups" | jq -r '.access_token')
```

### Test Access Control

| Tool | Viewer | Analyst | Clinician | Admin |
|------|--------|---------|-----------|-------|
| echo_tool | ✅ | ✅ | ✅ | ✅ |
| lookup_npi | ✅ | ✅ | ✅ | ✅ |
| search_providers | ✅ | ✅ | ✅ | ✅ |
| advanced_search | ❌ | ✅ | ✅ | ✅ |
| list_tableau_workbooks | ❌ | ✅ | ❌ | ✅ |
| query_tableau_view | ❌ | ✅ | ❌ | ✅ |

**Test viewer (should fail on Tableau tools):**
```bash
curl http://localhost:8000/tool/list_tableau_workbooks \
  -H "Authorization: Bearer $VIEWER_TOKEN" \
  -H "Content-Type: application/json"
# Expected: 403 Forbidden
```

**Test analyst (should succeed):**
```bash
curl http://localhost:8000/tool/list_tableau_workbooks \
  -H "Authorization: Bearer $ANALYST_TOKEN" \
  -H "Content-Type: application/json"
# Expected: 200 OK with workbook list
```

## Step 5: Check Server Logs

The server logs authentication events. Look for:

### Successful Authentication:
```
INFO - JWT Verifier initialized for Okta issuer: https://your-domain.okta.com/oauth2/default
INFO - ✅ Okta authentication ENABLED - JWT verifier active
DEBUG - Access granted for user 00u5a7b8c9d0e1f2g3h4 with groups ['mcp_analyst']
```

### Failed Authentication:
```
WARNING - Access denied for user 00u5a7b8c9d0e1f2g3h4: groups ['mcp_viewer'] do not match required roles ('mcp_analyst', 'mcp_admin')
```

### Token Validation Errors:
```
ERROR - Token validation failed: Token has expired
ERROR - Token validation failed: Invalid signature
ERROR - Token validation failed: Audience mismatch
```

## Step 6: Test in Claude Desktop

If you're using this server with Claude Desktop:

1. **Update Claude Desktop config** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
   ```json
   {
     "mcpServers": {
       "chg-healthcare": {
         "command": "python",
         "args": ["/path/to/combined_server.py"],
         "env": {
           "OKTA_ISSUER": "https://your-domain.okta.com/oauth2/default",
           "OKTA_AUDIENCE": "api://default",
           "OKTA_CLIENT_ID": "your_client_id",
           "OKTA_CLIENT_SECRET": "your_client_secret"
         }
       }
     }
   }
   ```

2. **Restart Claude Desktop**

3. **Test with prompts:**
   ```
   "Search for providers named Smith in California"
   "List all Tableau workbooks"
   ```

4. **Check logs** in Claude Desktop's developer console

## Common Issues & Troubleshooting

### Issue: "Token validation failed: Audience mismatch"
**Solution:** Ensure `OKTA_AUDIENCE` matches the `aud` claim in your token
```bash
# Check token audience
echo $ACCESS_TOKEN | cut -d. -f2 | base64 -d | jq '.aud'
```

### Issue: "Access denied: groups do not match required roles"
**Solution:** Add user to correct Okta group
1. Go to Okta Admin → Directory → Groups
2. Find the required group (e.g., `mcp_analyst`)
3. Add user to group
4. Get new token (old token still has old groups claim)

### Issue: "Token has expired"
**Solution:** Get a new token - tokens typically expire after 1 hour
```bash
# Check token expiration
echo $ACCESS_TOKEN | cut -d. -f2 | base64 -d | jq '.exp'
# Compare to current time: date +%s
```

### Issue: "groups claim not in token"
**Solution:** Add groups claim to Authorization Server
1. Okta Admin → Security → API → Authorization Servers
2. Select your server → Claims tab
3. Add claim: name=`groups`, include in token type=`Access Token`, value type=`Groups`, filter=`Regex: .*`

### Issue: "FastMCP JWTVerifier not available"
**Solution:** Update FastMCP to latest version
```bash
pip install --upgrade fastmcp
```

## Testing Checklist

- [ ] Okta Authorization Server configured with groups claim
- [ ] Environment variables set correctly
- [ ] Can obtain access token via client credentials
- [ ] Token contains expected claims (iss, aud, groups)
- [ ] Server logs show "✅ Okta authentication ENABLED"
- [ ] Public tool (echo) works without token
- [ ] Protected tool (lookup_npi) requires token
- [ ] Viewer role can access basic tools
- [ ] Viewer role is denied access to analyst tools
- [ ] Analyst role can access Tableau tools
- [ ] Admin role can access all tools
- [ ] Expired tokens are rejected
- [ ] Invalid tokens are rejected

## Security Best Practices

1. **Never commit tokens to git** - Tokens are sensitive credentials
2. **Use short-lived tokens** - Set expiration to 1 hour or less
3. **Rotate secrets regularly** - Update client secrets monthly
4. **Monitor authentication logs** - Watch for unusual access patterns
5. **Use HTTPS in production** - Never send tokens over HTTP
6. **Implement rate limiting** - Prevent brute force attacks
7. **Audit group memberships** - Review who has access quarterly

## Next Steps

After successful testing:

1. ✅ Verify all RBAC rules work as expected
2. ✅ Test token expiration and renewal
3. ✅ Document which roles need which tools
4. ✅ Set up monitoring and alerting
5. ✅ Deploy to production with HTTPS
6. ✅ Train users on authentication flow

---

*Need help? Check [OKTA_SETUP.md](OKTA_SETUP.md) for initial configuration or [AUTHENTICATION_STATUS.md](AUTHENTICATION_STATUS.md) for deployment options.*
