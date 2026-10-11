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

# 2. Your Communication Agent class
class CommunicationAgent:
    def process_incoming_email(self, email_body: str, sender: str) -> AgentResult:
        # Check if email is an internship or job alert
        is_opportunity = "internship" in email_body.lower() or "job" in email_body.lower()
        
        if is_opportunity:
            return AgentResult(
                status="pending_approval",
                summary="Detected an internship opportunity. Drafted a confirmation reply.",
                details={
                    "sender": sender,
                    "draft_reply": "Hello,\nThank you for notifying me about this role. I will submit my documents shortly.\nBest regards."
                },
                confidence=0.92,
                sources=[],
                next_actions=[
                    NextAction(
                        action_type="REQUEST_APPROVAL",
                        description=f"Send drafted reply to {sender}",
                        payload={"recipient": sender, "action": "send_email"}
                    )
                ]
            )

        return AgentResult(
            status="completed",
            summary="Standard email. No immediate student actions required.",
            details={"sender": sender},
            confidence=0.99,
            sources=[],
            next_actions=[]
        )

# 3. Test execution block
if __name__ == "__main__":
    agent = CommunicationAgent()
    sample_email = "Hello Students, we are hiring for the Summer 2026 Software Internship!"
    result = agent.process_incoming_email(sample_email, sender="recruiter@tech.com")
    print(result.model_dump_json(indent=2))