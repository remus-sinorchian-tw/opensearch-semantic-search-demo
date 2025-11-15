import ollama
import json
from opensearchpy import OpenSearch
from neo4j import GraphDatabase

# --- 1. Connect to Services ---
os_client = OpenSearch(hosts=[{'host': 'localhost', 'port': 9200}], use_ssl=False, verify_certs=False, ssl_assert_hostname=False)
neo4j_driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password123"))
ollama_client = ollama.Client()

EMBEDDING_MODEL = "nomic-embed-text"
LLM_MODEL = "llama3"

# --- 2. The NLP "Query Analysis" Step ---
def analyze_query_with_llm(user_query):
    print(f"--- Analyzing Query: '{user_query}' ---")
    prompt = f"""
    You are a query analysis expert for a personal research assistant.
    Analyze the user's query about their books and extract:
    1. 'semantic_query': A string that captures the core semantic meaning, focusing on the content of the books.
    2. 'keywords': A list of critical keywords (like book titles, character names, specific terms).
    3. 'kg_entities': A list of entities (people, locations, concepts, book titles) to search in the Knowledge Graph.

    User Query: "{user_query}"

    Respond with ONLY a valid JSON object.

    Example:
    Query: "Find passages in 'Dune' about 'ecology' and tell me who the author is."
    JSON:
    {{
      "semantic_query": "passages discussing ecology",
      "keywords": ["Dune", "ecology"],
      "kg_entities": ["Dune"]
    }}
    """

    response = ollama_client.chat(
        model=LLM_MODEL,
        messages=[{'role': 'user', 'content': prompt}],
        options={'temperature': 0.0},
        format="json"
    )
    analysis = json.loads(response['message']['content'])
    print(f"Query Analysis:\n{json.dumps(analysis, indent=2)}")
    return analysis

# --- 3. The Retrieval Steps (KG + OpenSearch) ---
def search_knowledge_graph(entities):
    print(f"--- Searching KG for: {entities} ---")
    if not entities:
        return "No KG entities found to search."

    # This query finds the entities and any 1-hop connections
    query = f"""
    MATCH (e) WHERE e.name IN {json.dumps(entities)} OR e.title IN {json.dumps(entities)}
    OPTIONAL MATCH path = (e)-[]-(related)
    RETURN e, path
    LIMIT 10
    """
    with neo4j_driver.session(database="neo4j") as session:
        results = session.run(query)
        findings = []
        for record in results:
            path = record["path"]
            if path:
                nodes = [n.get('name') or n.get('title') for n in path.nodes]
                rel = path.relationships[0].type
                findings.append(f"Fact: ({nodes[0]}) -[{rel}]-> ({nodes[1]})")
            else:
                e = record["e"]
                findings.append(f"Entity: ({e.get('name') or e.get('title')})")

        if not findings:
            return "No facts found in KG for these entities."

    print(f"KG Findings:\n{findings}")
    return "\n".join(findings)

def search_opensearch_hybrid(semantic_query, keywords):
    print(f"--- Running Hybrid Search on Book Chunks ---")

    vector = ollama_client.embeddings(model=EMBEDDING_MODEL, prompt=semantic_query)['embedding']

    query = {
      "size": 3, # Get top 3 matching chunks
      "query": {
        "hybrid": {
          "queries": [
            {
              "match": {
                "content": {
                  "query": " ".join(keywords),
                  "boost": 1.0 
                }
              }
            },
            {
              "knn": {
                "content_vector": {
                  "vector": vector,
                  "k": 3,
                  "boost": 1.0
                }
              }
            }
          ]
        }
      }
      # To use RRF, you would need to create a search pipeline in OpenSearch
    }

    response = os_client.search(index="book_chunks", body=query)
    # *** THIS IS THE KEY CHANGE ***
    # We now return the content *and* the source
    docs = [
        f"Source: {hit['_source']['source_book']}\nContent: {hit['_source']['content']}\n---" 
        for hit in response["hits"]["hits"]
    ]

    if not docs:
        return "No relevant passages found in your books."

    print(f"OpenSearch Findings:\n{docs}")
    return "\n".join(docs)

# --- 4. The Synthesis Step (RAG) ---
def synthesize_answer(user_query, kg_findings, os_findings):
    print("--- Synthesizing Final Answer ---")
    prompt = f"""
    You are a 'Personal Research Assistant'.
    Your job is to answer the user's query about their books based *only* on the context provided.
    Do not make anything up.

    User's Query: "{user_query}"

    --- Context from Knowledge Graph (High-level facts) ---
    {kg_findings}

    --- Context from Book Passages (OpenSearch) ---
    {os_findings}

    ---

    Your final, synthesized answer for the user:
    """

    response = ollama_client.chat(
        model=LLM_MODEL,
        messages=[{'role': 'user', 'content': prompt}],
        stream=True
    )

    final_answer = ""
    print("\n--- YOUR ASSISTANT'S ANSWER ---")
    for chunk in response:
        content = chunk['message']['content']
        print(content, end='', flush=True)
        final_answer += content
    print("\n---------------------------------")
    return final_answer

# --- 5. Run the Demo ---
if __name__ == "__main__":
    # Edit this query to match your books and KG!
    my_query = "Find passages in 'Dune' about 'ecology' and tell me who the author is."

    # Step 1: Analyze
    analysis = analyze_query_with_llm(my_query)

    # Step 2: Retrieve
    kg_results = search_knowledge_graph(analysis['kg_entities'])
    os_results = search_opensearch_hybrid(analysis['semantic_query'], analysis['keywords'])

    # Step 3: Synthesize
    synthesize_answer(my_query, kg_results, os_results)

    neo4j_driver.close()