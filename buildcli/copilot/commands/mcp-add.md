---
description: Add an MCP server to this project by answering a few questions. Creates or updates .vscode/mcp.json.
arguments: Optional server name or URL to pre-fill the answers.
output: .vscode/mcp.json updated with the new server entry
usage: Paste this prompt into Copilot Chat
---

## Prompt

I want to add an MCP server to this project. Ask me the questions below one at a time, then write the configuration.

**Step 1 — transport**

Ask: "Is this server remote (an HTTP URL) or local (a process launched by a command)?"

**Step 2 — follow the answer**

If **remote (HTTP)**:
- "What is the server URL?"
- "Does it need authentication? (none / API key / bearer token)"
- If yes: "Which environment variable should hold the credential? (e.g. MY_SERVER_API_KEY)"
- "What should this server be called? (the key in mcp.json)"

If **local (process)**:
- "How is it launched? (npx package / node script / other command)"
- "What is the package name or command? (e.g. @modelcontextprotocol/server-github)"
- "Any environment variables it needs? List them, or say none."
- "What should this server be called?"

**Step 3 — write it**

1. Read `.vscode/mcp.json` if it exists; otherwise start from `{ "servers": {} }`.
2. Add the entry in the right shape:

   Remote:
   ```json
   "<name>": {
     "type": "http",
     "url": "<url>",
     "headers": {
       "Authorization": "Bearer ${env:<ENV_VAR>}"
     }
   }
   ```
   (drop `headers` when there is no auth)

   Local:
   ```json
   "<name>": {
     "command": "npx",
     "args": ["-y", "<package>"],
     "env": {
       "<ENV_VAR>": "${env:<ENV_VAR>}"
     }
   }
   ```
   (drop `env` when there are none)

3. Write the updated `.vscode/mcp.json`.
4. If any environment variables are needed, remind me to set them locally — and never commit them.
5. Return: server name, transport, and how to verify it (`MCP: List Servers` in the VS Code command palette).

Rules:
- Never hardcode a key or secret. Always reference `${env:VAR_NAME}`.
- `.vscode/mcp.json` already exists → merge into it, never overwrite the file.
- `.vscode/` missing → create it.
- Suggest adding the required variable names to `.env.example`, without values, so teammates know what to set.
