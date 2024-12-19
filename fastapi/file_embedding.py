import os
# from langchain.document_loaders import PDFLoader, DocLoader
from langchain_community.document_loaders import PyPDFLoader, UnstructuredWordDocumentLoader
from langchain_mistralai import MistralAIEmbeddings
from langchain_core.documents.base import Document
from qdrant import QdrantDB


def process_and_add_embeddings():
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
    QDRANT_URL = os.getenv("QDRANT_URL")
    QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION")
    MISTRALAI_API_KEY=os.getenv("MISTRALAI_API_KEY")
    ASSETS_DIR = "assets"

    embeddings = MistralAIEmbeddings(
        model="mistral-embed",
        api_key=MISTRALAI_API_KEY
    )
    
    qdrant_class = QdrantDB(QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION, embeddings)
    qdrant_class.create_collection()
    
    if not os.path.exists(ASSETS_DIR):
        raise ValueError(f"The folder '{ASSETS_DIR}' does not exist.")

    for file_name in os.listdir(ASSETS_DIR):
        file_path = os.path.join(ASSETS_DIR, file_name)
        
        # if file_path.endswith('.pdf'):
        #     loader = PyPDFLoader(file_path)
        if file_path.endswith('.doc') or file_path.endswith('.docx'):
            loader = UnstructuredWordDocumentLoader(file_path)
        else:
            continue  

        try:
            documents: list[Document] = loader.load()
            qdrant_class.add_documents(documents=documents)

        except Exception as e:
            print(f"Error processing file {file_name}: {e}")
