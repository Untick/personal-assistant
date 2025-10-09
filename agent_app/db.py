import os
import logging

from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import CharacterTextSplitter
from langchain_community.document_loaders import DirectoryLoader

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Константы ---
PERSIST_DIRECTORY = 'chroma'
KNOWLEDGE_BASE_DIR = 'knowledge_base'
EMBEDDINGS_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

def get_embeddings_model() -> HuggingFaceEmbeddings:
    """
    Загружает и возвращает мультиязычную модель эмбеддингов из Hugging Face.
    """
    logging.info(f"Загрузка модели эмбеддингов: {EMBEDDINGS_MODEL_NAME}")
    model_kwargs = {'device': 'cpu'}
    encode_kwargs = {'normalize_embeddings': True}
    
    return HuggingFaceEmbeddings(
        model_name=EMBEDDINGS_MODEL_NAME,
        model_kwargs=model_kwargs,
        encode_kwargs=encode_kwargs
    )

def get_vector_db_retriever(force_create: bool = False):
    """
    Создает (если не существует) или загружает векторную базу данных ChromaDB.
    Возвращает объект retriever, который агент будет использовать для поиска информации.
    """
    embeddings = get_embeddings_model()
    
    if not os.path.exists(PERSIST_DIRECTORY) or force_create:
        logging.info("Создание новой векторной базы знаний...")
        
        loader = DirectoryLoader(KNOWLEDGE_BASE_DIR, glob="*.txt", show_progress=True)
        documents = loader.load()

        if not documents:
            logging.warning(f"Документы в {KNOWLEDGE_BASE_DIR} не найдены. Создается пустая база.")
            db = Chroma.from_documents([], embeddings, persist_directory=PERSIST_DIRECTORY)
        else:
            text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            docs = text_splitter.split_documents(documents)
            logging.info(f"Загружено {len(documents)} документов, разбито на {len(docs)} чанков.")
            
            db = Chroma.from_documents(docs, embeddings, persist_directory=PERSIST_DIRECTORY)
            logging.info("Векторная база успешно создана и сохранена.")
    else:
        logging.info(f"Загрузка существующей базы знаний из {PERSIST_DIRECTORY}")
        db = Chroma(persist_directory=PERSIST_DIRECTORY, embedding_function=embeddings)

    return db.as_retriever()

if __name__ == '__main__':
    # Этот блок позволяет нам запустить файл напрямую, чтобы протестировать его
    print("--- Тестирование модуля db.py ---")
    retriever = get_vector_db_retriever(force_create=True)
    print("База знаний успешно создана/загружена.")
    
    test_query = "Для чего нужен этот проект?"
    results = retriever.get_relevant_documents(test_query)
    print(f"\nРезультаты поиска по запросу: '{test_query}'")
    if results:
        for doc in results:
            print(f"  - Документ: {doc.page_content[:150]}...")
    else:
        print("  - Релевантные документы не найдены.")
    print("--- Тестирование завершено ---")
