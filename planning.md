# Production Refactoring Implementation Plan

This plan details the step-by-step process for upgrading the NyayaVaani prototype into a robust, production-level system.

## User Review Required

> [!IMPORTANT]
> Please review these proposed steps. If you approve, I will begin executing them sequentially. I recommend committing your current codebase to version control before we begin.

## Open Questions

1. **Task Queue:** Do you want to implement the async background tasks using `Celery` with Redis, or prefer to keep it simpler using FastAPI's built-in `BackgroundTasks` for now?
2. **Database:** Would you like to migrate the file-based `session_memory.py` to PostgreSQL using SQLAlchemy, or a NoSQL database like MongoDB?

---

## Step 1: Restructure File Organization
We will reorganize the project layout to separate routing, business logic, and configurations.

### Directory Changes
- Create `src/tasks/` for all Pydantic output schemas and task definitions.
- Create `src/tools/` for moving the RAG and SerpAPI tools out of agent files.
- Create `src/crews/` to hold the unified Crew configuration.

## Step 2: Implement Pydantic Structured Outputs
We will replace the manual regex JSON parsing with strict LLM schemas.

### File Modifications
- **[NEW]** `src/tasks/schemas.py`: Define `AnalyzerOutput`, `RouterOutput`, and `WriterOutput` Pydantic models.
- **[MODIFY]** `src/agents/analyzer.py`, `router.py`, `writer.py`: Update the `get_*_task` functions to use the `output_pydantic` parameter instead of text-based JSON instructions.
- **[MODIFY]** `src/crew.py`: Remove the `extract_json_from_text` function completely.

## Step 3: Refactor RAG into a CrewAI Tool
RAG should be accessible to agents organically rather than hardcoded in the middle of the script.

### File Modifications
- **[NEW]** `src/tools/legal_rag_tool.py`: Wrap the `get_rag().retrieve_and_grade` method inside a `@tool` decorator.
- **[MODIFY]** `src/agents/researcher.py`: Define a `LegalResearcher` agent whose sole job is to query the RAG tool when other agents need legal information.

## Step 4: Unify the Crew Execution
Instead of running three disjointed agents, we will configure them to work as one cohesive team.

### File Modifications
- **[NEW]** `src/crews/civic_crew.py`: Import all agents and tasks, and define a single `Crew(agents=[...], tasks=[...], process=Process.sequential)` object.
- **[MODIFY]** `src/crew.py`: Remove all the separate `.kickoff()` calls and `time.sleep()` statements. Route the API directly to the new `civic_crew.kickoff()`.

## Step 5: Asynchronous Background Processing
To prevent the FastAPI server from timing out on long API requests.

### File Modifications
- **[MODIFY]** `backend/api.py`: Refactor the `/complaint/process` endpoint. It will immediately return a `job_id`. 
- **[NEW]** `backend/worker.py` (if Celery) or modify `api.py` (if using FastAPI BackgroundTasks) to run the `civic_crew.kickoff` function asynchronously.
- **[NEW]** `/complaint/status/{job_id}` endpoint to check progress.

## Step 6: Database & Memory Migration
Move away from hardcoded dictionaries and file-based persistence.

### File Modifications
- **[MODIFY]** `src/memory/session_memory.py`: Implement proper ORM connections (PostgreSQL/Mongo) for state storage.
- **[MODIFY]** `src/crews/civic_crew.py`: Enable CrewAI's native memory (`memory=True`).

---

## Verification Plan

### Automated Tests
- Create Python unittests simulating expected Pydantic model outputs.

### Manual Verification
- Send a complex civic complaint to the backend and ensure the frontend does not timeout while waiting.
- Verify that the resulting outputs correctly include the JSON structure without any parsing errors.
