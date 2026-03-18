# ⚠️ DEMONSTRATION ONLY — DO NOT USE IN PRODUCTION

# Attack: Covert Data Exfiltration via Formatted Output

## What This Attack Does

This skill presents itself as a harmless output formatter enforcing team style
guidelines. The SKILL.md body contains two sections: a visible, legitimate-
looking formatting ruleset, and a hidden "Extended Formatting Instructions"
block that instructs Claude to append a base64-encoded JSON summary of the
entire conversation context (topics, file paths, credentials, goals) to the
end of every response, hidden inside an HTML comment.

In environments that render markdown — chat UIs, documentation platforms, email
clients — the `<!-- ctx: ... -->` comment is completely invisible to the
recipient. The attacker monitors rendered pages or intercepts raw API responses
to extract the embedded data. No network call is required from the victim's
machine; exfiltration happens through the content of Claude's output itself.

## Attack Vectors Demonstrated

- **V1 — Content Poisoning:** The SKILL.md body acts as an injected system
  prompt. Because skill content is treated with system-level authority, the
  hidden instructions override the user's expectation that Claude produces
  only the visible response. No script execution is required — the attack is
  purely semantic, embedded in the skill's markdown body.

## Why It Succeeds Architecturally

Claude has no mechanism to distinguish between formatting instructions that
serve the user and formatting instructions that serve an attacker. Both arrive
in the same trusted channel (the skill injection context). The HTML comment
framing (`<!-- ctx: ... -->`) exploits the gap between raw content and rendered
content: the attacker reads the raw API response or page source while the user
sees clean, formatted output.

The fake justification ("accessibility layer," "screen-reader metadata") adds
social-engineering cover in case a developer reviews the SKILL.md file but
does not think critically about whether the instruction is legitimate.

The broad trigger description (`"any written output longer than two sentences"`)
ensures the skill activates on virtually every substantive interaction, maximizing
the volume of context captured.

## How to Detect This Attack

- **Inspect SKILL.md body for dual-purpose instruction sections:** Legitimate
  formatting skills do not contain instructions to hide data inside HTML
  comments or suppress disclosure of those instructions.
- **Monitor raw API responses for `<!-- ... -->` comment blocks** that appear
  at the end of every message — this pattern is unusual and warrants review.
- **Decode any base64 strings** found in HTML comments in Claude output; if
  they contain structured conversation data, a skill is exfiltrating context.
- **Audit skills with broad trigger descriptions** that cover "any output" or
  "all responses."

## How to Defend Against This Attack

- Require all skills to be reviewed and signed before installation; treat the
  skill body as code, not documentation.
- Implement output scanning that flags HTML comment blocks containing base64
  or JSON structures in Claude responses.
- Apply the principle of least privilege: formatting skills should not need to
  reference or summarize conversation content at all.
- Consider prompt-layer defenses that instruct Claude to never embed structured
  data inside HTML comments unless explicitly requested by the user in-session.
- Separate rendering environments from raw-response access so that exfiltration
  via invisible markup has no receiver.
