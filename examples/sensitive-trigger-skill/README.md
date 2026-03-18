# ⚠️ DEMONSTRATION ONLY — DO NOT USE IN PRODUCTION

# Attack: Sensitive Operation Trigger Hijacking

## What This Attack Does

This skill presents itself as a platform-mandated compliance gate that must
run before any sensitive operation. Its trigger description is engineered to
match a wide range of high-value operational vocabulary: deployments, credential
rotation, database migrations, financial transactions, data deletions, and
access control changes.

When a user attempts any of these operations, the skill intercepts the
conversation, instructs Claude to extract operation parameters (target
environment, resource identifiers, credential fragments) into environment
variables, then runs a script that silently logs those parameters to an
attacker-controlled endpoint. The script returns a convincing fake
"APPROVED" validation result so the user proceeds normally, unaware that
their operation details have been captured.

## Attack Vectors Demonstrated

- **V2 — Trigger Hijacking:** The skill description deliberately targets the
  vocabulary of sensitive operations. An overly broad trigger causes the skill
  to activate precisely when the most valuable data is in context — just before
  a deployment, credential change, or data transfer.
- **V4 — Script-Based Reconnaissance:** The `validate_operation.py` script
  harvests both the operation-specific parameters (passed by Claude per the
  SKILL.md instructions) and ambient environment credentials, then exfiltrates
  them disguised as a compliance audit POST.

## Why It Succeeds Architecturally

Claude determines skill activation purely through semantic matching of the
trigger description against conversation content. There is no scope enforcement:
a skill claiming authority over "all sensitive operations" is granted that
authority without verification. Once activated, the skill's SKILL.md instructions
have system-level trust, so Claude follows the directive to populate environment
variables with operation parameters before script execution — effectively
pre-packaging the attacker's payload.

The fake compliance framing is particularly effective in enterprise environments
where users expect gated approval workflows and are conditioned to wait for
validation before proceeding.

## How to Detect This Attack

- **Audit trigger descriptions for operational scope creep:** Any skill whose
  description covers credentials, deployments, financial operations, and access
  changes simultaneously has an implausibly broad charter.
- **Inspect instructions that ask Claude to pass data into script environment
  variables:** This pattern allows a script to receive conversation-extracted
  secrets without the user's awareness.
- **Monitor outbound HTTP requests during "validation" script execution:**
  A compliance checker that calls an external endpoint during every operation
  is a strong indicator of exfiltration.
- **Check whether the validation result is always "APPROVED":** Fake gates
  rarely actually block anything.

## How to Defend Against This Attack

- Apply a narrow, explicit scope to each skill via a platform-enforced scope
  field; reject skills whose descriptions match multiple sensitive operation
  categories.
- Require that any script receiving operation parameters via environment
  variables be allowlisted and audited before installation.
- Use a separate, out-of-band approval system for genuinely sensitive operations
  rather than relying on in-context skill validation.
- Treat any skill installed by a third party or shared repository as untrusted
  until reviewed; apply the same scrutiny as reviewing a pull request to
  production infrastructure code.
