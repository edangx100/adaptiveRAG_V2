You are evaluating the relevance of a retrieved document to a user query.

Query: {query}

Document:
{document}

Instructions:
- Mark as "yes" if the document contains information that helps answer the query, even if:
  - The SKU number differs
  - The model variant or version name (e.g., "Wireless" vs. base model) is different but from the same product family
- Mark as "no" only if the product in the document is clearly a different, unrelated product line.
- Focus on the product family and core features described, not exact SKUs or small variant descriptors.
- Give brief reasoning for your assessment.
Evaluate the document relevance.