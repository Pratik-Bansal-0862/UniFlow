import json

import pytest

from app.services.document_answer_service import DocumentAnswerService
from app.services.llm_service import LLMUnavailableError


class FakeLLM:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.called = False

    def generate(self, *, system_prompt, user_prompt):
        self.called = True
        if self.error:
            raise self.error
        return self.response


def test_no_evidence_skips_llm():
    llm = FakeLLM(response="unused")
    service = DocumentAnswerService(llm_service=llm)

    answer, status = service.answer("What skills do I have?", [])

    assert answer is None
    assert status == "no_evidence"
    assert llm.called is False


def test_valid_answer_is_returned():
    llm = FakeLLM(
        response=json.dumps({
            "answer": "The resume lists Python and SQL.",
            "insufficient_evidence": False,
        })
    )
    service = DocumentAnswerService(llm_service=llm)

    answer, status = service.answer(
        "Which skills are listed?",
        [{"source_name": "resume.pdf", "text": "Skills: Python and SQL"}],
    )

    assert answer == "The resume lists Python and SQL."
    assert status == "generated"
    assert llm.called is True


def test_insufficient_evidence_is_reported():
    llm = FakeLLM(
        response=json.dumps({
            "answer": "The documents do not specify the graduation date.",
            "insufficient_evidence": True,
        })
    )
    service = DocumentAnswerService(llm_service=llm)

    answer, status = service.answer(
        "When did I graduate?",
        [{"source_name": "resume.pdf", "text": "Skills: Python"}],
    )

    assert answer == "The documents do not specify the graduation date."
    assert status == "insufficient_evidence"


def test_unavailable_llm_preserves_retrieval_fallback():
    llm = FakeLLM(error=LLMUnavailableError("Providers unavailable"))
    service = DocumentAnswerService(llm_service=llm)

    answer, status = service.answer(
        "Which skills are listed?",
        [{"source_name": "resume.pdf", "text": "Skills: Python"}],
    )

    assert answer is None
    assert status == "unavailable"


def test_invalid_llm_json_is_rejected():
    llm = FakeLLM(response="not valid JSON")
    service = DocumentAnswerService(llm_service=llm)

    answer, status = service.answer(
        "Which skills are listed?",
        [{"source_name": "resume.pdf", "text": "Skills: Python"}],
    )

    assert answer is None
    assert status == "invalid_response"
