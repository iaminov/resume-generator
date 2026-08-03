"""Shared fixtures.

All fixture data is fictional. Per the confidentiality rule in
.claude/rules/data-integrity.md, no real person, company, or profile content may
appear in anything committed outside data/profiles/ -- and the tests are
committed.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))


@pytest.fixture
def short_resume():
    """A resume with one brief role -- comfortably under one page."""
    return {
        "name": "Jane Doe",
        "contact": {"email": "jane@example.com", "location": "Springfield"},
        "summary": "Backend engineer.",
        "skills": [{"category": "Languages", "items": ["Python", "Go"]}],
        "experience": [
            {
                "title": "Software Engineer",
                "company": "Acme Corp",
                "dates": "2020 - Present",
                "bullets": ["Built a thing.", "Fixed another thing."],
            }
        ],
        "education": [{"degree": "B.S. Computer Science", "institution": "State University"}],
    }


@pytest.fixture
def long_resume():
    """A resume big enough to need several pages at any density."""
    bullet = (
        "Designed and shipped a distributed service handling substantial traffic, "
        "coordinating across several teams and owning it end to end through "
        "design, rollout, and on-call."
    )
    return {
        "name": "Jane Doe",
        "contact": {
            "email": "jane@example.com",
            "phone": "(555) 010-0100",
            "location": "Springfield",
            "linkedin": "linkedin.com/in/example",
            "github": "github.com/example",
        },
        "summary": "Backend engineer. " + ("Detail sentence for length. " * 12),
        "skills": [
            {"category": f"Category {i}", "items": [f"Skill {j}" for j in range(14)]}
            for i in range(6)
        ],
        "experience": [
            {
                "title": f"Engineer Level {i}",
                "company": f"Company {i}",
                "location": "Springfield",
                "dates": "2018 - 2024",
                "bullets": [bullet] * 6,
            }
            for i in range(6)
        ],
        "projects": [
            {"name": f"Project {i}", "description": bullet, "technologies": "Python, Go"}
            for i in range(8)
        ],
        "education": [{"degree": "B.S. Computer Science", "institution": "State University"}],
    }


@pytest.fixture
def cover_letter():
    return {
        "name": "Jane Doe",
        "contact": {"email": "jane@example.com", "location": "Springfield"},
        "date": "January 1, 2030",
        "recipient": {"company": "Acme Corp", "location": "Springfield"},
        "salutation": "Dear Hiring Manager,",
        "body": ["First paragraph here.", "Second paragraph here."],
        "closing": "Sincerely,",
        "signature": "Jane Doe",
    }
