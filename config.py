import os
_BASE = os.path.dirname(os.path.abspath(__file__))

# Database paths
MOCK_STORE_DB = os.path.join(_BASE, "..", "create-mcp-ingestion", "mock_store.db")
CHUNKS_VEC_DB = os.path.join(_BASE, "..", "create-mcp-ingestion", "chunks_vec.db")
FILE_STORE_PATH = os.path.join(_BASE, "..", "create-mcp-ingestion", "file_store")

# Ollama
OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"
CHAT_MODEL = "llama3"           # model used for RAG answer generation
CHAT_MAX_TOKENS = 1500          # approximate — passed as num_predict to Ollama

# RAG
TOP_K_CHUNKS = 6
EVENT_CONFIDENCE_THRESHOLD = 0.7

# Interests
DEFAULT_STALENESS_TYPE = "time"
DEFAULT_STALENESS_THRESHOLD = 30  # days
