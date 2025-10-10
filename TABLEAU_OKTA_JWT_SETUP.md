# Tableau Connected Apps Setup for Okta JWT Passthrough

## Overview

This guide explains how to configure **Tableau Connected Apps with External Authorization Server (EAS)** to enable **Okta SSO token passthrough** for REST API access. This eliminates the need for personal access tokens or service accounts.

## Current State vs. Desired State

### Current (Not Ideal)
```
User → Okta Login → MCP Server → Personal Access Token → Tableau API
                                  (separate credential)
```

### Desired (True SSO)
```
User → Okta Login → MCP Server → User's Okta JWT → Tableau API
                                  (same token!)      validates with Okta
```

## Benefits of JWT Passthrough

✅ **True Single Sign-On** - One login for everything
✅ **No Service Accounts** - No shared credentials to manage
✅ **Per-User Authorization** - Tableau sees the actual user
✅ **Audit Trail** - Tableau logs show real user identity
✅ **Automatic Expiration** - Token expires when Okta session expires
✅ **No Token Management** - No PATs to create/rotate/revoke

## Prerequisites

Before starting, verify:
- [ ] CHG has Tableau Cloud (https://10ay.online.tableau.com)
- [ ] CHG uses Okta for Tableau SSO (mychg.okta.com)
- [ ] You have **Tableau Site Admin** access
- [ ] You have **Okta Admin** access
- [ ] Tableau version supports Connected Apps (2021.4+)

## Step 1: Find Your Tableau Site LUID

The Site LUID (Locally Unique Identifier) is required for JWT configuration.

### Option A: Via Tableau Cloud UI

1. **Sign into Tableau Cloud** as site admin
2. **Go to:** Settings (gear icon) → General
3. **Look for:** "Site ID" or "Content URL"
   - Example: `chghealthcare` (this is the site name)
4. **To get the LUID:** You need to use the REST API or Settings page
   - The LUID looks like: `a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6`

### Option B: Via REST API

```bash
# Sign in and get the site LUID
curl -X POST "https://10ay.online.tableau.com/api/3.21/auth/signin" \
  -H "Content-Type: application/json" \
  -d '{
    "credentials": {
      "personalAccessTokenName": "YOUR_TOKEN_NAME",
      "personalAccessTokenSecret": "YOUR_TOKEN_SECRET",
      "site": {
        "contentUrl": "chghealthcare"
      }
    }
  }'

# Response includes: "site": {"id": "SITE_LUID"}
```

### Option C: Via Settings → Site

1. Sign into Tableau Cloud
2. Settings → Site → General
3. Look for "Site LUID" field
4. Copy the UUID value

**CHG Healthcare Site LUID:** `c37e554a-0bfb-aa48-8037-87274e81445e`

(This value was extracted from the CHG Okta SAML configuration Object GUID)

## Step 2: Configure Tableau Connected App (Tableau Admin)

### 2.1 Access Connected Apps

1. **Sign into Tableau Cloud** as site admin
2. **Navigate to:** Settings (gear icon) → Connected Apps
3. **Click:** "New Connected App"
4. **Select:** "OAuth 2.0 Trust" (External Authorization Server)

### 2.2 Configure the Connected App

**Fill in the form:**

```
Name: CHG Okta JWT Integration
Description: Enables Okta SSO token passthrough for MCP Server REST API access

External Authorization Server (EAS) Settings:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Issuer URL: https://mychg.okta.com/oauth2/default
(This must match the 'iss' claim in Okta JWTs)

Domain Allowlist: https://mychg.okta.com
(Allows Tableau to validate tokens from this domain)

Access Level:
☑ Enable connected app

Advanced Settings:
Max Token Expiration: 600 seconds (10 minutes - Tableau requirement)
```

**Click:** Save

### 2.3 Verify Configuration

After saving, verify:
- Connected app status shows "Enabled"
- Issuer URL matches Okta exactly
- Domain is allowlisted

## Step 3: Configure Okta Authorization Server (Okta Admin)

### 3.1 Access Okta Authorization Server

1. **Log into Okta Admin Console**
2. **Navigate to:** Security → API → Authorization Servers
3. **Select:** The authorization server used for Tableau
   - Likely: "default" or a custom CHG authorization server
   - URL format: `https://mychg.okta.com/oauth2/{server_id}`

### 3.2 Add Tableau Audience

1. **In Authorization Server Settings:**
2. **Audience (aud) claim configuration:**

**Option A: Update default audience**
- Go to Settings → Audience
- Current might be: `api://default` or `https://mychg.okta.com`
- This is site-wide, so be careful!

**Option B: Add Tableau-specific claim (RECOMMENDED)**
- Go to Claims tab
- Add new claim:

```
Claim Configuration:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Name: tableau_aud (or just 'aud' if no conflicts)
Include in token type: Access Token
Value type: Expression
Value: "tableau:c37e554a-0bfb-aa48-8037-87274e81445e"
Include in: Any scope
Disable claim: No

This creates the Tableau audience claim for CHG Healthcare site
```

### 3.3 Add Required Claims for Tableau

Tableau JWTs require these claims:

**Claim 1: User Email (sub)**
```
Name: sub
Include in token type: Access Token
Value type: Expression
Value: user.email
Include in: Any scope
```

**Claim 2: Scopes (scp)**
```
Name: scp
Include in token type: Access Token
Value type: Expression
Value: ["tableau:content:read", "tableau:views:embed"]
Include in: Any scope
```

**Claim 3: Issuer (iss) - Usually automatic**
- Should already be set to: `https://mychg.okta.com/oauth2/default`

**Claim 4: Expiration (exp) - Automatic**
- Tableau requires exp within 10 minutes of issue time
- Configure in: Settings → Lifetime → Access Token Lifetime = 10 minutes (or less)

### 3.4 Update Access Policy

1. **Go to:** Access Policies tab
2. **Create or update policy:**

```
Policy Name: Tableau API Access
Assigned to: Your MCP application
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Rule: Allow Tableau Access
IF:
  - Requested scopes: Contains any of [tableau:content:read, tableau:views:embed]
  - User: Assigned to application OR In groups [mcp_analyst, mcp_admin]

THEN Grant access with these scopes
```

## Step 4: Update Okta Application Configuration

### 4.1 Configure MCP Application Scopes

1. **Navigate to:** Applications → Applications
2. **Select:** CHG MCP Server application
3. **Go to:** Sign On tab → OpenID Connect ID Token

**Add Tableau scopes:**
```
tableau:content:read
tableau:views:embed
tableau:datasources:read
tableau:workbooks:read
```

### 4.2 Test Token Generation

Use Okta's Token Preview to verify JWT structure:

1. **Go to:** Security → API → Authorization Servers → [Your Server] → Token Preview
2. **Settings:**
   - OAuth/OIDC client: CHG MCP Server
   - Grant type: Authorization Code
   - User: Select a test user
   - Scopes: tableau:content:read openid profile email groups

3. **Click:** Preview Token
4. **Verify JWT contains:**
   ```json
   {
     "iss": "https://mychg.okta.com/oauth2/default",
     "aud": "tableau:c37e554a-0bfb-aa48-8037-87274e81445e",
     "sub": "user@chghealthcare.com",
     "scp": ["tableau:content:read", "tableau:views:embed"],
     "groups": ["mcp_analyst"],
     "exp": 1234567890,
     "iat": 1234567300,
     "jti": "unique-token-id"
   }
   ```

## Step 5: Update MCP Server Code

The MCP server needs to be updated to pass the user's Okta JWT to Tableau REST API.

### Current Code (Uses Service Account)
```python
# Server authenticates to Tableau with its own credentials
auth = TSC.PersonalAccessTokenAuth(token_name, token_value, site_id)
server.auth.sign_in(auth)
```

### New Code (Uses User's JWT)
```python
# Server passes user's Okta JWT to Tableau
# Tableau validates JWT with Okta directly
auth = TSC.JWTAuth(jwt_token, site_id)
server.auth.sign_in_with_jwt(auth)
```

**Implementation needed:**
1. Extract user's JWT from FastMCP auth context
2. Pass JWT to Tableau authentication
3. Handle token expiration and refresh

## Step 6: Testing the Integration

### Test 1: Verify JWT Structure

```bash
# Get a token from Okta
curl -X POST "https://mychg.okta.com/oauth2/default/v1/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code" \
  -d "code=YOUR_AUTH_CODE" \
  -d "redirect_uri=YOUR_REDIRECT" \
  -d "client_id=YOUR_CLIENT_ID"

# Decode the JWT
echo "YOUR_JWT_TOKEN" | cut -d. -f2 | base64 -d | jq '.'

# Verify it contains:
# - aud: "tableau:YOUR_SITE_LUID"
# - sub: user email
# - scp: tableau scopes
# - iss: mychg.okta.com
# - exp: within 10 minutes
```

### Test 2: Test Tableau API with JWT

```bash
# Try to sign in to Tableau REST API with JWT
curl -X POST "https://10ay.online.tableau.com/api/3.21/auth/signin" \
  -H "Content-Type: application/json" \
  -d '{
    "credentials": {
      "jwt": "YOUR_OKTA_JWT_HERE",
      "site": {
        "contentUrl": "chghealthcare"
      }
    }
  }'

# Expected: Success response with Tableau credentials
# Error: Check JWT claims, expiration, issuer, audience
```

### Test 3: End-to-End with MCP Server

1. User authenticates with Okta through MCP client
2. MCP server receives user's JWT
3. MCP server calls Tableau API with JWT
4. Tableau validates JWT with Okta
5. Tableau returns data
6. MCP server returns data to user

**Check server logs for:**
```
INFO - Access granted for user user@chghealthcare.com with groups ['mcp_analyst']
INFO - Authenticating to Tableau with user JWT
INFO - Tableau authentication successful
INFO - Tool access: list_tableau_workbooks by user@chghealthcare.com
```

## Troubleshooting

### Error: "Invalid JWT"

**Check:**
- [ ] JWT is not expired (exp claim)
- [ ] Issuer matches exactly: `https://mychg.okta.com/oauth2/default`
- [ ] Audience is: `tableau:SITE_LUID`
- [ ] JWT is signed (not encrypted)
- [ ] Claims include: sub, aud, iss, exp, scp

### Error: "Invalid audience"

**Fix:**
- Verify Tableau Site LUID is correct
- Ensure Okta JWT includes: `"aud": "tableau:YOUR_SITE_LUID"`
- Check Tableau Connected App has correct issuer URL

### Error: "Token expired"

**Fix:**
- Okta Access Token Lifetime > current time
- Tableau requires exp within 10 minutes of iat
- Set shorter token lifetime in Okta (5-10 minutes)

### Error: "User not found"

**Fix:**
- Ensure `sub` claim contains user's email
- Verify user exists in Tableau with that email
- Check email case matches exactly

### Connected App Not Working

**Check:**
1. Connected App is "Enabled" in Tableau
2. Issuer URL exactly matches Okta
3. Domain is allowlisted
4. JWT signature algorithm is RS256 (Okta default)

## Security Considerations

### Token Expiration
- **Okta tokens expire** (typically 1 hour)
- **Tableau requires** exp within 10 minutes of iat
- **Solution:** Use shorter Okta token lifetime for Tableau scopes

### Token Refresh
- User's token should refresh automatically via Okta
- MCP server should handle expired tokens gracefully
- Refresh tokens can extend session without re-login

### Audit Logging
- Tableau logs show actual user (not service account)
- Okta logs show token issuance
- MCP server logs show user access
- Full audit trail maintained

### Access Control
- Tableau permissions still apply per user
- Okta RBAC controls MCP tool access
- Tableau RBAC controls data access
- Layered security model

## Rollback Plan

If JWT passthrough doesn't work immediately:

1. **Keep existing PAT as fallback:**
   - Configure both JWT and PAT authentication
   - Try JWT first, fall back to PAT on error

2. **Progressive rollout:**
   - Test with pilot users first
   - Monitor error rates
   - Expand when stable

3. **Revert if needed:**
   - Disable Tableau Connected App
   - Continue using PAT authentication
   - Investigate and retry later

## Next Steps

1. **CHG IT configures Tableau Connected App** (Step 2)
2. **Okta Admin configures JWT claims** (Step 3)
3. **Test JWT structure** (Step 6, Test 1)
4. **MCP Server code update** (Step 5)
5. **End-to-end testing** (Step 6, Test 3)
6. **Production rollout**

## Reference Documentation

- [Tableau Connected Apps - OAuth 2.0 Trust](https://help.tableau.com/current/online/en-us/connected_apps_eas.htm)
- [Tableau REST API Authentication](https://help.tableau.com/current/api/rest_api/en-us/REST/rest_api_concepts_auth.htm)
- [Okta Authorization Servers](https://developer.okta.com/docs/concepts/auth-servers/)
- [JWT Best Practices](https://datatracker.ietf.org/doc/html/rfc8725)

---

**Questions or issues?** Contact CHG IT Infrastructure team or Tableau/Okta support.
