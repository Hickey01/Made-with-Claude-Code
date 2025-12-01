# FastMCP Cloud + Claude Desktop Windows Troubleshooting Guide

This guide addresses connection issues with FastMCP Cloud servers when using Claude Desktop on Windows, specifically the `coordinateAuth` OAuth callback port bug.

## The Problem

When connecting to a FastMCP Cloud server (e.g., `chg-fastmcp.fastmcp.app`) using Claude Desktop on Windows, the connection fails with:

```
Fatal error: TypeError: Cannot read properties of null (reading 'port')
    at coordinateAuth (mcp-remote/dist/chunk-WSHBHZXM.js:14600:30)
```

### Root Cause

This error occurs due to a coordination bug in the `mcp-remote` package on Windows:

1. **Lockfile Coordination**: Windows has disabled lockfile-based coordination due to platform-specific process management issues
2. **Port Reuse Logic**: When OAuth tries to reuse an existing callback port from a previous session, the coordination logic attempts to read port information that may be null or stale
3. **Race Conditions**: Multiple instances or crashed sessions leave corrupted state files that cause the next authentication attempt to fail

## Workarounds

### Solution 1: Complete State Cleanup (Recommended)

Clear all cached authentication state and force a fresh OAuth flow:

**Windows PowerShell:**
```powershell
# Stop Claude Desktop completely
taskkill /F /IM "Claude.exe" 2>$null

# Clear npx cache
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\npm-cache\_npx" -ErrorAction SilentlyContinue

# Clear mcp-remote auth state
Remove-Item -Recurse -Force "$env:USERPROFILE\.mcp-auth" -ErrorAction SilentlyContinue

# Clear Claude Desktop logs (optional, for clean testing)
Remove-Item -Recurse -Force "$env:APPDATA\Claude\logs" -ErrorAction SilentlyContinue

# Restart Claude Desktop
```

**Windows Command Prompt:**
```cmd
# Stop Claude Desktop
taskkill /F /IM "Claude.exe"

# Clear caches
rmdir /S /Q "%LOCALAPPDATA%\npm-cache\_npx"
rmdir /S /Q "%USERPROFILE%\.mcp-auth"
rmdir /S /Q "%APPDATA%\Claude\logs"

# Restart Claude Desktop
```

### Solution 2: Use Environment Variables for Auth Headers

Windows Claude Desktop has a bug where spaces in `args` aren't properly escaped when invoking npx. Restructure your MCP configuration:

**Before (Broken on Windows):**
```json
{
  "mcpServers": {
    "chg-fastmcp": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote@latest",
        "https://chg-fastmcp.fastmcp.app/mcp",
        "--header",
        "Authorization: Bearer TOKEN"
      ]
    }
  }
}
```

**After (Windows-Compatible):**
```json
{
  "mcpServers": {
    "chg-fastmcp": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote@latest",
        "https://chg-fastmcp.fastmcp.app/mcp",
        "--header",
        "Authorization:${AUTH_HEADER}"
      ],
      "env": {
        "AUTH_HEADER": "Bearer YOUR_TOKEN_HERE",
        "NODE_EXTRA_CA_CERTS": "C:\\path\\to\\ca-certificates.crt"
      }
    }
  }
}
```

**Key changes:**
- Remove spaces around `:` in header arguments
- Move actual values to environment variables
- Use `${VAR_NAME}` placeholders in args

### Solution 3: Specify OAuth Callback Port Explicitly

Force a specific callback port to avoid coordination conflicts:

```json
{
  "mcpServers": {
    "chg-fastmcp": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote@latest",
        "https://chg-fastmcp.fastmcp.app/mcp",
        "3334"
      ]
    }
  }
}
```

**Note**: If port 3334 is unavailable, `mcp-remote` will automatically select a random open port.

### Solution 4: Enable Debug Logging

Get detailed logs to diagnose the exact failure point:

```json
{
  "mcpServers": {
    "chg-fastmcp": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote@latest",
        "https://chg-fastmcp.fastmcp.app/mcp",
        "--debug"
      ]
    }
  }
}
```

Debug logs are written to:
- `%USERPROFILE%\.mcp-auth\{server_hash}_debug.log`

**Log location for FastMCP servers:**
- `%APPDATA%\Claude\logs\mcp-server-chg-fastmcp (FastMCP).log`

### Solution 5: Use Static OAuth Client Info

If your FastMCP server doesn't support dynamic client registration, use pre-registered credentials:

```json
{
  "mcpServers": {
    "chg-fastmcp": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote@latest",
        "https://chg-fastmcp.fastmcp.app/mcp",
        "--static-oauth-client-info",
        "{\"client_id\":\"YOUR_CLIENT_ID\",\"client_secret\":\"YOUR_SECRET\"}"
      ]
    }
  }
}
```

### Solution 6: Test Connection Outside Claude Desktop

Verify the server works independently of Claude Desktop:

```powershell
# Test the connection directly
npx -p mcp-remote@latest mcp-remote-client https://chg-fastmcp.fastmcp.app/mcp --debug
```

This helps isolate whether the issue is:
- Server-side (FastMCP Cloud deployment)
- Client-side (Claude Desktop + Windows integration)
- Network-related (firewall, VPN, certificates)

## Prevention: Avoiding Future Issues

### 1. Single FastMCP Instance Per Claude Session

Windows coordination issues are exacerbated by multiple concurrent instances. If you need multiple FastMCP servers:

```json
{
  "mcpServers": {
    "fastmcp-server-1": {
      "command": "npx",
      "args": ["-y", "mcp-remote@latest", "https://server1.fastmcp.app/mcp", "3334"]
    },
    "fastmcp-server-2": {
      "command": "npx",
      "args": ["-y", "mcp-remote@latest", "https://server2.fastmcp.app/mcp", "3335"]
    }
  }
}
```

Assign different explicit ports (3334, 3335, etc.) to prevent coordination conflicts.

### 2. Node.js Version Requirements

Ensure you have Node.js 18 or higher installed:

```powershell
node --version
# Should output v18.0.0 or higher
```

**Important**: Claude Desktop uses your **system Node.js**, not versions managed by nvm or other version managers.

### 3. Windows Firewall Configuration

Ensure Node.js has inbound rules for OAuth callbacks:

```powershell
# Run as Administrator
New-NetFirewallRule -DisplayName "Node.js MCP OAuth" -Direction Inbound -Program "C:\Program Files\nodejs\node.exe" -Action Allow
```

### 4. Corporate VPN/Proxy Setup

If behind a corporate VPN or proxy, add CA certificates:

```json
{
  "mcpServers": {
    "chg-fastmcp": {
      "command": "npx",
      "args": ["-y", "mcp-remote@latest", "https://chg-fastmcp.fastmcp.app/mcp"],
      "env": {
        "NODE_EXTRA_CA_CERTS": "C:\\path\\to\\corporate-ca-bundle.crt",
        "HTTP_PROXY": "http://proxy.corp.com:8080",
        "HTTPS_PROXY": "http://proxy.corp.com:8080"
      }
    }
  }
}
```

## Understanding the Bug

The `coordinateAuth` function in `mcp-remote` implements a coordination mechanism to:
1. Prevent duplicate OAuth authorization windows
2. Allow multiple MCP clients to share authentication state
3. Reuse callback ports when possible

**On Windows**, this coordination fails because:
- Lockfile-based coordination is disabled due to platform differences in process management
- Stale or corrupted state files from crashed sessions aren't properly cleaned up
- Port reuse logic attempts to read `port` from a coordination object that may be `null`

**The specific error location:**
```javascript
// mcp-remote/dist/chunk-WSHBHZXM.js:14600
// Pseudocode representation:
const coordinationInfo = readLockfile(); // May return null on Windows
const port = coordinationInfo.port; // TypeError: Cannot read properties of null
```

## When to Report Upstream

If none of these workarounds resolve your issue, you may have encountered a new variant. Please report it to:

**FastMCP Cloud Issues:**
- If the server deploys but won't connect: https://fastmcp.com/support

**mcp-remote Package Issues:**
- If the OAuth coordination fails: https://github.com/geelen/mcp-remote/issues

**Claude Desktop Issues:**
- If Claude Desktop-specific: https://github.com/anthropics/claude-code/issues

## Additional Resources

- [MCP-Remote Troubleshooting Guide](https://kyle.czajkowski.tech/blog/troubleshooting-claude-s-remote-connection-to-mcp-servers)
- [MCP-Remote GitHub Issues](https://github.com/geelen/mcp-remote/issues/25)
- [FastMCP Documentation](https://gofastmcp.com/)
- [Model Context Protocol Spec](https://modelcontextprotocol.io/)

## Success Indicators

You'll know the issue is resolved when:

1. Claude Desktop logs show successful OAuth completion:
   ```
   [INFO] Successfully authenticated with chg-fastmcp.fastmcp.app
   [INFO] MCP server 'chg-fastmcp' connected successfully
   ```

2. You can invoke tools from your FastMCP server in Claude conversations

3. No `coordinateAuth` errors appear in `%APPDATA%\Claude\logs\`

## Quick Reference: Common Error Messages

| Error Message | Solution |
|---------------|----------|
| `Cannot read properties of null (reading 'port')` | Solution 1: Clear all state |
| `Authentication Error: Token exchange failed: HTTP 400` | Solution 1: Clear `~/.mcp-auth` |
| `spaces inside args aren't escaped` | Solution 2: Use env vars |
| `Port 3334 already in use` | Solution 3: Specify different port |
| `TransformStream is not defined` | Update Node.js to v18+ |
| `UNABLE_TO_VERIFY_LEAF_SIGNATURE` | Solution 4: Add `NODE_EXTRA_CA_CERTS` |

---

**Last Updated**: December 2025
**Tested With**: Claude Desktop (Windows), mcp-remote@latest, FastMCP Cloud
