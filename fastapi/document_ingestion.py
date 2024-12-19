import os
from uuid import uuid4
from langchain.document_loaders import DirectoryLoader, PyPDFLoader, UnstructuredWordDocumentLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_mistralai import MistralAIEmbeddings
from langchain.vectorstores import Qdrant
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

# Constants
ASSETS_DIR = "./assets"
QDRANT_API_KEY = "MYZXgP-lUPvL8i5r6-fuFe8NMdZx3OSOc3yJBgPhxJd8gwaOS4ab3w"
QDRANT_URL = "https://e94f3e20-cf25-423e-9552-b114492dac4f.europe-west3-0.gcp.cloud.qdrant.io:6333"
COLLECTION_NAME = "drive-docs"  # Name of the Qdrant collection d

def load_documents(directory):
    """
    Loads PDF and DOCX files from a directory.
    """
    loaders = [
        DirectoryLoader(directory, glob="*.pdf", loader_cls=PyPDFLoader),
        DirectoryLoader(directory, glob="*.docx", loader_cls=UnstructuredWordDocumentLoader),
    ]
    documents = []
    for loader in loaders:
        documents.extend(loader.load())
    return documents

def chunk_documents(documents):
    """
    Splits documents into smaller chunks using recursive character splitting.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )
    return splitter.split_documents(documents)

def generate_embeddings(chunks):
    """
    Generates embeddings for the document chunks using Mistral AI.
    """
    embeddings = MistralAIEmbeddings(
    model="mistral-embed",
    )
    qdrant_store = QdrantVectorStore.from_documents(
    docs=chunks,
    embeddings=embeddings,
    url=QDRANT_URL,
    prefer_grpc=True,
    api_key=QDRANT_API_KEY,
    collection_name="drive-docs",
    )
    uuids = [str(uuid4()) for _ in range(len(chunks))]
    return qdrant_store.add_documents(documents=chunks, ids=uuids)

# def ingest_into_qdrant(chunks, embeddings):
#     """
#     Ingests document chunks and their embeddings into Qdrant.
#     """
#     qdrant_client = QdrantClient(
#         url=QDRANT_URL,
#         api_key=QDRANT_API_KEY,
#     )
#     qdrant_vectorstore = Qdrant(
#         client=qdrant_client,
#         collection_name=COLLECTION_NAME,
#     )

#     # Ensure collection exists in Qdrant
#     qdrant_vectorstore.create_collection()

#     # Prepare documents with metadata
#     texts = [chunk.page_content for chunk in chunks]
#     metadata = [{"source": chunk.metadata.get("source", "unknown")} for chunk in chunks]

#     # Add to Qdrant
#     qdrant_vectorstore.add_texts(
#         texts=texts,
#         metadatas=metadata,
#         embeddings=embeddings,
#     )

#     print(f"Ingested {len(texts)} documents into Qdrant.")

if __name__ == "__main__":
    # Step 1: Load documents
    documents = load_documents(ASSETS_DIR)
    print(f"Loaded {len(documents)} documents.")

    # Step 2: Chunk documents
    chunks = chunk_documents(documents)
    print(f"Split into {len(chunks)} chunks.")

    # Step 3: Generate embeddings
    embeddings = generate_embeddings(chunks)
    print("Generated embeddings.")
