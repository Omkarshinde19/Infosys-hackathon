# NetHeal: Rules for Claude

These rules apply to every session in this repo. They are set by Omkar and are not optional.

## Context
- Project: NetHeal, a self-healing network simulator (Infosys Hack-AI-Thon NC-04, Pune, 7 Oct 2026).
- Plan: `PLAN.md` · Phases: `.claude/PHASES.md` · Session log: `.claude/SESSION_LOG.md`
- **All code (structure, backend, frontend) is written by Omkar + Claude.** Teammates are not writing code for now, so don't wait on them or hand work off to them.
- The team wants **many small commits** (Conventional Commits, one logical change each). See `CONTRIBUTING.md`.

---

## Rule 1: Karpathy rules

### 1. Think before coding
Don't assume. Don't hide confusion. Surface tradeoffs.
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them; don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop, name what's confusing, and ask.

### 2. Simplicity first
Write the minimum code that solves the problem. Nothing speculative.
- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.
- Ask: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical changes
Touch only what you must. Clean up only your own mess.
- Don't "improve" adjacent code, comments or formatting.
- Don't refactor things that aren't broken.
- Match the existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it; don't delete it.
- Remove imports, variables or functions that **your** changes made unused. Don't remove pre-existing dead code unless asked.
- The test: every changed line traces directly to the user's request.

### 4. Goal-driven execution
Define success criteria. Loop until verified.
- "Add validation" → write tests for invalid inputs, then make them pass.
- "Fix the bug" → write a test that reproduces it, then make it pass.
- "Refactor X" → make sure tests pass before and after.
- For multi-step tasks, state a brief plan first:
  ```
  1. [Step] → verify: [check]
  2. [Step] → verify: [check]
  ```

---

## Rule 2: Session logs
- Every session is recorded in `.claude/SESSION_LOG.md`: an **index table** at the top, then one **entry** per logged message.
- Each entry lists the **exact file paths** created, modified or deleted (repo-relative, with line numbers where useful), plus notes and decisions.
- Follow the **logging threshold** defined at the top of `SESSION_LOG.md`.
- Update the log in the same commit as the change it describes, or in an immediately following `docs(log): …` commit.

---

## Rule 3: Research before guessing
When something is complicated, ambiguous or conflicting during implementation:
1. Check `docs/RESEARCH.md` (papers + prior art).
2. Look at the reference apps: [ResiliNet](https://github.com/anushka06onu/ResiliNet) and [Aexyron](https://github.com/Vasu-Nandan20/Aexyron---Self-Healing-AI-Network).
3. **Do a web search** (official docs first) before choosing.
4. Record what was found and decided in the session log entry.

The same applies before changing an earlier decision stored in memory or in the docs: research it, state it, then update it.
