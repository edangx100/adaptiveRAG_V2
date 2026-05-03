---
name: routing
description: Routes queries to appropriate data sources (vectordb, web_search, direct_llm) and selects collections to search. Use when analyzing user queries, determining search strategy, or when the user mentions routing, collections, or data source selection.
---

# Query Routing

## Instructions

Route queries using `route_query()` in `agents/query_agent.py`. Returns routing decision with data source and collections to search.

**Call once at pipeline start** with the original query. Do NOT re-route during retries.

**Default usage:**

```python
routing_decision = route_query(user_query)
route = routing_decision['route']  # "vectordb" | "web_search" | "direct_llm"
```

**Route handling:**

```python
if route == 'vectordb':
    collections = routing_decision.get('collections', [])
    docs = query_specific_collections(query, collections)

elif route == 'web_search':
    docs = search_web(query, num_results=5)

elif route == 'direct_llm':
    docs = []  # Skip retrieval
```

**Available collections** (vectordb only):
- `catalog`: Products, specs, pricing
- `faq`: Policies, shipping, returns
- `troubleshooting`: TechMart product support

**Strategies** (vectordb only):
- `single_collection`: One clear match
- `multi_collection`: 2-3 collections
- `comprehensive`: All collections (vague queries)

**Implementation:** `agents/query_agent.py`, uses structured outputs to enforce valid routes.

## Examples

### Example 1: Product query → vectordb, catalog

```python
# Input
result = route_query("What gaming laptops do you have?")

# Output
{
    "route": "vectordb",
    "strategy": "single_collection",
    "collections": ["catalog"],
    "reasoning": "Product inquiry about gaming laptops"
}
```

### Example 2: Web search query

```python
# Input
result = route_query("Windows 11 blue screen error 0x0000007E")

# Output
{
    "route": "web_search",
    "reasoning": "Current OS error requiring up-to-date information"
}
```

### Example 3: Multi-collection query

```python
# Input
result = route_query("Laptop not working, can I return it?")

# Output
{
    "route": "vectordb",
    "strategy": "multi_collection",
    "collections": ["troubleshooting", "faq"],
    "reasoning": "Combines technical issue with return policy question"
}
```

### Example 4: Direct LLM (no retrieval)

```python
# Input
result = route_query("Hello, thank you!")

# Output
{
    "route": "direct_llm",
    "reasoning": "Simple greeting, no retrieval needed"
}
```
