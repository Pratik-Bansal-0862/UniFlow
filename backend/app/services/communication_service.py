import json
import logging
import re
from typing import Optional, List
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.student_profile import StudentProfile
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

class CommunicationDraftRequest(BaseModel):
    recipient_type: str
    recipient_name: Optional[str] = "Hiring Manager"
    company_or_institution: Optional[str] = ""
    opportunity_id: Optional[str] = None
    specific_intent: str
    tone: Optional[str] = "Professional and enthusiastic"

class CommunicationDraftResponse(BaseModel):
    subject: str
    body: str
    key_highlights_used: List[str]
    suggested_next_steps: List[str]

class CommunicationService:
    def __init__(self):
        self.llm = LLMService()

    def generate_draft(
        self, db: Session, student_id: str, request: CommunicationDraftRequest
    ) -> CommunicationDraftResponse:
        skills = ["Python", "FastAPI", "Full-Stack Development"]
        try:
            profile = db.query(StudentProfile).filter(StudentProfile.student_id == student_id).first()
            if profile and profile.skills:
                skills = profile.skills
        except Exception:
            pass

        target_company = request.company_or_institution or "your team"
        recipient = request.recipient_name or "Hiring Manager"

        system_prompt = (
            "You are an expert University Career and Communications AI. "
            "Draft a concise, compelling, professional email for a student.\n"
            "You MUST respond ONLY with a raw JSON object (no markdown, no backticks):\n"
            "{\n"
            '  "subject": "Clear, engaging subject line",\n'
            '  "body": "Complete professional email text",\n'
            '  "key_highlights_used": ["highlight 1", "highlight 2"],\n'
            '  "suggested_next_steps": ["step 1", "step 2"]\n'
            "}"
        )

        user_prompt = (
            f"Recipient: {recipient} ({request.recipient_type})\n"
            f"Target Organization: {target_company}\n"
            f"Objective: {request.specific_intent}\n"
            f"Tone: {request.tone}\n"
            f"Student Verified Skills: {', '.join(skills)}"
        )

        try:
            raw_response = self.llm.generate(system_prompt=system_prompt, user_prompt=user_prompt)
            cleaned = re.sub(r"^```(?:json)?\s*", "", raw_response.strip(), flags=re.MULTILINE)
            cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE)
            data = json.loads(cleaned)
            return CommunicationDraftResponse(**data)
        except Exception as exc:
            logger.warning(f"Live LLM call failed ({exc}). Using tailored backup.")

        subject_line = f"Inquiry regarding {request.specific_intent} — {target_company}"
        body_text = f"""Dear {recipient},

I hope this message finds you well.

I am writing to express my strong interest in {request.specific_intent} at {target_company}. As a student developer with experience in {', '.join(skills[:3])}, I have built projects focused on clean APIs, database integration, and modern web architectures.

I would welcome the opportunity to discuss how my skill set aligns with your current openings. My resume is attached for your review.

Thank you very much for your time and consideration.

Sincerely,
UniFlow Student"""

        return CommunicationDraftResponse(
            subject=subject_line,
            body=body_text,
            key_highlights_used=[
                f"Skills: {', '.join(skills[:3])}",
                f"Intent: {request.specific_intent}"
            ],
            suggested_next_steps=[
                "Personalize any specific open role or project references.",
                "Attach an up-to-date PDF resume.",
                "Send via email or LinkedIn during standard business hours."
            ]
        )