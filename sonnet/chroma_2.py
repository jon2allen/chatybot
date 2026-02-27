import chromadb
from chromadb.utils import embedding_functions
import re

def parse_sonnets(filepath):
    """Parses sonnets from a text file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    pattern = re.compile(r"([IVXLCDM]+)\s*\n(.*?)(?=\n[IVXLCDM]+\s*\n|\Z)", re.DOTALL)
    for match in pattern.finditer(text):
        yield match.group(1), match.group(2).strip()

def load_sonnets_to_chroma(filepath, db_path="sonnet_data.db"):
    """Loads sonnets into a ChromaDB collection."""
    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_or_create_collection("sonnets")
    
    sonnet_generator = parse_sonnets(filepath)
    
    documents = []
    ids = []
    metadatas = []

    for roman_numeral, sonnet_text in sonnet_generator:
        documents.append(sonnet_text)
        ids.append(roman_numeral)
        metadatas.append({"roman_numeral": roman_numeral})

    collection.add(
        documents=documents,
        ids=ids,
        metadatas=metadatas
    )
    return collection

def search_chroma(collection, query, n_results=3):
    """Searches ChromaDB for sonnets matching a query."""
    results = collection.query(
        query_texts=[query],
        n_results=n_results
    )
    return results

if __name__ == '__main__':
    collection = load_sonnets_to_chroma("sonnets.txt")

    # Perform test searches
    search_query_1 = "Shall I compare thee to a summer's day?"
    results_1 = search_chroma(collection, search_query_1)
    print(f"Search results for '{search_query_1}':")
    print(results_1)

    search_query_2 = "the eye of heaven"
    results_2 = search_chroma(collection, search_query_2)
    print(f"\nSearch results for '{search_query_2}':")
    print(results_2)
