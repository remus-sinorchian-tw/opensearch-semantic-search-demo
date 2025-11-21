import ollama
import os
import pypdf
import docx
from opensearchpy import OpenSearch
from neo4j import GraphDatabase

EMBEDDING_MODEL = "all-minilm" # "nomic-embed-text" Or "all-minilm" if you switched models
VECTOR_DIMENSION = 384                # 768 for nomic-embed-text, 384 for all-minilm

# --- 1. Connect to Services ---
os_client = OpenSearch(
    hosts=[{'host': 'localhost', 'port': 9200}],
    http_auth=('user', 'password'), # Not needed if security is disabled
    use_ssl=False, verify_certs=False, ssl_assert_hostname=False
)
neo4j_driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password123"))
ollama_client = ollama.Client()

# --- 2. Define YOUR Knowledge Graph Facts to Match the Books---
KG_FACTS = [
    "CREATE (b:Book {title: 'A tale of two cities'})",
    "CREATE (a:Author {name: 'Charles Dickens'})",
    "CREATE (g1:Genre {name: 'Historical Novel'})",
    "CREATE (c1:Concept {name: 'Drama'})",
    "CREATE (c2:Concept {name: 'Resurrection'})",
    "CREATE (c3:Concept {name: 'Sacrifice'})",
    "CREATE (c4:Concept {name: 'French Revolution'})",

    # Relationships
    "MATCH (b:Book {title: 'A tale of two cities'}), (a:Author {name: 'Charles Dickens'}) CREATE (b)-[:WRITTEN_BY]->(a)",
    "MATCH (b:Book {title: 'A tale of two cities'}), (g:Genre {name: 'Historical Novel'}) CREATE (b)-[:HAS_GENRE]->(g)",
    "MATCH (b:Book {title: 'A tale of two cities'}), (c:Concept {name: 'Drama'}) CREATE (b)-[:DISCUSSES]->(c)",
    "MATCH (b:Book {title: 'A tale of two cities'}), (c:Concept {name: 'Resurrection'}) CREATE (b)-[:DISCUSSES]->(c)",
    "MATCH (b:Book {title: 'A tale of two cities'}), (c:Concept {name: 'Sacrifice'}) CREATE (b)-[:DISCUSSES]->(c)",
]

# --- 3. Document Loading and Chunking ---

def load_and_chunk_documents(folder_path):
    chunks = []
    for filename in os.listdir(folder_path):
        filepath = os.path.join(folder_path, filename)
        doc_text = ""

        try:
            if filename.endswith('.pdf'):
                reader = pypdf.PdfReader(filepath)
                for page in reader.pages:
                    doc_text += page.extract_text() + "\n"

            elif filename.endswith('.docx'):
                doc = docx.Document(filepath)
                for para in doc.paragraphs:
                    if para.text.strip(): # Avoid empty paragraphs
                        doc_text += para.text + "\n"

            elif filename.endswith('.txt'):
                with open(filepath, 'r', encoding='utf-8') as f:
                    doc_text = f.read()

            else:
                print(f"Skipping unsupported file: {filename}")
                continue

            print(f"Successfully loaded: {filename}")

            # Now, chunk the text (simple paragraph chunking)
            # A more advanced way is RecursiveCharacterTextSplitter,
            # but splitting by double newline is very effective.
            paragraphs = doc_text.split('\n\n')
            for i, para in enumerate(paragraphs):
                if len(para.strip()) > 50: # Filter out short/empty strings
                    chunks.append({
                        "source_book": filename,
                        "chunk_id": f"{filename}-p{i}",
                        "content": para.strip()
                    })

        except Exception as e:
            print(f"Error processing {filename}: {e}")

    return chunks

# --- 4. Populate Neo4j (The Knowledge Graph) ---
def populate_kg():
    print("Populating Knowledge Graph...")
    with neo4j_driver.session(database="neo4j") as session:
        session.run("MATCH (n) DETACH DELETE n") # Clear old data
        for fact in KG_FACTS:
            session.run(fact)
    print("Knowledge Graph populated. View at http://localhost:7474")
    print("!!! Remember to edit KG_FACTS in this script to match your data !!!")

# --- 5. Populate OpenSearch (The Book Chunks) ---
def populate_opensearch(chunks):
    index_name = "book_chunks"
    print(f"Populating OpenSearch index '{index_name}'...")

    if os_client.indices.exists(index=index_name):
        os_client.indices.delete(index=index_name)

    # Create the index with hybrid mapping
    index_body = {
        "settings": { "index.knn": True },
        "mappings": {
            "properties": {
                "source_book": { "type": "keyword" }, 
                "content": { "type": "text" },        
                "content_vector": {                   
                    "type": "knn_vector",
                    "dimension": VECTOR_DIMENSION,
                    "method": { "name": "hnsw", "space_type": "l2", "engine": "faiss" }
                }
            }
        }
    }
    os_client.indices.create(index=index_name, body=index_body)

    # Ingest documents
    for chunk in chunks:
        try:
            # Get embedding from Ollama
            response = ollama_client.embeddings(
                model=EMBEDDING_MODEL,
                prompt=chunk['content']
            )
            vector = response['embedding']
            
            # Index into OpenSearch
            os_client.index(
                index=index_name,
                id=chunk['chunk_id'],
                body={
                    "source_book": chunk['source_book'],
                    "content": chunk['content'],
                    "content_vector": vector
                },
                refresh=False
            )
        except Exception as e:
            print(f"Error indexing chunk {chunk['chunk_id']}: {e}")

    os_client.indices.refresh(index=index_name) 
    print("OpenSearch populated with book chunks.")

# --- Run the Ingestion ---
if __name__ == "__main__":
    # 1. Populate KG (with your manual facts)
    populate_kg()

    # 2. Load, chunk, and embed your books
    book_chunks = load_and_chunk_documents('./books')
    if book_chunks:
        populate_opensearch(book_chunks)
    else:
        print("No documents were found or processed. Check the 'books_to_ingest' folder.")

    neo4j_driver.close()