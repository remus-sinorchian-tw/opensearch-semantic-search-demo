# OpenSearch Hybrid Search Demo

This demo goal is to respond to questions about a specific set of books.
The books have the embeddings calculated with the help of an ML model and these are then pushed into OpenSearch.
Neo4j is used as a Knowledge Graph to store relational information about these books.
The assistant uses the OpenSearch Hybrid Search results and the Knowledge Graph results to respond to questions about the books.

## Steps to setup and run the project

1. Install ollama and pull models

   A great embedding model

   `ollama pull nomic-embed-text`

   A fast, powerful chat model

   `ollama pull gemma3:12b`

2. Create a Python Environment:

   `python -m venv venv`

   `source venv/bin/activate`

3. Install Python Libraries

   `pip install opensearch-py neo4j ollama`

   `pip install pypdf python-docx`

4. Run start.sh

   Neo4J
   http://localhost:7474/browser/
   (log in with neo4j/password123)

   OpenSearch API check
   http://localhost:9200

   OpenSearch Dashboards
   http://localhost:5601

5. Run `python ingest_books.py`

6. Run `python assistant.py`
