import json
import logging
import re
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

class AcademicPlanRequest(BaseModel):
    goal: str
    target_date: Optional[str] = "Next 4 weeks"
    focus_topics: Optional[List[str]] = []

class StudyMilestone(BaseModel):
    week: str  # Can be Day X, Week X, Month X, Quarter X
    topic: str
    action_items: List[str]
    estimated_hours: int

class AcademicPlanResponse(BaseModel):
    summary: str
    coursework_gaps: List[str]
    milestones: List[StudyMilestone]
    exam_prep_tips: List[str]

class AcademicService:
    def __init__(self):
        try:
            self.llm = LLMService()
        except Exception as e:
            logger.warning(f"Failed to initialize LLMService: {e}")
            self.llm = None

    def _extract_json(self, text: str) -> dict:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start : end + 1])
        return json.loads(text)

    def _parse_time_units(self, timeline_str: str):
        """Extracts the quantity and unit (day, week, month, year) from the input string."""
        raw = timeline_str.lower()
        nums = re.findall(r"\d+", raw)
        qty = int(nums[0]) if nums else 1

        if any(w in raw for w in ["day", "hour", "tomorrow", "weekend"]):
            return max(1, min(qty, 14)), "Day"
        elif any(w in raw for w in ["week"]):
            return max(1, min(qty, 12)), "Week"
        elif any(w in raw for w in ["month"]):
            return max(1, min(qty, 12)), "Month"
        elif any(w in raw for w in ["year"]):
            return max(1, min(qty, 4)), "Quarter"
        
        # Default interpretation
        return 4, "Week"

    def _build_dynamic_plan(self, goal: str, count: int, unit: str, timeline_str: str) -> AcademicPlanResponse:
        """Fallback engine that creates granular milestones for any number of days, weeks, months, or years."""
        is_sys_design = any(k in goal.lower() for k in ["system design", "distributed", "architecture", "microservice", "scale"])
        is_dsa = any(k in goal.lower() for k in ["dsa", "data structure", "algorithm", "leetcode"])

        milestones = []
        
        if is_sys_design:
            topics_pool = [
                ("Networking, DNS, Load Balancers & Proxies", [
                    "Study OSI layers, HTTP/2 vs HTTP/3, and TCP/UDP tradeoffs",
                    "Understand Layer 4 vs Layer 7 Load Balancing and round-robin/consistent hashing",
                    "Configure a simple reverse proxy using Nginx or Caddy"
                ], 8),
                ("Databases, Replication & CAP Theorem", [
                    "Compare SQL vs NoSQL (Document, Wide-column, Key-Value)",
                    "Deep dive into Leader-Follower replication, Quorum consensus, and partition tolerance",
                    "Evaluate read-heavy vs write-heavy indexing strategies (B-Trees vs LSM-Trees)"
                ], 10),
                ("Caching, CDNs & Content Delivery", [
                    "Implement cache eviction policies (LRU, LFU, FIFO)",
                    "Analyze Write-Through, Write-Back, and Cache-Aside strategies",
                    "Review CDN edge routing and cache invalidation strategies"
                ], 8),
                ("Message Queues, Kafka & Async Processing", [
                    "Study Pub/Sub architecture, Kafka partitions, and RabbitMQ dead-letter queues",
                    "Analyze at-least-once, at-most-once, and exactly-once delivery semantics",
                    "Design an asynchronous task worker pipeline"
                ], 10),
                ("Designing URL Shortener & Rate Limiter", [
                    "Calculate throughput, storage, and bandwidth estimates (QPS/IOPS)",
                    "Implement Token Bucket or Leaky Bucket algorithm",
                    "Handle base62 encoding and hash collision resolution"
                ], 9),
                ("Designing Chat System & Video Streaming", [
                    "Compare WebSockets, Long-Polling, and Server-Sent Events (SSE)",
                    "Study video chunking, adaptive bitrate streaming (HLS/DASH), and metadata storage",
                    "Implement presence status tracking across distributed nodes"
                ], 10),
                ("High Availability, Resiliency & Circuit Breakers", [
                    "Design circuit breaker and retry mechanisms with exponential backoff",
                    "Understand disaster recovery: Multi-region active-active vs active-passive",
                    "Set up distributed tracing and telemetry using OpenTelemetry/Prometheus"
                ], 8),
                ("Final Mock System Design Interviews", [
                    "Complete 3 timed 45-minute whiteboarding interviews on real-world systems",
                    "Present clear capacity estimations, API signatures, and data models under time limits",
                    "Consolidate architectural trade-off cheat sheet"
                ], 10),
            ]
        elif is_dsa:
            topics_pool = [
                ("Arrays, Strings & Two Pointers", ["Sliding Window drills", "Two Pointers review", "10 Medium problems"], 8),
                ("Linked Lists, Stacks & Queues", ["Cycle detection", "Monotonic stack patterns", "8 Medium problems"], 8),
                ("Binary Trees & BSTs", ["Inorder/Preorder iterative traversals", "LCA & Tree paths", "10 Medium problems"], 10),
                ("Graphs, BFS & DFS", ["Topological sorting", "Shortest path (Dijkstra)", "Cycle detection in directed graphs"], 10),
                ("Dynamic Programming (1D & 2D)", ["Knapsack patterns", "Longest common subsequence", "State transition modeling"], 12),
                ("Heaps, Tries & Advanced Structures", ["Min/Max heaps for top-k elements", "Prefix trees implementation", "8 problems"], 9),
                ("Backtracking & Bit Manipulation", ["Subsets and permutations", "Bitmask DP and basic bitwise tricks", "8 problems"], 8),
                ("Mock Interview Assessments", ["Complete 4 timed LeetCode Medium/Hard mocks", "Review weak areas", "Final review"], 10),
            ]
        else:
            topics_pool = [
                (f"Foundations of {goal}", ["Study primary lectures and documentation", "Build sample hello-world scripts", "Set up tooling"], 6),
                (f"Core Practical Applications", ["Implement standard business logic", "Handle errors and input validation", "Write tests"], 8),
                (f"Advanced Features & Performance", ["Optimize bottlenecks", "Study architecture patterns", "Debug complex issues"], 9),
                (f"Real-World Project & Synthesis", ["Build an end-to-end practical project", "Document architecture and usage", "Final readiness review"], 10),
            ]

        # Distribute topics across the requested quantity
        for i in range(count):
            label = f"{unit} {i + 1}"
            topic_tuple = topics_pool[i % len(topics_pool)]
            milestones.append(
                StudyMilestone(
                    week=label,
                    topic=topic_tuple[0],
                    action_items=topic_tuple[1],
                    estimated_hours=topic_tuple[2]
                )
            )

        return AcademicPlanResponse(
            summary=f"Structured {count}-{unit.lower()} plan for '{goal}' tailored to {timeline_str}.",
            coursework_gaps=[
                f"Requires consistent {unit.lower()}-by-{unit.lower()} milestones to cover both theoretical architecture and implementation.",
                "Avoid reading theory without doing actual calculations (QPS, storage, memory constraints).",
                "Ensure continuous mock practice to explain design tradeoffs clearly."
            ],
            milestones=milestones,
            exam_prep_tips=[
                "Always start design questions with functional vs non-functional requirements and scale estimations.",
                "Highlight trade-offs clearly (e.g., Latency vs Consistency, SQL vs NoSQL)."
            ]
        )

    def generate_academic_plan(
        self, db: Session, student_id: str, request: AcademicPlanRequest
    ) -> AcademicPlanResponse:
        count, unit = self._parse_time_units(request.target_date)

        system_prompt = (
            "You are an expert Academic Advisor and Curriculum Planner for university students.\n"
            "CRITICAL TIMELINE INSTRUCTION:\n"
            f"The student requested a timeline of '{request.target_date}'.\n"
            f"You MUST generate EXACTLY {count} milestones, labeled '{unit} 1', '{unit} 2', up to '{unit} {count}'.\n"
            "Each milestone must have specific, realistic technical action items directly tailored to their goal.\n\n"
            "Respond ONLY with a valid JSON object matching this schema:\n"
            "{\n"
            '  "summary": "1-2 sentence strategy overview",\n'
            '  "coursework_gaps": ["gap 1", "gap 2", "gap 3"],\n'
            '  "milestones": [\n'
            '    {\n'
            f'      "week": "{unit} 1",\n'
            '      "topic": "Topic Name",\n'
            '      "action_items": ["Action 1", "Action 2", "Action 3"],\n'
            '      "estimated_hours": 8\n'
            "    }\n"
            "  ],\n"
            '  "exam_prep_tips": ["tip 1", "tip 2"]\n'
            "}"
        )

        user_prompt = (
            f"Goal: {request.goal}\n"
            f"Requested Timeline: {request.target_date}\n"
            f"Milestones required: Exactly {count} {unit}s."
        )

        if self.llm:
            try:
                raw_response = self.llm.generate(system_prompt=system_prompt, user_prompt=user_prompt)
                data = self._extract_json(raw_response)
                return AcademicPlanResponse(**data)
            except Exception as exc:
                logger.error(f"Live LLM call error: {exc}. Utilizing dynamic unit generator.")

        return self._build_dynamic_plan(request.goal, count, unit, request.target_date)