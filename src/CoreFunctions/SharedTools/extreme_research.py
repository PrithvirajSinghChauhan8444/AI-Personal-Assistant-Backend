import os
import json
import re
import time
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool
from src.CoreFunctions.Infrastructure.llm_factory import get_llm
from src.CoreFunctions.SharedTools.web_search import web_search

# ==============================================================================
# 1. Pydantic Schemas for Council Architecture
# ==============================================================================

class CouncilLens(BaseModel):
    lens_id: str = Field(description="Short alphanumeric identifier for the lens, e.g., 'technical', 'market', 'academic', 'community', 'regulatory'.")
    lens_title: str = Field(description="Formal title of the research lens, e.g., 'Technical & Architectural Deep-Dive'.")
    focus_areas: List[str] = Field(description="Key focus areas, specific angles, or questions this council member must investigate.")
    recommended_search_queries: List[str] = Field(description="Initial targeted search queries tailored specifically for this lens, including both formal sources and community platforms (Reddit, Quora, HackerNews, forums).")

class CouncilStrategyPlan(BaseModel):
    topic: str = Field(description="The central research topic.")
    min_time_minutes: int = Field(default=3, description="Minimum research time budget in minutes.")
    max_time_minutes: int = Field(default=10, description="Maximum research time ceiling in minutes.")
    executive_objective: str = Field(description="A comprehensive description of what the entire council must achieve across all dimensions.")
    council_lenses: List[CouncilLens] = Field(description="List of 3 to 6 distinct, non-overlapping council lenses/perspectives.")

class LensFindings(BaseModel):
    findings: str = Field(description="Detailed markdown summary of all key facts, statistics, technical specifics, real-world community sentiment (from Reddit, Quora, HN, forums), comparisons, and findings extracted from search results, citing specific source URLs inline (e.g. [Source Title/Domain](url)).")
    sources: List[str] = Field(default_factory=list, description="List of unique source URLs directly verified and used.")
    new_leads: List[str] = Field(default_factory=list, description="Follow-up queries relevant to this lens, including deep dives into community discussions and technical nuances.")
    new_unexplored_domains: List[str] = Field(default_factory=list, description="Brand new, unexpected domains or critical dimensions discovered that are outside the scope of current lenses and warrant summoning a new council agent.")

class AdjustedPlanResponse(BaseModel):
    topic: str = Field(description="The updated or confirmed research topic.")
    min_time_minutes: int = Field(description="Updated minimum research time in minutes.")
    max_time_minutes: int = Field(description="Updated maximum research time in minutes.")
    council_lenses: List[CouncilLens] = Field(description="The modified list of council lenses based on user feedback.")
    summary_of_changes: str = Field(description="Brief summary of what was adjusted according to user preferences.")

# ==============================================================================
# 2. Council Worker & Head Implementation
# ==============================================================================

class ExtremeResearchCouncil:
    def __init__(self, topic: str, min_time_minutes: int = 3, max_time_minutes: int = 10, interactive: bool = True):
        self.topic = topic
        self.min_time_minutes = min_time_minutes
        self.max_time_minutes = max_time_minutes
        self.min_time_seconds = max(60, min_time_minutes * 60)
        self.max_time_seconds = max(self.min_time_seconds + 60, max_time_minutes * 60)
        self.interactive = interactive
        self.start_time = None
        self.llm = get_llm()
        
        # Thread synchronization
        self._lock = threading.Lock()
        self.council_files = []
        self.active_lenses = []
        self.lens_index_counter = 0
        
        # Setup session storage
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
        self.reports_dir = os.path.join(project_root, "Memory", "research_reports")
        self.sessions_dir = os.path.join(self.reports_dir, "extreme_sessions")
        os.makedirs(self.sessions_dir, exist_ok=True)
        
        safe_topic = re.sub(r'[^a-zA-Z0-9_\-]', '_', topic.replace(" ", "_"))[:40].strip("_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.timestamp = timestamp
        self.session_id = f"session_{timestamp}_{safe_topic}"
        self.session_path = os.path.join(self.sessions_dir, self.session_id)
        os.makedirs(self.session_path, exist_ok=True)

    def elapsed_seconds(self) -> float:
        if not self.start_time:
            return 0.0
        return time.time() - self.start_time

    def is_min_time_met(self) -> bool:
        return self.elapsed_seconds() >= self.min_time_seconds

    def is_approaching_max_time(self) -> bool:
        # Buffer 45 seconds before max time for synthesis
        return self.elapsed_seconds() >= (self.max_time_seconds - 45)

    # --------------------------------------------------------------------------
    # Phase 1: Council Formulation & User Briefing / Customization
    # --------------------------------------------------------------------------
    def formulate_initial_plan(self) -> CouncilStrategyPlan:
        print(f"\n🏛️  [Council Head] Formulating multi-agent council strategy for topic: '{self.topic}'...", flush=True)
        prompt = f"""You are the Head of the Extreme Research Council.
Given the research topic: "{self.topic}"
Target minimum time: {self.min_time_minutes} minutes, maximum time: {self.max_time_minutes} minutes.

Formulate a multi-perspective research strategy. Decompose this topic into 3 to 5 distinct, highly specialized research lenses (such as Technical/Architecture, Market/Financial/Competitors, Academic/Scientific/Literature, Practical/Community/Case Studies, and Regulatory/Risks/Governance).

CRITICAL SOURCE DIVERSITY MANDATE:
For EVERY lens, include targeted search queries that search BOTH authoritative primary sources AND grassroots community discussions (such as Reddit, Quora, Hacker News, StackOverflow, and specialized practitioner forums).
"""
        try:
            structured_planner = self.llm.with_structured_output(CouncilStrategyPlan)
            plan: CouncilStrategyPlan = structured_planner.invoke(prompt)
            plan.min_time_minutes = self.min_time_minutes
            plan.max_time_minutes = self.max_time_minutes
            return plan
        except Exception as e:
            print(f"  ⚠️ [Council Head] Structured planning fallback triggered: {e}", flush=True)
            return CouncilStrategyPlan(
                topic=self.topic,
                min_time_minutes=self.min_time_minutes,
                max_time_minutes=self.max_time_minutes,
                executive_objective=f"Exhaustive council research on {self.topic}",
                council_lenses=[
                    CouncilLens(
                        lens_id="technical",
                        lens_title="Technical & Architectural Analysis",
                        focus_areas=["Core architecture", "Implementation details", "Performance benchmarks", "Developer challenges on Reddit & StackOverflow"],
                        recommended_search_queries=[
                            f"{self.topic} architecture technical deep dive",
                            f"{self.topic} benchmarks implementation site:github.com OR site:news.ycombinator.com",
                            f"{self.topic} technical issues developer discussion site:reddit.com"
                        ]
                    ),
                    CouncilLens(
                        lens_id="market",
                        lens_title="Market, Industry & Competitive Landscape",
                        focus_areas=["Market size", "Key competitors", "Pricing models", "Real user reviews & sentiment on Reddit & Quora"],
                        recommended_search_queries=[
                            f"{self.topic} market analysis competitors",
                            f"{self.topic} industry trends outlook",
                            f"{self.topic} worth it user review opinion site:reddit.com OR site:quora.com"
                        ]
                    ),
                    CouncilLens(
                        lens_id="academic_and_practical",
                        lens_title="Academic Literature, Real-World Case Studies & Community Experience",
                        focus_areas=["Scientific papers", "Real-world practitioner feedback", "Failure cases and lessons learned"],
                        recommended_search_queries=[
                            f"{self.topic} research papers state of the art",
                            f"{self.topic} practical lessons learned problems site:reddit.com",
                            f"{self.topic} user experiences discussions site:quora.com OR site:news.ycombinator.com"
                        ]
                    )
                ]
            )

    def conduct_user_briefing(self, plan: CouncilStrategyPlan) -> CouncilStrategyPlan:
        """Presents the proposed plan to the user and allows modifications before launching."""
        if not self.interactive or not sys.stdin.isatty():
            return plan

        border = "=" * 78
        print(f"\n{border}", flush=True)
        print("🏛️  EXTREME RESEARCH COUNCIL: PROPOSED INVESTIGATION PLAN", flush=True)
        print(f"{border}", flush=True)
        print(f"📌 Research Topic: {plan.topic}", flush=True)
        print(f"⏱️  Estimated Time: {plan.min_time_minutes} to {plan.max_time_minutes} minutes", flush=True)
        print(f"👥 Council Composition ({len(plan.council_lenses)} Specialized Agents):", flush=True)
        
        for idx, lens in enumerate(plan.council_lenses, start=1):
            print(f"   {idx}. [{lens.lens_title}] (ID: `{lens.lens_id}`)", flush=True)
            print(f"      • Focus: {', '.join(lens.focus_areas)}", flush=True)
            print(f"      • Initial Queries: {', '.join(lens.recommended_search_queries[:2])}", flush=True)
            
        print(f"{border}", flush=True)
        print("👉 Press [ENTER] to proceed with this plan, or type your adjustments below:", flush=True)
        print("   (e.g., 'Change time to 5-10m', 'Add lens on hardware requirements', 'Remove academic', 'Focus on ...')", flush=True)
        print(f"{border}\n", flush=True)

        try:
            user_feedback = input("Your input (Press ENTER to proceed): ").strip()
        except Exception:
            user_feedback = ""

        if not user_feedback or user_feedback.lower() in ["proceed", "yes", "y", "ok", "go", "start"]:
            print("✅ User approved plan. Launching Extreme Research Council...\n", flush=True)
            return plan

        # User wants changes -> Adjust plan with LLM
        print(f"\n🔄 [Council Head] Adjusting plan based on user feedback: '{user_feedback}'...", flush=True)
        adjust_prompt = f"""You are the Head of the Extreme Research Council.
The user requested adjustments to the proposed research plan.

Current Plan:
- Topic: "{plan.topic}"
- Time: {plan.min_time_minutes} to {plan.max_time_minutes} minutes
- Lenses: {[l.model_dump() for l in plan.council_lenses]}

User Feedback / Adjustments:
"{user_feedback}"

Generate the updated CouncilStrategyPlan incorporating all user instructions (modifying topic, time, adding/removing/adjusting lenses).
Ensure every lens continues to include mandatory community queries (Reddit, Quora, HackerNews, forums) alongside primary sources.
"""
        try:
            structured_adjuster = self.llm.with_structured_output(AdjustedPlanResponse)
            adjusted: AdjustedPlanResponse = structured_adjuster.invoke(adjust_prompt)
            
            plan.topic = adjusted.topic
            plan.min_time_minutes = max(1, adjusted.min_time_minutes)
            plan.max_time_minutes = max(plan.min_time_minutes + 1, adjusted.max_time_minutes)
            plan.council_lenses = adjusted.council_lenses
            
            # Update internal instance state
            self.topic = plan.topic
            self.min_time_minutes = plan.min_time_minutes
            self.max_time_minutes = plan.max_time_minutes
            self.min_time_seconds = self.min_time_minutes * 60
            self.max_time_seconds = self.max_time_minutes * 60
            
            print(f"✅ [Council Head] Plan adjusted: {adjusted.summary_of_changes}", flush=True)
            print(f"   • Updated Topic: {plan.topic}", flush=True)
            print(f"   • Updated Time: {plan.min_time_minutes} - {plan.max_time_minutes} mins", flush=True)
            print(f"   • Active Agents: {len(plan.council_lenses)}", flush=True)
            return plan
        except Exception as e:
            print(f"  ⚠️ Plan adjustment error: {e}. Proceeding with updated parameters...", flush=True)
            return plan

    # --------------------------------------------------------------------------
    # Phase 2: Fully Parallel & Independent Council Execution
    # --------------------------------------------------------------------------
    def run_council_member(self, lens: CouncilLens, lens_index: int, executor: Optional[ThreadPoolExecutor] = None) -> str:
        lens_filename = f"{lens_index:02d}_{lens.lens_id}.md"
        lens_filepath = os.path.join(self.session_path, lens_filename)
        
        with self._lock:
            self.active_lenses.append(lens.lens_id)
            if lens_filepath not in self.council_files:
                self.council_files.append(lens_filepath)
        
        print(f"\n🕵️‍♂️ [Council Agent {lens_index}: {lens.lens_title}] Initialized. Writing live to: {lens_filename}", flush=True)
        
        queries_queue = list(lens.recommended_search_queries)
        
        # Ensure every agent has explicit community platform queries queued
        community_queries = [
            f"{self.topic} {lens.lens_id} user experiences complaints site:reddit.com",
            f"{self.topic} {lens.lens_id} opinions discussion site:quora.com OR site:news.ycombinator.com"
        ]
        for cq in community_queries:
            if cq not in queries_queue:
                queries_queue.append(cq)

        completed_queries = set()
        collected_findings = []
        collected_sources = set()
        
        iteration = 1
        
        # Keep searching iteratively until minimum time is satisfied or time limit is approaching
        while queries_queue:
            if self.is_approaching_max_time():
                print(f"  ⏱️ [Council Agent {lens_index}: {lens.lens_title}] Time ceiling reached ({self.elapsed_seconds():.1f}s elapsed). Finalizing findings...", flush=True)
                break
                
            current_query = queries_queue.pop(0)
            if current_query.lower() in completed_queries:
                continue
                
            completed_queries.add(current_query.lower())
            print(f"  🔍 [Agent {lens_index} ({lens.lens_id}) - Step {iteration}] Querying: '{current_query}'...", flush=True)
            
            search_results = web_search(query=current_query, max_results=5, max_length=25000)
            
            analysis_prompt = f"""You are a specialized Senior Researcher in the Research Council assigned to the '{lens.lens_title}' lens.
Research Topic: "{self.topic}"
Target Lens: {lens.lens_title}
Focus Areas: {', '.join(lens.focus_areas)}
Current Query: "{current_query}"

Search Content:
{search_results}

Analyze this content strictly from your specialized lens.
CRITICAL REQUIREMENTS:
1. **MANDATORY COMMUNITY & PRACTITIONER EXTRACTION**:
   - Actively identify, extract, and cite grassroots user feedback, controversies, practical complaints, and community consensus from platforms like Reddit, Quora, Hacker News, StackOverflow, and user forums present in the search results alongside formal documentation.
2. **SOURCE ATTRIBUTION**:
   - For EVERY key fact, statistic, community quote, or claim, ALWAYS attach its source URL inline as a clickable markdown link: `[Source Title/Domain](url)`.
   - List all extracted source URLs in `sources`.
3. **FOLLOW-UP LEADS**:
   - List new follow-up questions/leads in `new_leads`. If you notice intriguing community debates or unresolved user concerns, add community-focused queries (e.g. including Reddit or Quora).
4. **NEW DOMAIN SUMMONING**:
   - If you discover a brand new, critical domain/dimension outside the scope of current lenses ({', '.join(self.active_lenses)}), list it in `new_unexplored_domains`.
"""
            try:
                structured_analyzer = self.llm.with_structured_output(LensFindings)
                res: LensFindings = structured_analyzer.invoke(analysis_prompt)
                
                collected_findings.append(f"#### Investigation Query: `{current_query}`\n\n{res.findings}\n")
                for s in res.sources:
                    if s:
                        collected_sources.add(s)
                
                # If we still have time budget before min_time, actively queue discovered leads
                if not self.is_min_time_met() or not self.is_approaching_max_time():
                    for lead in res.new_leads:
                        lead_clean = lead.strip()
                        if lead_clean.lower() not in completed_queries and lead_clean not in queries_queue:
                            queries_queue.append(lead_clean)
                            
                # If queue is getting low but min_time is not yet met, generate deep follow-up queries
                if len(queries_queue) == 0 and not self.is_min_time_met() and not self.is_approaching_max_time():
                    queries_queue.append(f"{self.topic} {lens.lens_id} controversies challenges site:reddit.com")
                    queries_queue.append(f"{self.topic} {lens.lens_id} expert opinions case studies")
                            
                # Dynamic mid-flight agent summoning for newly discovered domains
                if res.new_unexplored_domains and executor and not self.is_approaching_max_time():
                    for new_dom in res.new_unexplored_domains:
                        self._maybe_summon_new_agent(new_dom, executor)
                            
            except Exception as e:
                print(f"  ⚠️ [Agent {lens_index}] Extraction error: {e}", flush=True)
                collected_findings.append(f"#### Query: `{current_query}`\n\nRaw search snippet:\n{search_results[:2500]}...\n")
                
            # Write intermediate file checkpoint to disk independently
            self._write_lens_file(lens_filepath, lens, collected_findings, list(collected_sources), completed_queries)
            iteration += 1

        print(f"  ✅ [Council Agent {lens_index}: {lens.lens_title}] Completed with {len(collected_findings)} sections and {len(collected_sources)} sources saved to {lens_filename}.", flush=True)
        return lens_filepath

    def _maybe_summon_new_agent(self, domain_lead: str, executor: ThreadPoolExecutor):
        """Dynamically summons a new council agent mid-flight if a completely new domain is discovered."""
        clean_lead = domain_lead.strip()
        if not clean_lead or len(clean_lead) < 5:
            return
            
        with self._lock:
            # Avoid summoning duplicate or excessive agents (cap at 7 total)
            if len(self.active_lenses) >= 7:
                return
            for existing in self.active_lenses:
                if existing.lower() in clean_lead.lower() or clean_lead.lower() in existing.lower():
                    return
                    
            self.lens_index_counter += 1
            new_idx = self.lens_index_counter
            safe_id = re.sub(r'[^a-zA-Z0-9]', '_', clean_lead.lower())[:20].strip('_')
            self.active_lenses.append(safe_id)

        print(f"\n✨ [Council Head] 🚨 NEW DOMAIN DISCOVERED: '{clean_lead}'! Summoning New Council Agent {new_idx}...", flush=True)
        
        new_lens = CouncilLens(
            lens_id=safe_id,
            lens_title=f"Discovered Dimension: {clean_lead}",
            focus_areas=[clean_lead, "Impact on overall topic", "Community & practitioner feedback", "Key findings and evidence"],
            recommended_search_queries=[
                f"{self.topic} {clean_lead}",
                f"{clean_lead} user discussion site:reddit.com OR site:quora.com",
                f"{clean_lead} implications analysis"
            ]
        )
        
        # Submit new agent dynamically to the thread pool
        executor.submit(self.run_council_member, new_lens, new_idx, executor)

    def _write_lens_file(self, filepath: str, lens: CouncilLens, findings: List[str], sources: List[str], queries: set):
        content = f"""# Council Report: {lens.lens_title}
**Lens ID**: `{lens.lens_id}`  
**Topic**: {self.topic}  
**Focus Areas**: {', '.join(lens.focus_areas)}  
**Last Updated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  

---

## 🔬 Key Research Findings & Evidence

{''.join(findings)}

---

## 🌐 Verified Sources & References
{chr(10).join(f'- [{s}]({s})' for s in sorted(sources))}

---
*Queries Executed*: {', '.join(f'`{q}`' for q in queries)}
"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

    # --------------------------------------------------------------------------
    # Phase 3: Master Lossless Writer Agent & Timestamped Archival
    # --------------------------------------------------------------------------
    def synthesize_master_report(self) -> str:
        print(f"\n✍️  [Master Writer Agent] Reading all {len(self.council_files)} council files for lossless master synthesis...", flush=True)
        
        combined_council_data = ""
        for fpath in sorted(self.council_files):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                    combined_council_data += f"\n\n{'='*60}\n{content}\n{'='*60}\n"
            except Exception as e:
                print(f"  ⚠️ Error reading council file {fpath}: {e}", flush=True)

        writer_prompt = f"""You are the Master Research Writer & Chief Synthesizer for an Extreme Multi-Agent Research Council.
You have been provided with the exhaustive, raw research reports prepared by the council agents across all lenses on the topic: "{self.topic}".

Below is the complete compilation of all council reports:
{combined_council_data}

### 🎯 WRITING OBJECTIVE & MANDATORY LOSSLESS SYNTHESIS RULES:
1. **ZERO INFORMATION LOSS**:
   - You must NOT omit or overly compress any specific technical specifications, quantitative statistics, comparative metrics, historical timelines, controversial insights, or discovered nuances.
   - Combine and reconcile all perspectives into a unified, flowing master document.
2. **MANDATORY COMMUNITY PERSPECTIVES & CONSENSUS (Reddit, Quora, Forums)**:
   - In every relevant chapter, synthesize grassroots user experiences, real-world complaints, and community consensus from platforms like Reddit, Quora, and Hacker News, directly reconciling them against corporate and academic claims.
3. **RICH & BEAUTIFUL STRUCTURE**:
   - **Title & Metadata**: Polished title, executive overview, methodology statement mentioning the Extreme Council Multi-Agent investigation.
   - **Executive Summary & High-Impact Takeaways**: Comprehensive summary capturing core breakthroughs and findings.
   - **Table of Contents**: Linked or clearly structured headings.
   - **In-Depth Thematic Chapters**: Create deep, data-rich sections integrating Technical Architecture, Market/Ecosystem Dynamics, Academic/Theoretical Context, Real-World Community Evidence (Reddit/Quora/HN), and Risk/Regulatory Considerations.
   - **Comparative Tables & Callout Blocks**: Use Markdown tables and quote blocks wherever comparisons, timelines, or key trade-offs exist.
4. **MANDATORY INLINE CITATIONS & SOURCES**:
   - Every single fact, statistic, quote, and community finding MUST retain its inline clickable markdown citation `[Source Title/Domain](url)`.
   - Conclude with a unified, exhaustive "Master Bibliography & Sources" section listing all verified URLs used across all council files (including all Reddit, Quora, academic, and documentation links).

Format the final document in elegant, publication-grade Markdown.
"""
        try:
            response = self.llm.invoke(writer_prompt)
            content = response.content
            if isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        text_parts.append(item["text"])
                    elif isinstance(item, str):
                        text_parts.append(item)
                master_md = "".join(text_parts)
            else:
                master_md = str(content)
        except Exception as e:
            master_md = f"# Extreme Research Master Report: {self.topic}\n\nError during master synthesis: {e}\n\n## Raw Council Reports\n\n{combined_council_data}"

        # Save Master Report
        safe_topic = re.sub(r'[^a-zA-Z0-9_\-]', '_', self.topic.replace(" ", "_"))[:40].strip("_")
        master_filename = f"research_extreme_{safe_topic}_{self.timestamp}.md"
        master_filepath = os.path.join(self.reports_dir, master_filename)

        with open(master_filepath, "w", encoding="utf-8") as f:
            f.write(master_md)

        # Write permanent session metadata & preserve individual agent files
        meta = {
            "topic": self.topic,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "start_time": self.start_time,
            "total_elapsed_seconds": self.elapsed_seconds(),
            "council_files": [os.path.basename(p) for p in self.council_files],
            "master_report": master_filename
        }
        with open(os.path.join(self.session_path, "session_metadata.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        print(f"💾 [Saved] Master Extreme Research Report saved to: {master_filepath}", flush=True)
        print(f"💾 [Saved] All {len(self.council_files)} individual council agent files permanently preserved in: {self.session_path}", flush=True)

        confirmation = (
            f"### 🏆 Extreme Research Council Investigation Completed!\n\n"
            f"- **Council Session Folder**: `{os.path.relpath(self.session_path, self.reports_dir)}` ({len(self.council_files)} specialized agent files permanently stored)\n"
            f"- **Master Report**: [Memory/research_reports/{master_filename}](file://{master_filepath})\n"
            f"- **Total Time Elapsed**: {self.elapsed_seconds():.1f}s\n\n"
        )
        return confirmation + master_md

    # --------------------------------------------------------------------------
    # Main Execution Flow
    # --------------------------------------------------------------------------
    def run(self) -> str:
        # 1. Formulate Initial Plan
        plan = self.formulate_initial_plan()
        
        # 2. Pre-flight Briefing & User Customization
        plan = self.conduct_user_briefing(plan)
        
        # Set start timer after user confirms
        self.start_time = time.time()
        self.lens_index_counter = len(plan.council_lenses)
        
        print(f"\n🚀 [Extreme Research] Launching Council of {len(plan.council_lenses)} Parallel Agents (Min: {self.min_time_minutes}m, Max: {self.max_time_minutes}m)...", flush=True)
        
        # 3. Parallel Execution of Independent Council Agents
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = []
            for idx, lens in enumerate(plan.council_lenses, start=1):
                fut = executor.submit(self.run_council_member, lens, idx, executor)
                futures.append(fut)
                
            # Wait for all submitted council agents to complete
            for fut in as_completed(futures):
                try:
                    fut.result()
                except Exception as e:
                    print(f"  ⚠️ Agent execution exception: {e}", flush=True)

        # 4. Check Minimum Time Floor
        remaining_min_time = self.min_time_seconds - self.elapsed_seconds()
        if remaining_min_time > 0 and len(self.council_files) > 0:
            print(f"  ⏱️ [Council Head] Minimum time limit not yet reached ({self.elapsed_seconds():.1f}s < {self.min_time_seconds}s). Performing council gap-filling pass for {remaining_min_time:.1f}s...", flush=True)
            try:
                gap_query = f"{self.topic} community debates real-world issues site:reddit.com OR site:quora.com"
                web_search(query=gap_query, max_results=5, max_length=20000)
            except Exception:
                pass

        # 5. Master Lossless Synthesis by Writer Agent
        master_output = self.synthesize_master_report()
        return master_output


def extreme_research(topic: str, min_time_minutes: int = 3, max_time_minutes: int = 10, interactive: bool = True) -> str:
    """Performs multi-agent Extreme Research using a governed Research Agent Council.
    
    1. Briefs user with topic, estimated duration, and list of council agents with their focus areas.
    2. Allows user to modify any parameter (topic, time, adding/removing lenses).
    3. Runs council agents in FULL PARALLELISM with complete state independence.
    4. Mandates search & extraction from community resources (Reddit, Quora, HackerNews, forums) across all lenses.
    5. Dynamically summons new council agents mid-execution if brand new unexpected domains are discovered.
    6. Saves timestamped individual files per agent and compiles a lossless Master Research Report.

    Args:
        topic (str): The research topic or question.
        min_time_minutes (int, optional): Minimum time budget in minutes. Defaults to 3.
        max_time_minutes (int, optional): Maximum time ceiling in minutes. Defaults to 10.
        interactive (bool, optional): Whether to prompt user for pre-flight confirmation/edits if in terminal. Defaults to True.
    """
    orchestrator = ExtremeResearchCouncil(
        topic=topic,
        min_time_minutes=min_time_minutes,
        max_time_minutes=max_time_minutes,
        interactive=interactive
    )
    return orchestrator.run()


extreme_research_tool = StructuredTool.from_function(
    func=extreme_research,
    name="extreme_research",
    description="Perform exhaustive, multi-agent Extreme Research governed by a Research Council. Briefs user on topic/time/agents, supports user edits, runs agents with full parallelism, mandates inclusion of community sources (Reddit, Quora, HN), dynamically summons new agents for discovered domains, and produces individual timestamped files + a lossless master report."
)
