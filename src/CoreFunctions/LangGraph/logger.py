import sys
from datetime import datetime

class GraphLogger:
    """
    A simple logger for LangGraph nodes with ANSI color support.
    """
    
    # ANSI escape codes
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    
    @classmethod
    def log_node_start(cls, node_name: str):
        """
        Logs the start of a node execution.
        Format: Running {node} :
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        # Using Cyan for visibility
        print(f"\n{cls.BOLD}{cls.CYAN}Running {node_name} :{cls.RESET} ({timestamp})")
        sys.stdout.flush()

    @classmethod
    def log_node_end(cls, node_name: str):
        """
        Logs the end of a node execution.
        """
        # print(f"{cls.DIM}Finished {node_name}{cls.RESET}\n")
        # Keep it distinct but less noisy? Or just a separator?
        print(f"{cls.BOLD}{cls.CYAN}--- {node_name} Finished ---{cls.RESET}")
        sys.stdout.flush()

    @classmethod
    def log_decision(cls, component: str, decision: str, details: str = ""):
        """
        Logs a decision or routing choice.
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        msg = f"{cls.BOLD}{cls.GREEN}[{component}] Decision: {decision}{cls.RESET}"
        if details:
            msg += f" | {details}"
        print(f"{msg} ({timestamp})")
        sys.stdout.flush()

    @classmethod
    def log_error(cls, source: str, error_msg: str):
        """
        Logs an error.
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{cls.BOLD}{cls.RED}[{source}] ERROR: {error_msg}{cls.RESET} ({timestamp})")
        sys.stdout.flush()

    @classmethod
    def log_message(cls, source: str, message: str):
        """
        General purpose log.
        """
        print(f"[{source}] {message}")
