# Quick Start: Testing Okta Authentication with Tableau

This guide gets you testing Okta authentication in under 10 minutes.

## Prerequisites
- Okta admin access
- Terminal/command line
- `curl` and `jq` installed

## Step 1: Get Your Okta Token (2 minutes)

### Option A: Using Client Credentials (Easiest)
```bash
# Replace with your actual values
export OKTA_DOMAIN="your-domain.okta.com"
export CLIENT_ID="your_client_id"
export CLIENT_SECRET="your_client_secret"

# Get token
export ACCESS_TOKEN=$(curl -s -X POST \
  "https://$OKTA_DOMAIN/oauth2/default/v1/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -d "scope=mcp:access" \
  -u "$CLIENT_ID:$CLIENT_SECRET" | jq -r '.access_token')

echo "Token obtained: ${ACCESS_TOKEN:0:20}..."
```

### Option B: Using Password Grant (For User Testing)
```bash
# For testing with specific users
export USER_EMAIL="analyst@example.com"
export USER_PASSWORD="Password123!"

export ACCESS_TOKEN=$(curl -s -X POST \
  "https://$OKTA_DOMAIN/oauth2/default/v1/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "username=$USER_EMAIL" \
  -d "password=$USER_PASSWORD" \
  -d "scope=openid profile groups" \
  -u "$CLIENT_ID:$CLIENT_SECRET" | jq -r '.access_token')
```

## Step 2: Verify Token Has Groups Claim (1 minute)

```bash
# Decode and check token
echo $ACCESS_TOKEN | cut -d. -f2 | base64 -d | jq '.'

# Expected output should include:
# {
#   "iss": "https://your-domain.okta.com/oauth2/default",
#   "aud": "api://default",
#   "groups": ["mcp_analyst", "mcp_admin"],  <-- IMPORTANT!
#   "sub": "00u..."
# }
```

**If you don't see `groups` claim:**
1. Go to Okta Admin → Security → API → Authorization Servers
2. Select your authorization server → Claims
3. Add claim: name=`groups`, type=`Groups`, token=`Access Token`, filter=`.*`
4. Get a new token

## Step 3: Test Server Locally (3 minutes)

```bash
# Start the server (in your project directory)
cd Made-with-Claude-Code
python combined_server.py

# You should see:
# ✅ Okta authentication ENABLED - JWT verifier active
# ✅ RBAC configuration complete
```

## Step 4: Test Tool Access (4 minutes)

### Test 1: Echo Tool (Public - No Auth Required)
```bash
curl http://localhost:8000/tool/echo_tool \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello World"}'

# Expected: {"result": "Hello World"}
```

### Test 2: NPPES Lookup (Requires Viewer+)
```bash
# WITH token - should work
curl http://localhost:8000/tool/lookup_npi \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"npi_number": "1234567893"}'

# Expected: ✅ Provider details

# WITHOUT token - should fail
curl http://localhost:8000/tool/lookup_npi \
  -H "Content-Type: application/json" \
  -d '{"npi_number": "1234567893"}'

# Expected: ❌ 401 Unauthorized
```

### Test 3: Tableau Tools (Requires Analyst)

**If you have analyst role:**
```bash
curl http://localhost:8000/tool/list_tableau_workbooks \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"limit": 5}'

# Expected: ✅ Workbook list (demo data if Tableau not configured)
```

**If you DON'T have analyst role (only viewer):**
```bash
# Same command as above
# Expected: ❌ 403 Forbidden
# Message: "Access denied: groups ['mcp_viewer'] do not match required roles"
```

## Step 5: Verify RBAC is Working

### Create Test Scenario

1. **Get viewer token:**
```bash
# Ensure user is ONLY in mcp_viewer group
VIEWER_TOKEN=$(curl -s -X POST \
  "https://$OKTA_DOMAIN/oauth2/default/v1/token" \
  -u "$CLIENT_ID:$CLIENT_SECRET" \
  -d "grant_type=password" \
  -d "username=viewer@example.com" \
  -d "password=Password123!" \
  -d "scope=openid profile groups" | jq -r '.access_token')
```

2. **Test viewer can access NPPES:**
```bash
curl http://localhost:8000/tool/lookup_npi \
  -H "Authorization: Bearer $VIEWER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"npi_number": "1234567893"}'
# Expected: ✅ Success
```

3. **Test viewer CANNOT access Tableau:**
```bash
curl http://localhost:8000/tool/list_tableau_workbooks \
  -H "Authorization: Bearer $VIEWER_TOKEN" \
  -H "Content-Type: application/json"
# Expected: ❌ 403 Forbidden
```

4. **Get analyst token:**
```bash
# Ensure user is in mcp_analyst group
ANALYST_TOKEN=$(curl -s -X POST \
  "https://$OKTA_DOMAIN/oauth2/default/v1/token" \
  -u "$CLIENT_ID:$CLIENT_SECRET" \
  -d "grant_type=password" \
  -d "username=analyst@example.com" \
  -d "password=Password123!" \
  -d "scope=openid profile groups" | jq -r '.access_token')
```

5. **Test analyst CAN access Tableau:**
```bash
curl http://localhost:8000/tool/list_tableau_workbooks \
  -H "Authorization: Bearer $ANALYST_TOKEN" \
  -H "Content-Type: application/json"
# Expected: ✅ Success with workbook list
```

## Quick RBAC Reference

| Role | Echo | NPPES Tools | Advanced Search | Tableau Tools |
|------|------|-------------|-----------------|---------------|
| **mcp_viewer** | ✅ | ✅ | ❌ | ❌ |
| **mcp_analyst** | ✅ | ✅ | ✅ | ✅ |
| **mcp_clinician** | ✅ | ✅ | ✅ | ❌ |
| **mcp_admin** | ✅ | ✅ | ✅ | ✅ |

## Troubleshooting

### "Token validation failed: Audience mismatch"
```bash
# Check your token's audience
echo $ACCESS_TOKEN | cut -d. -f2 | base64 -d | jq '.aud'

# Compare to your .env
grep OKTA_AUDIENCE .env

# They must match exactly!
```

### "groups claim not in token"
Add groups claim to Okta Authorization Server (see Step 2)

### "Access denied"
```bash
# Check which groups you have
echo $ACCESS_TOKEN | cut -d. -f2 | base64 -d | jq '.groups'

# Add user to required group in Okta:
# Okta Admin → Directory → Groups → [group name] → Add People
```

### "Connection refused"
Make sure server is running: `python combined_server.py`

## Next Steps

✅ **Working?** Proceed to:
- [OKTA_TESTING_GUIDE.md](OKTA_TESTING_GUIDE.md) - Complete testing scenarios
- [TABLEAU_INTEGRATION.md](TABLEAU_INTEGRATION.md) - Configure real Tableau

❌ **Not working?** Check:
- Server logs for authentication errors
- Token claims (especially `groups`)
- Okta Authorization Server configuration
- Environment variables in `.env`

## Testing Checklist

- [ ] Can obtain Okta access token
- [ ] Token contains `groups` claim
- [ ] Server starts with "✅ Okta authentication ENABLED"
- [ ] Echo tool works without token
- [ ] NPPES tools require token
- [ ] Viewer can access NPPES tools
- [ ] Viewer CANNOT access Tableau tools
- [ ] Analyst CAN access Tableau tools
- [ ] Server logs show authentication events

**All checked?** Your Okta authentication and RBAC are working! 🎉

---

*For detailed testing scenarios, see [OKTA_TESTING_GUIDE.md](OKTA_TESTING_GUIDE.md)*
