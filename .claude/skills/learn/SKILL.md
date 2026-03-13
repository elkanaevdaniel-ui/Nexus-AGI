---
name: learn
description: >
  Learn and document unfamiliar code through ASCII diagrams, interactive explanations,
  and spaced repetition. Use this skill when the user says "/learn", "explain this code",
  "how does this work", "teach me", "diagram this", "I don't understand", or any request
  to understand a codebase or module.
---

# Learning Mode

## Techniques

### 1. ASCII Architecture Diagrams
When asked to explain a module, ALWAYS start with an ASCII diagram:
```
+---------------+     +----------------+     +---------------+
|  Telegram     |---->|  LLM Router    |---->|  Provider     |
|  Bot Input    |     |  (port 5100)   |     |  (Anthropic/  |
+---------------+     +----------------+     |  OpenRouter)  |
                             |               +---------------+
                             v
                      +----------------+
                      | Cost Tracker   |
                      | (port 5200)    |
                      +----------------+
```

### 2. Explain the WHY, not just the WHAT
- Don't just describe what code does — explain WHY it was written this way
- What problem does it solve? What alternatives were considered?
- What would break if this code was removed?

### 3. Interactive Knowledge Gaps
After explaining something, ask:
- "What part is still unclear?"
- "Can you explain back to me how [X] works?"
- "What would happen if [edge case]?"

### 4. Generate HTML Presentations
For complex modules, create an interactive HTML file with:
- Architecture diagram (SVG or ASCII)
- Key function explanations with collapsible details
- Data flow walkthrough
- Common gotchas and edge cases

### 5. Spaced Repetition
After a learning session, create a quick-reference card:
```markdown
## [Module Name] Quick Reference
- **Purpose**: [one sentence]
- **Key files**: [list]
- **Data flow**: [A -> B -> C]
- **Common mistakes**: [list]
- **Last reviewed**: [date]
```
Save these to docs/quick-ref/ for future sessions.

