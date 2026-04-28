"""
Agent 2 — Department Router
Reads departments.json + uses SerpAPI for state-specific helplines.
Returns both central and state department details.
"""

import json
from crewai import Agent, Task
from crewai.tools import tool
# from langchain_google_genai import ChatGoogleGenerativeAI
from serpapi import GoogleSearch
from loguru import logger
from config import config


def load_departments() -> dict:
    try:
        with open(config.DEPARTMENTS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load departments.json: {e}")
        return {}


@tool("DepartmentLookupTool")
def department_lookup_tool(department_category: str = "") -> str:
    """
    Look up central department details from departments.json.
    Input: department category key (e.g., 'banking', 'electricity', 'road_general')
    Returns: JSON string with full department details.
    """
    if not department_category:
        department_category = "general"

    departments = load_departments()
    dept_data = departments.get("departments", {})

    if department_category in dept_data:
        return json.dumps(dept_data[department_category], ensure_ascii=False, indent=2)

    # Try fuzzy match
    for key, value in dept_data.items():
        if department_category.lower() in key.lower() or key.lower() in department_category.lower():
            return json.dumps(value, ensure_ascii=False, indent=2)

    # Return universal portal as fallback
    universal = departments.get("universal_portal", {})
    return json.dumps({
        "note": "Specific department not found. Using universal grievance portal.",
        "universal_portal": universal
    }, ensure_ascii=False, indent=2)


@tool("StateHelplineTool")
def state_helpline_tool(query: str = "") -> str:
    """
    Search for state-specific helpline numbers using SerpAPI.
    Use this for state-level departments like electricity, water, police.
    Input: search query like 'West Bengal electricity complaint helpline number'
    Returns: Search results with state helpline information.
    """
    if not query:
        return json.dumps({"error": "No query provided", "result": "Please check state portal directly"})

    if not config.SERPAPI_KEY:
        return json.dumps({"error": "SerpAPI key not configured", "result": "Please check state portal directly"})

    try:
        search = GoogleSearch({
            "q": query,
            "api_key": config.SERPAPI_KEY,
            "num": 5,
            "gl": "in",  # India
            "hl": "en"
        })
        results = search.get_dict()
        organic = results.get("organic_results", [])

        formatted = []
        for r in organic[:4]:
            formatted.append({
                "title": r.get("title", ""),
                "snippet": r.get("snippet", ""),
                "link": r.get("link", "")
            })

        return json.dumps({
            "query": query,
            "results": formatted
        }, ensure_ascii=False)

    except Exception as e:
        logger.error(f"SerpAPI search failed: {e}")
        return json.dumps({"error": str(e), "result": "Search unavailable"})


# State-specific departments that need SerpAPI lookup
STATE_SPECIFIC_DEPARTMENTS = [
    "electricity", "water_supply_general", "water_supply_jal_shakti",
    "road_general", "police", "ration_pds", "pollution_general",
    "pollution_air", "hospital_health", "education_school"
]


def get_router_agent() -> Agent:
    # Using string format for LiteLLM (internal to CrewAI) to avoid Pydantic validation errors
    llm_model = f"gemini/{config.LLM_MODEL}"

    return Agent(
        role="Government Department Router",
        goal=(
            "Find the most accurate government department details for a citizen's complaint. "
            "Always provide BOTH central and state-level contact information. "
            "Use real-time search for state-specific helplines."
        ),
        backstory=(
            "You are an expert in Indian government structure with deep knowledge of "
            "central and state government departments. You know which complaints go to "
            "central authorities versus state authorities. You always provide accurate, "
            "verified contact details and never guess helpline numbers."
        ),
        llm=llm_model,
        tools=[department_lookup_tool, state_helpline_tool],
        verbose=True,
        allow_delegation=False,
        max_iter=4
    )


def get_router_task(agent: Agent, analyzed_complaint: str, user_state: str) -> Task:
    return Task(
        description=f"""
Based on the analyzed complaint below, find ALL relevant department contact details.

ANALYZED COMPLAINT:
{analyzed_complaint}

CITIZEN'S STATE: {user_state}

STEP-BY-STEP INSTRUCTIONS:

STEP 1 — Central Department Lookup
Use the DepartmentLookupTool with the department_category from the analyzed complaint.
Get the full central government contact details.

STEP 2 — State Department Search (MANDATORY for these categories)
If department is: electricity, water, police, road, ration, hospital, education, pollution
→ Use StateHelplineTool with query: "[{user_state}] [department name] grievance helpline number official"
→ Example: "West Bengal electricity complaint helpline WBSEDCL official number"
→ Extract the state-specific helpline from results

STEP 3 — Compile Complete Response
Combine both central and state information.

YOUR FINAL OUTPUT must be a structured JSON:
{{
  "department_name": "Full official name",
  "problem_category": "Category of problem",
  "central_details": {{
    "organization": "...",
    "helpline": "...",
    "portal": "...",
    "email": "...",
    "escalation": "...",
    "response_deadline": "X days"
  }},
  "state_details": {{
    "state": "{user_state}",
    "organization": "State specific org name",
    "helpline": "State specific number (from search or 'Search unavailable')",
    "portal": "State portal if found",
    "source": "URL where found"
  }},
  "relevant_acts": ["Act 1", "Act 2"],
  "is_state_specific": true/false,
  "action_type": "first_complaint OR escalation",
  "escalation_path": [
    "Step 1: Contact [X]",
    "Step 2: If no response in Y days, go to [Z]",
    "Step 3: Final escalation [W]"
  ],
  "response_deadline_days": 30,
  "whatsapp": "if available else null"
}}

IMPORTANT:
- Never make up helpline numbers
- If state search finds nothing, set state helpline as "Visit state portal directly"
- Always include the escalation path
- If citizen already complained (action_type = escalation), adjust escalation path accordingly
""",
        agent=agent,
        expected_output=(
            "Complete JSON with central and state department details, "
            "helplines, portals, escalation path, and relevant acts."
        )
    )