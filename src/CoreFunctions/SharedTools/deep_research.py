import os
import json
import re
from datetime import datetime
from typing import List
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Infrastructure.llm_factory import get_llm
from src.CoreFunctions.SharedTools.web_search import web_search

class ResearchPlan(BaseModel):
    expanded_objective: str = Field(description="A detailed paragraph describing the expanded research goal and areas of interest.")
    subtopics: List[str] = Field(description="A list of initial subtopics, questions, or areas of focus to research.")

class AnalysisResult(BaseModel):
    findings: str = Field(description="A detailed markdown summary of all key facts, statistics, and findings extracted from search results, citing the specific source URLs inline (e.g. [Source](url)).")
    sources: List[str] = Field(default_factory=list, description="A list of unique source URLs extracted directly from the search results that contributed to these findings.")
    new_leads: List[str] = Field(description="A list of newly discovered subtopics, questions, or leads found in the source content that require follow-up research. Return empty list if no new questions arise.")

def deep_research(topic: str, max_depth: int = 5) -> str:
    """Performs recursive, goal-oriented deep web research on a given topic.
    It expands the topic, iteratively searches and discovers subtopics, dynamically adds new questions/leads found in the search results, and compiles a comprehensive report.

    Args:
        topic (str): The research topic or question.
        max_depth (int, optional): The maximum recursion/iteration depth. Defaults to 5.
    """
    print(f"\n🚀 [Deep Research] Starting recursive deep research on topic: '{topic}' with max depth: {max_depth}...", flush=True)
    
    # 1. Initialize LLM
    try:
        llm = get_llm()
    except Exception as e:
        return f"Error initializing LLM for deep research: {e}"

    # 2. Phase 1: Query Expansion and Initial Planning
    print("  📋 [Phase 1: Planning] Expanding search topic and formulating plan...", flush=True)
    plan_prompt = f"""You are an expert research planner. Given the user's research topic: "{topic}"
Expand this topic into a comprehensive research goal, identifying key areas to explore (e.g. history, current events, key competitors, important statistics, recent controversies, future trends).
Formulate a plan containing specific initial questions or subtopics to search.
"""
    try:
        structured_planner = llm.with_structured_output(ResearchPlan)
        plan: ResearchPlan = structured_planner.invoke(plan_prompt)
        print(f"  🔍 Expanded Objective: {plan.expanded_objective}", flush=True)
        print(f"  📋 Initial Subtopics to Research: {plan.subtopics}", flush=True)
    except Exception as e:
        print(f"  ⚠️ Structured planning failed: {e}. Using fallback planning...", flush=True)
        plan = ResearchPlan(
            expanded_objective=f"Deep research on the topic: {topic}",
            subtopics=[f"{topic} overview", f"{topic} history", f"{topic} recent news", f"{topic} facts and statistics"]
        )

    # 3. Phase 2: Recursive Discovery Loop
    pending_subtopics = list(plan.subtopics)
    completed_subtopics = set()
    research_log = {}
    
    depth = 1
    while depth <= max_depth and pending_subtopics:
        print(f"\n🔄 [Deep Research] Iteration {depth}/{max_depth} — Remaining queue size: {len(pending_subtopics)}", flush=True)
        
        # Process up to 3 subtopics in this depth level to avoid context explosion
        batch = []
        for _ in range(min(3, len(pending_subtopics))):
            batch.append(pending_subtopics.pop(0))
            
        for subtopic in batch:
            if subtopic.lower() in completed_subtopics:
                continue
                
            print(f"  🔍 [Searching Subtopic] '{subtopic}'...", flush=True)
            completed_subtopics.add(subtopic.lower())
            
            # Formulate query and fetch results from web_search
            # We use a large max_length (25,000 characters) to get detailed content
            search_results = web_search(query=subtopic, max_results=5, max_length=25000)
            
            # Analyze search results
            analysis_prompt = f"""You are a curious, highly analytical researcher.
Research Topic: "{topic}"
Current Target Subtopic: "{subtopic}"

Here are the search results returned from the web:
{search_results}

Analyze this content. Extract all key facts, data, statistics, and findings.
CRITICAL SOURCE ATTRIBUTION RULE:
- For every key fact, statistic, or finding you extract, ALWAYS attach or cite its corresponding source URL (e.g. `[Title/Domain](url)`).
- Extract and list all relevant source URLs in the `sources` field.

Be curious and creative. If you discover any new leads, interesting angles, controversies, or unexpected facts in this content that were NOT in the original research plan, list them as new leads.
"""
            try:
                structured_analyzer = llm.with_structured_output(AnalysisResult)
                analysis: AnalysisResult = structured_analyzer.invoke(analysis_prompt)
                
                # Save findings
                research_log[subtopic] = {
                    "findings": analysis.findings,
                    "sources": analysis.sources,
                    "queries_run": [subtopic]
                }
                print(f"  🔬 Extracted findings for '{subtopic}' ({len(analysis.findings)} chars, {len(analysis.sources)} sources).", flush=True)
                
                # Queue new leads dynamically (recursive discovery)
                for lead in analysis.new_leads:
                    lead_clean = lead.strip()
                    if lead_clean.lower() not in completed_subtopics and lead_clean not in pending_subtopics:
                        print(f"    ✨ [New Lead Discovered] Queuing: '{lead_clean}'", flush=True)
                        pending_subtopics.append(lead_clean)
            except Exception as e:
                print(f"  ⚠️ Analysis failed for subtopic '{subtopic}': {e}. Storing raw results...", flush=True)
                research_log[subtopic] = {
                    "findings": f"Raw search results snippet:\n{search_results[:2000]}...",
                    "sources": [],
                    "queries_run": [subtopic]
                }
                
        depth += 1

    # 4. Phase 3: Synthesis
    print("\n✍️ [Phase 3: Synthesis] Compiling and synthesizing final research report with sources...", flush=True)
    full_log_str = ""
    all_collected_sources = set()
    for sub, log in research_log.items():
        full_log_str += f"### Subtopic: {sub}\n{log['findings']}\n\n"
        for s in log.get("sources", []):
            if s:
                all_collected_sources.add(s)
        
    synthesis_prompt = f"""You are a master research editor. You have completed deep, recursive research on the topic: "{topic}".
Below is the complete log of findings and sources collected during the research process:

{full_log_str}

Please synthesize this into a highly professional, comprehensive, and exhaustive research report.
CRITICAL REQUIREMENTS:
1. **Title & Executive Summary**: A clear title, expanded research objective, and high-level summary.
2. **Table of Contents**: To organize all sections.
3. **Detailed Thematic Sections**: Synthesize findings logically under clean headings (history, current state, key players, statistics, controversies, and future outlook). Merge subtopics into cohesive narratives.
4. **Mandatory Inline Citations**: For EVERY key finding, statistic, claim, or fact, ALWAYS attach and cite its source URL inline using markdown links (e.g., `[Source](url)`). Never present facts without their source URL.
5. **Sources & References Section**: An exhaustive list at the end of the report of all verified sources and URLs used.

Format the output in clean, readable Markdown.
"""
    try:
        report_response = llm.invoke(synthesis_prompt)
        content = report_response.content
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    text_parts.append(item["text"])
                elif isinstance(item, str):
                    text_parts.append(item)
            report_md = "".join(text_parts)
        else:
            report_md = str(content)
    except Exception as e:
        report_md = f"# Deep Research Report: {topic}\n\nError during synthesis: {e}\n\n## Raw Logs\n\n{full_log_str}"

    # 5. Phase 4: Save Report
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    reports_dir = os.path.join(project_root, "Memory", "research_reports")
    os.makedirs(reports_dir, exist_ok=True)
    
    # Generate filename friendly topic name
    safe_topic = re.sub(r'[^a-zA-Z0-9_\-]', '_', topic.replace(" ", "_"))[:50].strip("_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"research_{safe_topic}_{timestamp}.md"
    file_path = os.path.join(reports_dir, filename)
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(report_md)
        print(f"💾 [Saved] Final deep research report saved to: {file_path}", flush=True)
        relative_path = os.path.relpath(file_path, project_root)
        confirmation = f"### Deep Research Completed!\n\nThe final research report has been successfully compiled and saved to [Memory/research_reports/{filename}](file://{file_path}).\n\n"
        return confirmation + report_md
    except Exception as save_err:
        return f"Deep research report synthesized successfully, but failed to save to disk: {save_err}\n\n{report_md}"

deep_research_tool = StructuredTool.from_function(
    func=deep_research,
    name="deep_research",
    description="Perform recursive, goal-oriented deep web research on a topic, discovering subtopics and dynamically following new leads up to a maximum depth."
)
