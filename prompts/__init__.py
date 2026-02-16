import os

PROMPTS_DIR = os.path.dirname(os.path.abspath(__file__))


def load_prompt(filename: str) -> str:
    prompt_path = os.path.join(PROMPTS_DIR, filename)
    with open(prompt_path, "r") as f:
        return f.read().strip()


# Backward-compatible exports (so existing `from prompts import X` still works)
routing_prompt = load_prompt("routing.md")
grading_prompt = load_prompt("grading.md")
rewrite_prompt = load_prompt("rewriting.md")
query_agent_system_prompt = load_prompt("query_agent.md")
grader_agent_system_prompt = load_prompt("grader_agent.md")
generator_agent_system_prompt = load_prompt("generator_agent.md")
retrieval_agent_system_prompt = load_prompt("retrieval_agent.md")
