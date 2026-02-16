from agents.query_agent import QueryAgent
from agents.grader_agent import GraderAgent
from agents.generator_agent import GeneratorAgent
from agents.retrieval_agent import RetrievalAgent
from agents.web_search_agent import WebSearchAgent

AGENT_CLASSES = {
    "query_agent": QueryAgent,
    "grader_agent": GraderAgent,
    "generator_agent": GeneratorAgent,
    "retrieval_agent": RetrievalAgent,
    "web_search_agent": WebSearchAgent,
}
