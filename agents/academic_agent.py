from typing import Dict, Any, List
from pydantic import BaseModel, Field

# 1. Output structure matching the team contract
class NextAction(BaseModel):
    action_type: str
    description: str
    payload: Dict[str, Any] = Field(default_factory=dict)

class AgentResult(BaseModel):
    status: str
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)
    confidence: float
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    next_actions: List[NextAction] = Field(default_factory=list)

# 2. Your Academic Agent class
class AcademicAgent:
    def analyze_syllabus_or_assignment(self, text: str, course_code: str) -> AgentResult:
        """
        Parses course notes or syllabus text to identify deliverables and study tasks.
        """
        has_deadline = "deadline" in text.lower() or "due" in text.lower() or "submit" in text.lower()
        
        if has_deadline:
            return AgentResult(
                status="completed",
                summary=f"Detected academic deadline for course {course_code}. Study task planned.",
                details={
                    "course_code": course_code,
                    "extracted_topic": "Assignment / Project Submission",
                    "suggested_prep_time": "3 days before deadline"
                },
                confidence=0.90,
                sources=[],
                next_actions=[
                    NextAction(
                        action_type="CREATE_TASK",
                        description=f"Prepare and submit assignment for {course_code}",
                        payload={"course": course_code, "status": "Pending"}
                    )
                ]
            )

        return AgentResult(
            status="completed",
            summary=f"Parsed academic material for {course_code}. No critical deadlines found.",
            details={"course_code": course_code},
            confidence=0.95,
            sources=[],
            next_actions=[]
        )

# 3. Test execution block
if __name__ == "__main__":
    agent = AcademicAgent()
    sample_text = "Operating Systems Project 1: Submit your CPU scheduling code before Friday midnight."
    result = agent.analyze_syllabus_or_assignment(sample_text, course_code="CS301")
    print(result.model_dump_json(indent=2))