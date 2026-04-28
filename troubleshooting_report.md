# NyayaVaani Troubleshooting Report: Resolving Pipeline ValidationError

This report details the technical issues encountered during the execution of the multi-agent complaint pipeline and the steps taken to resolve them.

## 1. The Problem
The system was failing at the start of the complaint processing pipeline with the following error:
`Processing failed: {"detail":"RetryError[<Future at ... raised ValidationError>]"}`

### Root Causes:
*   **Pydantic v2 Strictness**: CrewAI 1.14.3 uses Pydantic v2, which is extremely strict about data types during class initialization.
*   **Agent Instance Mismatch**: The code was creating separate instances of the same Agent for the `Task` and the `Crew`. Pydantic flagged this as a validation error because it expected the task's agent to be an identical reference to one in the crew's list.
*   **LLM Type Validation**: The `ChatGroq` instance from `langchain-groq` was not being correctly recognized as a valid `BaseLLM` type by CrewAI's internal Pydantic models.
*   **Missing Dependency**: When attempting to use the more robust `groq/` prefix for model identification, the system lacked the `litellm` package, which is required by CrewAI 1.x for non-OpenAI providers.

---

## 2. Technical Approach
To solve this, I followed a multi-step diagnostic process:

1.  **Enhanced Logging**: I modified `backend/api.py` to print full stack traces. This revealed that the error was happening at the moment of `Agent()` instantiation.
2.  **Code Auditing**: I reviewed `analyzer.py`, `router.py`, and `writer.py` and found that `get_task` functions were calling `get_agent` internally, leading to duplicate objects.
3.  **Environment Inspection**: I checked the installed versions of `crewai`, `pydantic`, and `langchain-core` to identify version-specific breaking changes.
4.  **End-to-End Simulation**: I used a browser subagent to trigger the error in real-time, allowing me to see exactly where the UI hung.

---

## 3. The Fix

### Step 1: Agent & Task Refactoring
I decoupled the Agent creation from the Task creation. In `src/crew.py`, agents are now initialized exactly once and then passed as arguments to the task generators.
```python
# Before (Problematic)
tasks=[get_analyzer_task(text, state)] # Internally called get_agent() again

# After (Fixed)
analyzer_agent = get_analyzer_agent()
analyzer_task = get_analyzer_task(analyzer_agent, text, state)
```

### Step 2: Robust LLM Configuration
Instead of passing a `ChatGroq` object instance (which caused the Pydantic type mismatch), I switched to the string-based provider format:
```python
# analyzer.py
return Agent(
    role="...",
    llm="groq/llama-3.3-70b-versatile", # Uses LiteLLM bridge
    temperature=0.1
)
```

### Step 3: Dependency Installation
I installed `litellm` to enable the bridge between CrewAI and Groq's API. This is the recommended "industry standard" for CrewAI 1.x projects.

### Step 4: Defensive Tool Programming
I updated the `DepartmentLookupTool` and `StateHelplineTool` to include default values (e.g., `query: str = ""`) and check for `None` or empty inputs. This prevents the LLM from accidentally triggering a `ValidationError` if it tries to call a tool with missing data.

---

## 4. Verification Results
The system was tested end-to-end via the Streamlit UI:
1.  **Status**: ✅ SUCCESS
2.  **Performance**: The pipeline now completes in ~30-45 seconds.
3.  **Stability**: No further `RetryError` or `ValidationError` observed.
4.  **Outputs**: Correctly generates Formal Letters, Emails, and SMS drafts for Indian civic grievances.

**Report generated on:** 2026-04-27
**System Version**: NyayaVaani 1.0 (CrewAI 1.14.3)
