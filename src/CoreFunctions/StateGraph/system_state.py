import os
import json
from typing import Dict, Any
from src.CoreFunctions.StateGraph.state import AgentState
from src.CoreFunctions.StateGraph.worker_framework import WorkerRegistry

def system_state_node(state: AgentState) -> dict:
    from src.CoreFunctions.Infrastructure.logger import log_node_start, log_node_end, log_message
    log_node_start("SystemState", state)
    
    # 1. Gather active workers info
    active_workers = {}
    for name, worker in WorkerRegistry.get_all_workers().items():
        model = WorkerRegistry._config.get(name, {}).get("model", "unknown")
        node_type = "Graph Node" if worker.is_graph_node else "Sub-Worker"
        active_workers[name] = {
            "description": worker.description,
            "is_graph_node": worker.is_graph_node,
            "use_local_llm": worker.use_local_llm,
            "model": model
        }
        
    # 2. Gather conversation history stats
    chat_history = state.get("chat_history", []) or []
    history_len_chars = sum(len(m.get("content", "")) for m in chat_history)
    history_words = sum(len(m.get("content", "").split()) for m in chat_history)
    
    # 3. Model parameters and budgets
    gemini_model = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
    ollama_model = os.environ.get("OLLAMA_MODEL", "gemma4:e4b")
    
    log_message(f"SystemState: {len(active_workers)} workers active, history: {len(chat_history)} messages.")
    
    system_state = {
        "active_workers": active_workers,
        "history_length_chars": history_len_chars,
        "history_length_words": history_words,
        "token_limits": {
            "gemini_thinking_budget": 2048,
            "gemini_model": gemini_model,
            "ollama_model": ollama_model
        }
    }
    
    output_state = {
        "system_state": system_state
    }
    
    log_node_end("SystemState", output_state)
    return output_state
