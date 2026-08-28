import sqlite3
import os
from langchain_core.tools import StructuredTool

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

def search_chat_history(query: str, limit: int = 5) -> str:
    """Search the full conversational history archive using full-text search (FTS5).
    Use this tool to find past details, files created, actions completed, or user statements from previous turns/sessions.

    Args:
        query (str): The search query or keywords to look up in the chat archive.
        limit (int): The maximum number of historical exchanges to return. Defaults to 5.
    """
    print(f"\n[DEBUG] 🛠️ Calling Tool: search_chat_history")
    print(f"   Args: query={query}, limit={limit}")
    
    db_path = os.path.join(BASE_DIR, "Memory", "chat_archive.db")
    if not os.path.exists(db_path):
        return "No chat history archive exists yet."
        
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(
            """
            SELECT session_id, timestamp, role, content 
            FROM chat_history_fts 
            WHERE chat_history_fts MATCH ? 
            ORDER BY timestamp DESC 
            LIMIT ?
            """,
            (query, limit)
        )
        rows = cursor.fetchall()
        if not rows:
            cursor = conn.execute(
                """
                SELECT session_id, timestamp, role, content 
                FROM chat_history_fts 
                WHERE content LIKE ? 
                ORDER BY timestamp DESC 
                LIMIT ?
                """,
                (f"%{query}%", limit)
            )
            rows = cursor.fetchall()
            
        if not rows:
            return f"No chat history matches found for query: '{query}'"
            
        lines = []
        for row in rows:
            session_id, timestamp, role, content = row
            lines.append(f"[{timestamp}] Session: {session_id} | {role.capitalize()}: {content}")
        return "\n\n".join(lines)
    except sqlite3.OperationalError:
        try:
            cursor = conn.execute(
                """
                SELECT session_id, timestamp, role, content 
                FROM chat_history_fts 
                WHERE content LIKE ? 
                ORDER BY timestamp DESC 
                LIMIT ?
                """,
                (f"%{query}%", limit)
            )
            rows = cursor.fetchall()
            if not rows:
                return f"No chat history matches found for query: '{query}'"
            lines = []
            for row in rows:
                session_id, timestamp, role, content = row
                lines.append(f"[{timestamp}] Session: {session_id} | {role.capitalize()}: {content}")
            return "\n\n".join(lines)
        except Exception as fallback_err:
            return f"Error searching chat history: {fallback_err}"
    except Exception as e:
        return f"Error searching chat history: {e}"
    finally:
        conn.close()

memory_worker_tool_search_chat_history = StructuredTool.from_function(
    func=search_chat_history,
    name="search_chat_history",
    description="Search the full append-only archive of past conversation logs (FTS5 indexed) to find facts, instructions, or decisions from previous sessions."
)
