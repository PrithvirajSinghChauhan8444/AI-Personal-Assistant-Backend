from langchain_core.tools import StructuredTool
from src.CoreFunctions.Infrastructure.file_vector_store import rag_qa_workspace_documents

def query_documents_db_tool(query: str) -> str:
    """Queries the user's embedded document database (PDFs, Word docs, spreadsheets, slides, images) 
    to retrieve answers across files in the workspace/Documents folder.

    Args:
        query (str): The specific question to search and answer using embedded documents.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: query_documents_db_tool")
    print(f"   Args: query={query}")
    return rag_qa_workspace_documents(query)

query_documents_db_tool = StructuredTool.from_function(
    func=query_documents_db_tool,
    name="query_documents_db_tool",
    description="Queries the user's document database (PDFs, Word docs, spreadsheets, presentations, image captions) to answer questions across files in the workspace."
)
