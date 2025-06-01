from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from collections import Counter
import re

import chromadb
from chromadb.config import Settings
from server.config import *

from flashrank import Ranker, RerankRequest

CHROMA_PATH = "chroma"

def get_chroma_client(mode="local"):
    """Get ChromaDB client with embedding function based on mode (local, openai, cloudflare)"""
    from chromadb.utils import embedding_functions
    if mode == "openai":
        embedding_fn = embedding_functions.OpenAIEmbeddingFunction(
            api_key=OPENAI_API_KEY,
            model_name=openai_embedding_model
        )
    elif mode == "cloudflare":
        embedding_fn = embedding_functions.OpenAIEmbeddingFunction(
            api_base=f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/v1",
            api_key=CLOUDFLARE_API_KEY,
            model_name=cloudflare_embedding_model
        )
    else:  # local
        embedding_fn = embedding_functions.OpenAIEmbeddingFunction(
            api_base="http://localhost:1234/v1",
            api_key="not-needed",
            model_name="nomic-embed-text"
        )
    client = chromadb.PersistentClient(
        path=CHROMA_PATH,
        settings=Settings(anonymized_telemetry=False)
    )
    return client, embedding_fn
# This script is only used as a RAG tool for other scripts.

def get_embedding(text, model=embedding_model):
    text = text.replace("\n", " ")
    mode = get_mode()
    if mode == "openai":
        response = client.embeddings.create(input = [text], dimensions = 768, model=model)
    else:
        response = client.embeddings.create(input = [text], model=model)
    vector = response.data[0].embedding
    return vector

def rag_answer(question, prompt, model=completion_model):
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", 
             "content": prompt
            },
            {"role": "user", 
             "content": question
            }
        ],
        temperature=0.0,
    )
    return completion.choices[0].message.content

def rerank_results(results, question, max_length=4000):
    """Rerank results and trim to fit context window"""
    # Calculate relevance scores using basic keyword matching
    scored_results = []
    question_words = set(question.lower().split())
    
    for doc in results['documents'][0]:
        # Count keyword matches
        doc_words = set(doc.lower().split())
        score = len(question_words.intersection(doc_words))
        
        # Add document length as a penalty factor
        length_penalty = len(doc) / 1000  # Penalize very long documents
        final_score = score / length_penalty
        
        scored_results.append((doc, final_score))
    
    # Sort by score and select best results that fit in context
    scored_results.sort(key=lambda x: x[1], reverse=True)
    
    selected_docs = []
    total_length = 0
    
    for doc, _ in scored_results:
        if total_length + len(doc) <= max_length:
            selected_docs.append(doc)
            total_length += len(doc)
    
    return selected_docs

def calculate_semantic_similarity(query_embedding, doc_embedding):
    """Calculate cosine similarity between query and document embeddings"""
    return cosine_similarity(
        np.array(query_embedding).reshape(1, -1),
        np.array(doc_embedding).reshape(1, -1)
    )[0][0]

def calculate_keyword_score(question, doc):
    """Calculate keyword matching score with weights for important terms"""
    # Architecture-specific important keywords
    important_keywords = {
        'architect': 2.0, 'design': 1.5, 'building': 1.5, 'structure': 1.5,
        'space': 1.5, 'form': 1.5, 'function': 1.5, 'style': 1.2,
        'material': 1.2, 'construction': 1.2
    }
    
    question_words = question.lower().split()
    doc_words = doc.lower().split()
    
    # Count matching keywords with weights
    score = 0
    for word in question_words:
        if word in doc_words:
            score += important_keywords.get(word, 1.0)
    
    return score

def calculate_position_score(doc_index, total_docs):
    """Give higher weight to documents appearing earlier in search results"""
    return 1 - (doc_index / total_docs)

def rag_call(question, n_results=10, max_context_length=4000):

    client, embedding_fn = get_chroma_client()
    collections = client.list_collections()
    if not collections:
        raise ValueError("No collections found in the database.")
    
    # Get collection WITH embedding function
    collection = client.get_collection(
        name=collections[0].name,
        embedding_function=embedding_fn
    )
    
    # Rest of the function remains the same
    results = collection.query(
        query_texts=[question],
        n_results=n_results * 2,
        include=['embeddings', 'documents']
    )

    rag_result = "\n".join(results)
    
    prompt = f"""Answer the question based on the provided information.
                Focus on the most relevant details and maintain coherence.
                If you don't know the answer, just say "I do not know."
                QUESTION: {question}
                PROVIDED INFORMATION: {rag_result}"""
    
    return rag_answer(question=question, prompt=prompt)

def init_rag(mode="local"):
    print("Initiating RAG with enhanced reranking...")
    client, embedding_fn = get_chroma_client(mode)
    collections = client.list_collections()
    if not collections:
        raise ValueError("No collections found in the database.")
    
    # Get collection WITH embedding function
    collection = client.get_collection(
        name=collections[0].name,
        embedding_function=embedding_fn
    )

    print(os.getcwd())

    ranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir=os.path.join(os.getcwd(), "models"))

    return collection, ranker

def rag_call_alt(question, collection, ranker, agent_prompt=None, n_results=10, max_context_length=4000):

    results = collection.query(
        query_texts=[question],
        n_results=n_results * 2,
        include=['documents', 'metadatas']
    )

    # passagedocs = [{'id': i, 'text': doc} for i, doc in enumerate(results['documents'][0])]
    passagedocs = [{
        'id': i,
        'text': doc,
        'metadata': meta
    } for i, (doc, meta) in enumerate(zip(results['documents'][0], results['metadatas'][0]))]
    
    rerankrequest = RerankRequest(query=question, passages=passagedocs)
    selected_docs = ranker.rerank(rerankrequest)

    # rag_result = "\n".join([doc['text'] for doc in selected_docs])[:max_context_length-20]
    # Format documents with source information
    formatted_docs = []
    for doc in selected_docs:
        source_info = f"\n[Source: {doc['metadata']['source']}]"
        # if 'page_number' in doc['metadata']:
        #     source_info += f", Page: {doc['metadata']['page_number']}"
        # source_info += "]"
        
        formatted_docs.append(f"{doc['text']}{source_info}")

    rag_result = "\n\n".join(formatted_docs)[:max_context_length-20]

    if agent_prompt is None:
        agent_prompt= """Answer the question based on the provided information. 
                        Each text chunk includes its source information in brackets.
                        You must cite your sources and page number if available.
                        Format references as: [Source: filename, Page: X]
                        Focus on the most relevant details and maintain coherence.
                        If you don't know the answer, just say "I do not know."
                        """
    else:
        agent_prompt += """
                        Each text chunk includes its source information in brackets.
                        You must cite your sources and page number if available.
                        Format references as: [Source: filename, Page: X]
                        Focus on the most relevant details and maintain coherence.
                        If you don't know the answer, just say "I do not know."
                        """
    prompt = f"""{agent_prompt}
                QUESTION: {question}
                PROVIDED INFORMATION: {rag_result}"""
    
    return rag_answer(question=question, prompt=prompt), rag_result
