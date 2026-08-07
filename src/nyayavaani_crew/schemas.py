from typing import List, Optional
from pydantic import BaseModel, Field

class AnalyzerOutput(BaseModel):
    problem_summary: str = Field(description="Core problem in 1-2 sentences")
    department_category: str = Field(description="Category like road/electricity/water/ration/police/property_tax/hospital/education/pension/land/pollution/consumer/banking/corruption/telecom")
    severity: str = Field(description="Severity level: critical, high, medium, low")
    severity_reason: str = Field(description="Brief reason for the severity level")
    duration: str = Field(description="How long the problem has existed")
    prior_complaint: bool = Field(description="True if citizen already complained somewhere")
    prior_complaint_details: str = Field(description="Where and when they complained")
    prior_response: str = Field(description="What response they got")
    specific_org_mentioned: str = Field(description="Specific department/organization mentioned")
    location_details: str = Field(description="Location details mentioned")
    amounts_mentioned: str = Field(description="Any amounts/numbers mentioned")
    officials_mentioned: str = Field(description="Names of officials mentioned")
    citizen_impact: str = Field(description="How this is affecting the citizen's daily life")
    action_type: str = Field(description="first_complaint or escalation")
    level: str = Field(description="state, central, or both")

class CentralDetails(BaseModel):
    organization: str
    helpline: str
    portal: str
    email: str
    escalation: str
    response_deadline: str

class StateDetails(BaseModel):
    state: str
    organization: str
    helpline: str
    portal: str
    source: str

class RouterOutput(BaseModel):
    department_name: str
    problem_category: str
    central_details: CentralDetails
    state_details: StateDetails
    relevant_acts: List[str]
    is_state_specific: bool
    action_type: str
    escalation_path: List[str]
    response_deadline_days: int
    whatsapp: Optional[str] = None

class EmailOutput(BaseModel):
    to: str
    subject: str
    body: str

class WriterOutput(BaseModel):
    formal_letter: str = Field(description="Full letter text with all formatting")
    email: EmailOutput
    key_legal_rights: List[str]
    suggested_attachments: List[str]
    response_deadline: str

class SocialMediaOutput(BaseModel):
    twitter_post: str = Field(description="High-visibility Tweet for escalation")
