import sys
import builtins
import asyncio
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Infrastructure.auth_utils import _stdin_lock, get_stdin_prompt_banner

class HumanInterventionAbortError(BaseException):
    """Raised when the user explicitly stops or aborts execution during human intervention."""
    pass

class HumanInterventionReplanError(BaseException):
    """Raised when the user requests a re-planning from the Orchestrator/TaskRouter."""
    def __init__(self, reason: str, user_instruction: str):
        super().__init__(f"Replan requested. Reason: {reason}, User Instruction: {user_instruction}")
        self.reason = reason
        self.user_instruction = user_instruction

def locked_intervention_prompt(reason: str, prompt_text: str) -> str:
    with _stdin_lock:
        banner = get_stdin_prompt_banner("INTERVENTION", reason)
        print(banner, flush=True)
        return input(prompt_text)

async def request_human_intervention(reason: str) -> str:
    """Pauses the automated process and requests manual intervention from the human user.
    
    Use this tool when:
    - You encounter a CAPTCHA, Cloudflare verification, or bot detection.
    - You need a 2FA / OTP code, or the user needs to log in manually.
    - You are stuck, encounter a roadblock, or need clarification on how to proceed.
    
    Args:
        reason (str): The specific reason or barrier you encountered.
    """
    vis = getattr(builtins, "active_cli_visualizer", None)
    was_active_and_not_paused = False
    if vis and vis.active and not vis.is_paused:
        was_active_and_not_paused = True
        vis.is_paused = True
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()
    elif vis and vis.active and vis.is_paused:
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

    try:
        user_input = await asyncio.to_thread(
            locked_intervention_prompt,
            reason,
            "\nType guidance, 'abort'/'stop' to cancel, or 'ask orchestrator <instruction>' to re-plan: "
        )
        user_input = user_input.strip()
        if not user_input:
            user_input = "done"
            
        input_lower = user_input.lower()
        if input_lower in ["abort", "stop", "exit", "quit"]:
            raise HumanInterventionAbortError("User aborted execution.")
            
        elif input_lower.startswith("ask orchestrator") or input_lower.startswith("ask router") or input_lower.startswith("replan") or input_lower.startswith("re-plan"):
            instruction = ""
            for prefix in ["ask orchestrator", "ask router", "re-plan", "replan"]:
                if input_lower.startswith(prefix):
                    instruction = user_input[len(prefix):].strip()
                    break
            
            if not instruction:
                instruction = await asyncio.to_thread(
                    input,
                    "Enter instructions/details for the orchestrator to re-plan: "
                )
                instruction = instruction.strip()
                if not instruction:
                    instruction = "No specific instructions provided."
                    
            raise HumanInterventionReplanError(reason, instruction)

        print(f"✅ Resuming automation. User responded: '{user_input}'\n", flush=True)
        return f"Human responded: {user_input}"
    finally:
        if was_active_and_not_paused and vis and vis.active:
            vis.is_paused = False

def request_human_intervention_sync(reason: str) -> str:
    """Synchronous version of request_human_intervention.
    
    Args:
        reason (str): The specific reason or barrier you encountered.
    """
    vis = getattr(builtins, "active_cli_visualizer", None)
    was_active_and_not_paused = False
    if vis and vis.active and not vis.is_paused:
        was_active_and_not_paused = True
        vis.is_paused = True
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()
    elif vis and vis.active and vis.is_paused:
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

    try:
        user_input = locked_intervention_prompt(
            reason,
            "\nType guidance, 'abort'/'stop' to cancel, or 'ask orchestrator <instruction>' to re-plan: "
        )
        user_input = user_input.strip()
        if not user_input:
            user_input = "done"
            
        input_lower = user_input.lower()
        if input_lower in ["abort", "stop", "exit", "quit"]:
            raise HumanInterventionAbortError("User aborted execution.")
            
        elif input_lower.startswith("ask orchestrator") or input_lower.startswith("ask router") or input_lower.startswith("replan") or input_lower.startswith("re-plan"):
            instruction = ""
            for prefix in ["ask orchestrator", "ask router", "re-plan", "replan"]:
                if input_lower.startswith(prefix):
                    instruction = user_input[len(prefix):].strip()
                    break
            
            if not instruction:
                instruction = input("Enter instructions/details for the orchestrator to re-plan: ")
                instruction = instruction.strip()
                if not instruction:
                    instruction = "No specific instructions provided."
                    
            raise HumanInterventionReplanError(reason, instruction)

        print(f"✅ Resuming automation. User responded: '{user_input}'\n", flush=True)
        return f"Human responded: {user_input}"
    finally:
        if was_active_and_not_paused and vis and vis.active:
            vis.is_paused = False

# Expose shared tool
human_intervention_tool = StructuredTool.from_function(
    func=request_human_intervention_sync,
    name="request_human_intervention",
    description="Pauses the automated process and requests manual intervention from the human user. Use this when you hit CAPTCHAs, bot checks, 2FA prompts, or roadblocks/issues you cannot solve yourself.",
    coroutine=request_human_intervention
)
