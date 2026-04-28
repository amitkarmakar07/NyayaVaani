"""
Agent 1 — Complaint Analyzer
Understands raw voice/text complaint deeply.
Extracts structured complaint data for downstream agents.
"""

from crewai import Agent, Task
from langchain_groq import ChatGroq
from config import config


def get_analyzer_agent() -> Agent:

    return Agent(
        role="Senior Complaint Analyst",
        goal=(
            "Deeply understand a citizen's complaint from their raw voice or text input. "
            "Extract all critical structured information needed to route and resolve the complaint. "
            "Be empathetic, thorough, and never miss implicit details."
        ),
        backstory=(
            "You are a seasoned Indian government complaint analyst with 20 years of experience "
            "handling civic grievances across all states. You understand both Hindi and English complaints, "
            "can read between the lines, and extract precise actionable information even from vague inputs. "
            "You know every type of civic problem Indian citizens face."
        ),
        llm=f"groq/{config.LLM_MODEL}",
        temperature=0.1,
        verbose=True,
        allow_delegation=False,
        max_iter=3
    )


def get_analyzer_task(agent: Agent, complaint_text: str, user_state: str) -> Task:
    return Task(
        description=f"""
Analyze the following citizen complaint thoroughly and extract all structured information.

CITIZEN COMPLAINT:
\"\"\"{complaint_text}\"\"\"

CITIZEN'S STATE: {user_state}

YOUR ANALYSIS MUST EXTRACT:

1. PROBLEM SUMMARY
   - What is the core problem in 1-2 sentences?
   - What department category does this belong to?
     (road/electricity/water/ration/police/property_tax/hospital/
      education/pension/land/pollution/consumer/banking/corruption/telecom)

2. SEVERITY ASSESSMENT
   - Severity level: critical / high / medium / low
   - Why this severity? (brief reason)

3. TIMELINE
   - How long has this problem existed? (extract from complaint or state "Not mentioned")
   - Any deadlines mentioned?

4. PRIOR ACTIONS
   - Has citizen already complained somewhere? (yes/no)
   - If yes, where and when?
   - What response did they get?

5. KEY ENTITIES
   - Specific department/organization mentioned (if any)
   - Location details mentioned
   - Any amounts/numbers mentioned (money, bill amount, etc.)
   - Names of officials mentioned (if any)

6. CITIZEN IMPACT
   - How is this affecting the citizen's daily life?

7. RECOMMENDED ACTION TYPE
   - First complaint OR Escalation (if already complained before)?
   - State-level issue OR Central government issue?

OUTPUT FORMAT: Respond ONLY as a structured JSON object with these exact keys:
{{
  "problem_summary": "...",
  "department_category": "...",
  "severity": "critical|high|medium|low",
  "severity_reason": "...",
  "duration": "...",
  "prior_complaint": true/false,
  "prior_complaint_details": "...",
  "prior_response": "...",
  "specific_org_mentioned": "...",
  "location_details": "...",
  "amounts_mentioned": "...",
  "officials_mentioned": "...",
  "citizen_impact": "...",
  "action_type": "first_complaint|escalation",
  "level": "state|central|both"
}}

Be precise. Do not hallucinate. If information is not in the complaint, use "Not mentioned".
""",
        agent=agent,
        expected_output=(
            "A valid JSON object with all extracted complaint details. "
            "Every field must be filled. Use 'Not mentioned' for missing info."
        )
    )