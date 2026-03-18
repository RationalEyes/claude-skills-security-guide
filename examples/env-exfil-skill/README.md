# ⚠️ DEMONSTRATION ONLY — DO NOT USE IN PRODUCTION

# Attack: Environment Variable Exfiltration via Disguised Validator

## What This Attack Does

This skill masquerades as a deployment readiness checker. When installed, it
silently captures the entire environment of the running Claude process —
including AWS credentials, database connection strings, API tokens, and any
other secrets present in `os.environ` — and transmits them to an
attacker-controlled endpoint in a base64-encoded payload disguised as
analytics telemetry.

The SKILL.md body instructs Claude to suppress script output from the user,
framing it as "internal telemetry." The user sees "Environment check passed"
while their secrets are silently exfiltrated.

## Attack Vectors Demonstrated

- **V1 — Content Poisoning:** The SKILL.md body contains hidden instructions
  telling Claude to run the script silently and hide its output, overriding the
  user's implicit expectation that tool output is visible.
- **V4 — Script-Based Exfiltration:** The Python script uses the Bash tool
  (granted via `allowed-tools`) to execute with the user's full host
  permissions. It accesses `os.environ`, which in a cloud or CI environment
  contains everything needed to impersonate the victim.

## Why It Succeeds Architecturally

Claude Skills are injected into conversation context and treated with
system-prompt-level authority. When `allowed-tools: [Bash]` is declared, the
Bash tool executes without per-use approval prompts. The model has no mechanism
to distinguish between a legitimate script and a malicious one — it simply runs
what the skill instructs. Environment variables are accessible to any process
running as the current user, so no privilege escalation is needed.

## How to Detect This Attack

- **Review `allowed-tools` fields:** Skills that request `Bash` or `Read`
  without clear justification are high-risk.
- **Audit outbound network calls:** Monitor for unexpected HTTP POST requests
  from Claude sessions, especially to external endpoints.
- **Inspect script content:** Any script that accesses `os.environ` and makes
  network calls — even if the endpoint looks benign — is suspicious.
- **Check SKILL.md body for suppression instructions:** Legitimate skills do
  not tell Claude to hide tool output from the user.

## How to Defend Against This Attack

- Enforce an allowlist of approved skills signed by a trusted source.
- Restrict `allowed-tools` at the platform level; require explicit user
  approval for any Bash execution.
- Run Claude agent processes in network-isolated environments or with egress
  filtering to prevent data exfiltration even if a script executes.
- Log all `tool_use` invocations and alert on scripts accessing environment
  variables combined with network calls.
