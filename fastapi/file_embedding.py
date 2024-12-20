import os
from typing import Callable
# from langchain.document_loaders import PDFLoader, DocLoader
from langchain_community.document_loaders import PyPDFLoader, UnstructuredWordDocumentLoader
from langchain_mistralai import MistralAIEmbeddings
from langchain_core.documents.base import Document
from qdrant import QdrantDB

ASSETS_DIR = "assets"

def process_and_add_embeddings(processing_id: str, progress_callback: Callable[[str, int, int, int, str], None]):
    
    qdrant_class = QdrantDB()
    
    if not os.path.exists(ASSETS_DIR):
        raise ValueError(f"The folder '{ASSETS_DIR}' does not exist.")

    for file_name in os.listdir(ASSETS_DIR):
        file_path = os.path.join(ASSETS_DIR, file_name)
        
        if file_path.endswith('.pdf'):
            loader = PyPDFLoader(file_path)
        elif file_path.endswith('.doc') or file_path.endswith('.docx'):
            loader = UnstructuredWordDocumentLoader(file_path)
        else:
            continue  

        try:
            documents: list[Document] = loader.load()
            qdrant_class.add_documents(documents, processing_id, progress_callback)

        except Exception as e:
            print(f"Error processing file {file_name}: {e}")
