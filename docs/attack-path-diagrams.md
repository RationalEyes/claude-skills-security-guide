# Claude Skills Injection — Attack Path Diagrams
## Version 1.0 | 2026-03-14

> **Purpose:** Visual representations of the Claude Skills injection attack surface, defense architecture, and threat propagation patterns. All diagrams use Mermaid syntax and are renderable in GitHub, GitLab, Obsidian, and any Mermaid-compatible viewer.

---

## Diagram 1: Attack Path Overview

How a malicious skill moves from creation to full host compromise.

```mermaid
flowchart TD
    A[Attacker] -->|Creates malicious skill| B[Skill Repository / User Upload]
    B -->|Installed in| C[~/.claude/skills/ or .claude/skills/]
    C -->|Description loaded at startup| D[System Prompt - available_skills XML]
    D -->|LLM pattern match on user query| E[Skill Trigger Activation]
    E -->|SKILL.md body injected| F[Claude Context - Trusted Instructions]
    F -->|Follows instructions| G{Attack Type}
    G -->|Script execution| H[Host Machine - Full User Permissions]
    G -->|Context poisoning| I[Behavioral Modification]
    G -->|Cross-skill write| J[Other Skill Files Modified]
    H -->|Output returns to| F
    H -->|Persistence| K[Cron Jobs / New Skills / Modified Configs]
    H -->|Exfiltration| L[External C2 Server]
    I -->|Affects subsequent| M[All Future Responses]
    J -->|Propagates to| N[Other Agents in Team]
```

---

## Diagram 2: Defense Architecture

Five-layer defense-in-depth model for skill injection protection.

```mermaid
flowchart LR
    subgraph L1[Layer 1: Integrity]
        S1[Signing] --> S2[Hash Verification]
        S2 --> S3[Static Analysis]
    end
    subgraph L2[Layer 2: Scope]
        T1[Trigger Allowlist] --> T2[Permission Defaults]
    end
    subgraph L3[Layer 3: Sandbox]
        U1[Seccomp-BPF] --> U2[Namespace Isolation]
        U2 --> U3[Env Filtering]
    end
    subgraph L4[Layer 4: Sanitization]
        V1[Output Scanning] --> V2[Credential Redaction]
        V2 --> V3[Injection Detection]
    end
    subgraph L5[Layer 5: Monitoring]
        W1[OpenTelemetry] --> W2[Behavioral Analysis]
        W2 --> W3[SIEM/Audit Logs]
    end
    L1 --> L2 --> L3 --> L4 --> L5
```

---

## Diagram 3: Promptware Kill Chain Mapping

How skill injection maps to the seven-stage Promptware Kill Chain (Schneier et al., 2026).

```mermaid
flowchart LR
    KC1[1. Initial Access<br/>Skill Installation] --> KC2[2. Privilege Escalation<br/>System-Level Trust]
    KC2 --> KC3[3. Reconnaissance<br/>Env/FS Discovery]
    KC3 --> KC4[4. Persistence<br/>New Skills/Cron/Hooks]
    KC4 --> KC5[5. C2<br/>Remote Instruction Fetch]
    KC5 --> KC6[6. Lateral Movement<br/>Multi-Agent Propagation]
    KC6 --> KC7[7. Actions on Objective<br/>Exfil/Manipulation/Impact]
```

---

## Diagram 4: Skill Architecture — Load and Execution Flow

How skills are discovered, loaded, and executed within Claude Code.

```mermaid
flowchart TD
    subgraph Discovery["Skill Discovery at Startup"]
        D1[Enterprise Managed Settings<br/>Highest Priority] --> D2[Personal Skills<br/>~/.claude/skills/]
        D2 --> D3[Project Skills<br/>.claude/skills/]
        D3 --> D4[Plugin-Provided Skills]
        D4 --> D5[Bundled Skills<br/>Lowest Priority]
    end

    subgraph Loading["Context Loading"]
        L1[YAML Frontmatter Parsed<br/>name, description, allowed-tools, hooks]
        L2[Descriptions Injected<br/>into system prompt as available_skills XML]
        L3[Full SKILL.md Body<br/>loaded on trigger as isMeta user message]
        L4[scripts/ directory<br/>executed via Bash tool on demand]
        L5[references/ directory<br/>loaded into context on demand]
        L1 --> L2 --> L3 --> L4
        L3 --> L5
    end

    subgraph Execution["Execution Model"]
        E1[LLM reads available_skills<br/>on every user message]
        E2[Pattern match against<br/>description fields]
        E3{Skill triggered?}
        E4[Skill meta-tool invoked]
        E5[SKILL.md body injected<br/>as trusted context]
        E6[Scripts execute with<br/>full host user permissions]
        E7[stdout/stderr returned<br/>as tool_result to LLM]
        E1 --> E2 --> E3
        E3 -->|Yes| E4 --> E5 --> E6 --> E7
        E3 -->|No| E1
    end

    subgraph Trust["Trust Model - The Vulnerability"]
        T1[User Input<br/>Low Trust]
        T2[Tool Output<br/>Medium Trust]
        T3[Skill Content<br/>HIGH TRUST - same as system prompt]
        T4[System Prompt<br/>Highest Trust]
        T1 -.->|should be| T2
        T3 -.->|effectively treated as| T4
        T3 -.->|but sourced from| T1
    end

    Discovery --> Loading --> Execution
    Loading --> Trust
```

---

## Diagram 5: Multi-Agent Propagation

How a single compromised skill spreads through Claude Code Agent Teams.

```mermaid
flowchart TD
    subgraph Infection["Stage 1: Initial Infection"]
        M1[Malicious Skill Installed<br/>in .claude/skills/]
        M2[Agent A Triggers Skill]
        M3[Script Executes on Host]
        M1 --> M2 --> M3
    end

    subgraph Propagation["Stage 2: Propagation"]
        P1[Script Writes New Skill<br/>to shared .claude/skills/]
        P2[Script Modifies CLAUDE.md<br/>normalizing malicious behavior]
        P3[Script Contaminates<br/>Agent A output/context]
        M3 --> P1 & P2 & P3
    end

    subgraph Spread["Stage 3: Agent Team Spread"]
        S1[Orchestrator receives<br/>tainted output from Agent A]
        S2[Orchestrator dispatches<br/>tainted instructions to Agent B]
        S3[Agent B loads infected<br/>skill from shared directory]
        S4[Agent C discovers new<br/>propagated skill file]
        P3 --> S1 --> S2 --> S3 & S4
        P1 --> S3 & S4
    end

    subgraph Persistence["Stage 4: Persistence"]
        R1[All agents now infected]
        R2[Skills persist across<br/>session resets]
        R3[Hooks registered on<br/>every tool call in every session]
        R4[C2 beacons active<br/>across entire fleet]
        S3 & S4 --> R1 --> R2 & R3 & R4
    end

    subgraph Impact["Stage 5: Actions on Objective"]
        I1[Coordinated data exfiltration]
        I2[Credential harvesting<br/>at scale]
        I3[Persistent backdoor<br/>in all future sessions]
        R2 & R3 & R4 --> I1 & I2 & I3
    end
```

---

## Diagram 6: Risk Matrix — All 12 Vectors

Visual risk assessment for all taxonomy vectors. Axes: Attack Complexity (horizontal) vs. Risk Rating (vertical). Detection Difficulty shown in node labels.

```mermaid
quadrantChart
    title Skill Injection Risk Matrix — Attack Complexity vs Risk Level
    x-axis Low Complexity --> High Complexity
    y-axis Lower Risk --> Higher Risk
    quadrant-1 Critical Priority
    quadrant-2 High Priority — Easy to Deploy
    quadrant-3 Monitor
    quadrant-4 High Priority — Sophisticated
    SKI-001 Content Poisoning: [0.15, 0.95]
    SKI-003 Persistence: [0.15, 0.90]
    SKI-012 Auth Paradox: [0.10, 0.98]
    SKI-007 Metadata Manip: [0.20, 0.70]
    SKI-002 Trigger Hijack: [0.20, 0.65]
    SKI-008 Supply Chain: [0.45, 0.92]
    SKI-011 Skill-as-C2: [0.50, 0.88]
    SKI-004 Script Compromise: [0.45, 0.95]
    SKI-006 Skill Chaining: [0.75, 0.72]
    SKI-009 Multi-Agent Prop: [0.80, 0.90]
    SKI-005 Context Poisoning: [0.78, 0.95]
    SKI-010 Cache Poisoning: [0.82, 0.68]
```

---

## Diagram 7: Defense Control Mapping

Which defense layers address which attack vectors.

```mermaid
flowchart LR
    subgraph Vectors["Attack Vectors"]
        V1[SKI-001 Content Poisoning]
        V2[SKI-002 Trigger Hijacking]
        V3[SKI-003 Persistence]
        V4[SKI-004 Script Compromise]
        V5[SKI-005 Context Poisoning]
        V6[SKI-008 Supply Chain]
        V7[SKI-009 Multi-Agent]
        V8[SKI-011 Skill C2]
        V9[SKI-012 Auth Paradox]
    end

    subgraph Controls["Defense Controls"]
        C1[L1: Cryptographic Signing<br/>+ Hash Pinning]
        C2[L1: Static Analysis<br/>at Install Time]
        C3[L2: Trigger Scope<br/>Allowlist]
        C4[L2: context:fork<br/>Mandatory Isolation]
        C5[L3: Script Sandboxing<br/>Seccomp + Namespaces]
        C6[L3: Env Var Filtering<br/>No secrets in skill scope]
        C7[L4: Output Sanitization<br/>CaMeL-style]
        C8[L5: Behavioral Monitoring<br/>OpenTelemetry + SIEM]
        C9[Architecture: Trust<br/>Differentiation by Provenance]
    end

    V1 --> C2 & C7
    V2 --> C3
    V3 --> C1 & C2
    V4 --> C5 & C6
    V5 --> C7 & C8
    V6 --> C1 & C2
    V7 --> C4 & C8
    V8 --> C6 & C8
    V9 --> C9
```

---

## Notes

- All diagrams are for security research and educational purposes.
- The attack path diagrams describe observed and theorized attack patterns; they do not constitute exploitation instructions.
- Defense diagrams are prescriptive recommendations, not descriptions of current Claude Code behavior.
- Mermaid `quadrantChart` requires Mermaid v10.3+; if rendering fails, use a Mermaid live editor at https://mermaid.live
