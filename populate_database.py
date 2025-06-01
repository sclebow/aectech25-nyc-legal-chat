import argparse
import os
import shutil
from tqdm import tqdm
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from PyPDF2 import PdfReader
import markdown
from bs4 import BeautifulSoup

CHROMA_PATH = "chroma"
SOURCE_DATA_DIR = "source_data"
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 60

def get_embedding_function():
    """Get the embedding function using local LM Studio server"""
    return embedding_functions.OpenAIEmbeddingFunction(
        api_base="http://localhost:1234/v1",
        api_key="not-needed",
        model_name="nomic-embed-text"
    )

def read_pdf(file_path):
    """Extract text from PDF file"""
    reader = PdfReader(file_path)
    text = ""
    for page_num, page in enumerate(reader.pages):
        text += f"Page {page_num + 1}: " + page.extract_text() + "\n"
    return text

def read_markdown(file_path):
    """Extract text from Markdown file preserving headers"""
    with open(file_path, 'r', encoding='utf-8') as file:
        md_content = file.read()
        # Convert markdown to HTML
        html = markdown.markdown(md_content)
        # Parse HTML
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract text with headers
        text = ""
        for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p']):
            if element.name.startswith('h'):
                # Preserve header level and content
                level = element.name[1]
                text += f"{'#' * int(level)} {element.get_text()}\n\n"
            else:
                text += f"{element.get_text()}\n\n"
        return text

def read_document(file_path):
    """Read content from either PDF or Markdown file"""
    if file_path.lower().endswith('.pdf'):
        return read_pdf(file_path)
    elif file_path.lower().endswith(('.md', '.markdown')):
        return read_markdown(file_path)
    else:
        raise ValueError(f"Unsupported file format: {file_path}")

def split_text(text, source_file):
    """Split text into overlapping chunks with metadata"""
    chunks = []
    chunk_ids = []
    metadata_list = []
    
    start = 0
    chunk_num = 0
    
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end]
        
        # Create unique ID and metadata
        chunk_id = f"{source_file}_{chunk_num}"
        metadata = {
            "source": source_file,
            "chunk_number": chunk_num,
            "start_char": start,
            "end_char": end
        }
        
        chunks.append(chunk)
        chunk_ids.append(chunk_id)
        metadata_list.append(metadata)
        
        start = end - CHUNK_OVERLAP
        chunk_num += 1
    
    return chunks, chunk_ids, metadata_list

def populate_database():
    """Create or update the database with documents"""
    client = chromadb.PersistentClient(
        path=CHROMA_PATH,
        settings=Settings(anonymized_telemetry=False)
    )
    
    # Get or create collection
    collection_name = "cost_estimating_docs"
    try:
        collection = client.get_collection(
            name=collection_name,
            embedding_function=get_embedding_function()
        )
        print(f"Using existing collection: {collection_name}")
    except:
        collection = client.create_collection(
            name=collection_name,
            embedding_function=get_embedding_function()
        )
        print(f"Created new collection: {collection_name}")

    # Process documents
    print("\nProcessing documents...")
    for filename in tqdm(os.listdir(SOURCE_DATA_DIR)):
        if filename.endswith(('.pdf', '.md', '.markdown')):
            file_path = os.path.join(SOURCE_DATA_DIR, filename)
            
            try:
                # Extract text
                text = read_document(file_path)
                
                # Split into chunks
                chunks, chunk_ids, metadata_list = split_text(text, filename)
                
                # Add to collection in batches
                batch_size = 100
                for i in range(0, len(chunks), batch_size):
                    end_idx = min(i + batch_size, len(chunks))
                    collection.add(
                        documents=chunks[i:end_idx],
                        ids=chunk_ids[i:end_idx],
                        metadatas=metadata_list[i:end_idx]
                    )
                print(f"\nProcessed {filename}: {len(chunks)} chunks added")
                
            except Exception as e:
                print(f"\nError processing {filename}: {str(e)}")
                continue

    print("\n✅ Database population complete!")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Reset the database")
    args = parser.parse_args()
    
    if args.reset:
        if os.path.exists(CHROMA_PATH):
            shutil.rmtree(CHROMA_PATH)
            print("✨ Cleared existing database")
    
    populate_database()