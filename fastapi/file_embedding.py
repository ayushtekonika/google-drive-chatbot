import os
from typing import Callable
# from langchain.document_loaders import PDFLoader, DocLoader
from langchain_community.document_loaders import PyPDFLoader, UnstructuredWordDocumentLoader, PyMuPDFLoader
from langchain_mistralai import MistralAIEmbeddings
from langchain_core.documents.base import Document
from qdrant import QdrantDB

ASSETS_DIR = "assets"

def process_and_add_embeddings(processing_id: str, progress_callback: Callable[[str, int, int, int, str], None]):
    
    qdrant_class = QdrantDB()
    documents_to_embed: list[Document] = []
    if not os.path.exists(ASSETS_DIR):
        raise ValueError(f"The folder '{ASSETS_DIR}' does not exist.")
    chunk_count = 0
    file_list = os.listdir(ASSETS_DIR)
    for file_name in file_list:
        file_path = os.path.join(ASSETS_DIR, file_name)
        
        if file_path.endswith('.pdf'):
            # loader = PyPDFLoader(file_path)
            loader = PyMuPDFLoader(file_path)
        elif file_path.endswith('.doc') or file_path.endswith('.docx'):
            loader = UnstructuredWordDocumentLoader(file_path)
        else:
            continue  

        try:
            documents: list[Document] = loader.load_and_split()
            chunk_count = chunk_count + 1
            progress_callback(processing_id, chunk_count, len(file_list), "Chunking Documents")
            documents_to_embed = documents_to_embed + documents

        except Exception as e:
            print(f"Error processing file {file_name}: {e}")

    qdrant_class.add_documents(documents_to_embed, processing_id, progress_callback)
