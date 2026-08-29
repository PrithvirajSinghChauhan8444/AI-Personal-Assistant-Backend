#!/usr/bin/env python3
"""
Launcher for AI Personal Assistant Pure CLI REPL
"""
import sys
import os

WORKSPACE_ROOT = os.path.dirname(os.path.abspath(__file__))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from src.cli import AssistantREPL

def main():
    repl = AssistantREPL()
    repl.run()

if __name__ == "__main__":
    main()
