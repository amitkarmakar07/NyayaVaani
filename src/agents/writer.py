"""
Agent 3 — Output Writer
Generates 3 professional outputs: Formal Letter + Email + SMS
Uses complaint analysis + department details + RAG legal context
"""

from crewai import Agent, Task
# from langchain_google_genai import ChatGoogleGenerativeAI
from config import config


def get_writer_agent() -> Agent:
    # Using string format for LiteLLM (internal to CrewAI) to avoid Pydantic validation errors
    llm_model = f"gemini/{config.LLM_MODEL}"

    return Agent(
        role="Professional Legal Communication Writer",
        goal=(
            "Write three types of professional complaint communications: "
            "a formal letter, an email, and a short SMS. "
            "Each must be precise, legally grounded, empathetic, and ready to submit."
        ),
        backstory=(
            "You are an expert legal communication specialist and former senior bureaucrat "
            "with 25 years of experience drafting official government complaints in India. "
            "You know exactly what language gets attention, what legal references strengthen "
            "a complaint, and how to write firmly yet respectfully. Your complaints always "
            "get responses. You write for common citizens who need professional representation."
        ),
        llm=llm_model,
        verbose=True,
        allow_delegation=False,
        max_iter=2
    )

def get_writer_task(
    agent: Agent,
    analyzed_complaint: str,
    department_details: str,
    rag_legal_context: str,
    user_name: str,
    user_address: str,
    user_state: str,
    user_contact: str
) -> Task:

    return Task(
        description=f"""
Write three professional complaint communications for a citizen based on:

COMPLAINT ANALYSIS:
{analyzed_complaint}

DEPARTMENT DETAILS:
{department_details}

LEGAL CONTEXT & RIGHTS (from official acts):
{rag_legal_context}

CITIZEN DETAILS:
- Name: {user_name}
- Address: {user_address}
- State: {user_state}
- Contact: {user_contact}
- Date: Use today's date

---

GENERATE ALL THREE OUTPUTS:

═══════════════════════════════════════
OUTPUT 1 — FORMAL LETTER
═══════════════════════════════════════
Format requirements:
- TO: Full designation and department name (from department details)
- FROM: Citizen name and full address
- DATE: Today's date
- SUBJECT: Clear one-line subject in bold style
- BODY:
  • Opening: Respectful salutation
  • Para 1: Introduce yourself and state the problem clearly
  • Para 2: Timeline — when it started, what happened
  • Para 3: Previous actions taken (if any) and their outcomes
  • Para 4: Legal rights — cite specific Act name and section
  • Para 5: Specific demand — what you want them to do and by when
  • Para 6: Consequence statement — what steps you will take if unresolved
  • Closing: Respectful sign-off
- ATTACHMENTS LINE: List what citizen should attach
- SIGNATURE BLOCK: Name, address, contact, date

═══════════════════════════════════════
OUTPUT 2 — EMAIL
═══════════════════════════════════════
Format requirements:
- TO: Official email from department details
- SUBJECT: Concise action-oriented subject line
- BODY:
  • Brief professional opening
  • Problem summary (2-3 sentences)
  • Key facts (date started, previous complaint reference if any)
  • Legal rights in 1 sentence
  • Clear ask with deadline
  • Professional closing
  • Full signature with contact details
- Keep it concise — max 200 words body

═══════════════════════════════════════
OUTPUT 3 — SMS / WHATSAPP MESSAGE
═══════════════════════════════════════
Format requirements:
- Max 320 characters
- Include: Name, problem, complaint ID placeholder [COMP-ID], helpline to call
- Direct and clear
- In plain language
- Example format:
  "Complaint: [Problem]. Name: [Name]. [State]. 
   Filed on [date]. Helpline: [number]. 
   Ref: [COMP-ID]"

---

CRITICAL WRITING RULES:
1. Base ALL legal references ONLY on the RAG legal context provided
2. Do not cite acts or sections not mentioned in legal context
3. If legal context is limited, use general RTI Act reference only
4. Keep tone: firm but respectful — never rude or aggressive
5. Use simple English — a common citizen should understand
6. All numbers, names, departments must come from provided data only

OUTPUT FORMAT:
Return a JSON object with exactly these keys:
{{
  "formal_letter": "Full letter text with all formatting using \\n for newlines",
  "email": {{
    "to": "email address",
    "subject": "email subject",
    "body": "full email body"
  }},
  "sms": "SMS text under 320 chars",
  "key_legal_rights": ["Right 1 from Act X", "Right 2 from Act Y"],
  "suggested_attachments": ["Document 1", "Document 2"],
  "response_deadline": "X days as per [Act name]"
}}
""",
        agent=agent,
        expected_output=(
            "A JSON object containing formal_letter, email object, sms text, "
            "key_legal_rights list, suggested_attachments list, and response_deadline."
        )
    )