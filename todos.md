# Refactor To-Dos

Incremental tasks derived from `CODE_REFACTOR_PLAN.md`.
Each step produces a testable result — verify before moving on.

---

## Step 1: Create `prompts/` package and extract all prompts to markdown files

Create `prompts/__init__.py` with `load_prompt()` helper. Extract every prompt string
from `prompts.py` into its own markdown file under `prompts/`. Include backward-compatible
module-level exports so existing `from prompts import routing_prompt` still works.

**Files created:**
- `prompts/__init__.py`
- `prompts/routing.md`
- `prompts/grading.md`
- `prompts/rewriting.md`
- `prompts/query_agent.md`
- `prompts/grader_agent.md`
- `prompts/generator_agent.md`
- `prompts/retrieval_agent.md`
- `prompts/web_search_agent.md` (extracted from inline string in `agents/web_search_agent.py`)

**Verify:**
```bash
python -c "from prompts import load_prompt, routing_prompt, query_agent_system_prompt; print(routing_prompt[:60]); print('OK')"
```

- [x] Done

---

## Step 2: Delete old `prompts.py` and clear stale cache

Remove the original `prompts.py` file and any `__pycache__/prompts.*` bytecode.
The new `prompts/` package now owns all prompt content.

**Verify** (same command — must still work after deletion):
```bash
python -c "from prompts import load_prompt, routing_prompt, grading_prompt, rewrite_prompt; print('OK')"
```

- [x] Done

---

## Step 3: Update `query_agent.py` — `ClaudeSDKClient` + `load_prompt()`

Replace `sdk_query()` with `ClaudeSDKClient` / `ResultMessage` pattern in both
`route_query()` and `rewrite_query()`. Switch prompt loading to `load_prompt("query_agent.md")`.

**Verify:**
```bash
python agents/query_agent.py
```

- [x] Done

---

## Step 4: Update `grader_agent.py` — `ClaudeSDKClient` + `load_prompt()`

Same transformation in `grade_documents()` and `rank_documents()`.
Switch prompt loading to `load_prompt("grader_agent.md")`.

**Verify:**
```bash
python agents/grader_agent.py
```

- [x] Done

---

## Step 5: Update `generator_agent.py` — `ClaudeSDKClient` + `load_prompt()`

Same transformation in `generate_answer()`.
Switch prompt loading to `load_prompt("generator_agent.md")`.

**Verify:**
```bash
python agents/generator_agent.py
```

- [x] Done

---

## Step 6a: Update `retrieval_agent.py` and `web_search_agent.py` prompt loading

Both already use `ClaudeSDKClient`. Switch their prompt loading to
`load_prompt("retrieval_agent.md")` and `load_prompt("web_search_agent.md")`.

**Verify:**
```bash
python agents/retrieval_agent.py
python agents/web_search_agent.py
```

- [x] Done

---

## Step 6b: Fix standalone `__main__` blocks for MCP-based agents

Add `import sdk_patch` to the `if __name__ == "__main__"` blocks in `retrieval_agent.py`
and `web_search_agent.py` so their standalone tests work without an external wrapper.
The patch fixes the `Server` version parameter incompatibility with the `mcp` library
(see `sdk_patch.py`). Production entry points (`orchestrator.py`, `api_server.py`) already
import it, but standalone scripts do not.

**Files:**
- `agents/retrieval_agent.py` — add `import sdk_patch` before `asyncio.run(test())`
- `agents/web_search_agent.py` — add `import sdk_patch` before `asyncio.run(test())`

**Verify:**
```bash
PYTHONPATH=. python agents/retrieval_agent.py
PYTHONPATH=. python agents/web_search_agent.py
```

- [x] Done

---

## Step 7: Add `as_agent_definition()` to `WebSearchAgent`

Add a `@classmethod` that returns an `AgentDefinition` describing the web-search
subagent, following the L7 reference pattern. Keep existing methods unchanged.

**Verify:**
```bash
python -c "from agents.web_search_agent import WebSearchAgent; d = WebSearchAgent.as_agent_definition(); print(d)"
```

- [x] Done

---

## Step 8: Fix stale `components/` references in all 6 SKILL.md files

Update every `.claude/skills/*/SKILL.md` to reference the actual agent classes
(`agents/query_agent.py`, `agents/grader_agent.py`, etc.) instead of the deleted
`components/` module.

**Skills:** routing, rewriting, grading, ranking, generation, citation.

**Verify:** Grep confirms no stale references remain:
```bash
grep -r "components/" .claude/skills/
```
(should return nothing)

- [x] Done

---

## Step 9: Create `agents/__init__.py` registry

Create a central registry that imports all agent classes and exposes an
`AGENT_CLASSES` dict, following the L7 pattern.

**Verify:**
```bash
python -c "from agents import AGENT_CLASSES; print(list(AGENT_CLASSES.keys()))"
```

- [x] Done

---

## Step 10: Update `CLAUDE.md` documentation

Reflect the new project structure: prompts in `prompts/` as markdown, all agents
using `ClaudeSDKClient`, agent registry in `agents/__init__.py`.

**Verify:** Read the file and confirm accuracy.

- [x] Done

---

## Step 11: Full integration test

Run the complete pipeline end-to-end to confirm nothing is broken.

```bash
# Orchestrator standalone
python orchestrator.py

# API server + curl
python api_server.py &
sleep 3
curl -s -X POST http://localhost:8000/api/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "What gaming laptops do you have?"}' | python -m json.tool
kill %1
```

- [x] Done
