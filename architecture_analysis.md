# Codebase & Architecture Analysis

I have thoroughly reviewed the file structure, system architecture, and specifically the CrewAI implementation in the NyayaVaani project. While the concept (Agentic Civic Assistant + Corrective RAG) is excellent, there are several significant architectural flaws that prevent this from being a production-ready, industry-level application.

Here is a comprehensive breakdown of the current flaws and how to upgrade them for a production environment.

## 1. CrewAI Design Flaws & Upgrades

### ❌ Flaw: Manual Sequential Orchestration instead of Native Crew
Currently, in `src/crew.py`, you are creating three **completely separate Crews**, each with 1 Agent and 1 Task. You manually execute them one by one, force `time.sleep(3)` between them, and pass data by manually parsing JSON strings.
**Why it's bad:** This defeats the purpose of CrewAI. It eliminates the agents' ability to collaborate, share context, or gracefully recover from errors as a team.
**✅ Production Upgrade:**
Define **ONE** `Crew` that contains all agents and tasks. CrewAI natively supports sequential processing.
```python
# Production approach
civic_crew = Crew(
    agents=[analyzer_agent, router_agent, writer_agent],
    tasks=[analyzer_task, router_task, writer_task],
    process=Process.sequential,
    memory=True # Enable native memory
)
result = civic_crew.kickoff(inputs={"complaint_text": complaint_text, "user_state": state})
```

### ❌ Flaw: Manual JSON Parsing via Regex
The `extract_json_from_text` function in `crew.py` relies on brittle regex patterns to clean up LLM markdown output.
**Why it's bad:** LLMs can output unpredictable text formats, causing regex to fail and breaking the pipeline.
**✅ Production Upgrade:**
CrewAI natively supports **Pydantic Structured Outputs**. By defining a Pydantic model for your expected output and passing it to the `Task` via the `output_pydantic` parameter, CrewAI forces the LLM to output valid JSON conforming to your schema automatically.

### ❌ Flaw: RAG is Hardcoded Instead of Being a Tool
Currently, RAG is called procedurally in `crew.py` between Agent 1 and Agent 2. I noticed an empty file: `src/agents/researcher.py`.
**Why it's bad:** Hardcoding the RAG step limits the system's flexibility. If an agent needs to look up something *during* writing, it cannot.
**✅ Production Upgrade:**
Flesh out `researcher.py` to create a `LegalResearcher` Agent. Convert your `CorrectiveRAG` methods into a `Tool` (using CrewAI's `@tool` decorator). Assign this tool to the Researcher or Writer agent so they can autonomously query Indian law whenever they need it.

---

## 2. System Design & Backend Flaws

### ❌ Flaw: Blocking API Endpoints
In `backend/api.py`, the `/complaint/process` endpoint calls `run_complaint_pipeline()` synchronously.
**Why it's bad:** AI agent pipelines take 30-60+ seconds to run. Fast/Uvicorn workers will be blocked, and browsers will eventually timeout waiting for an HTTP response. This will crash under concurrent user load.
**✅ Production Upgrade:**
Use a Task Queue (like **Celery + Redis** or **Temporal**). The API should instantly return a `job_id`, and the frontend should either poll a `/status/{job_id}` endpoint or use WebSockets to stream agent progress in real-time.

### ❌ Flaw: Inefficient Retry Logic
In `crew.py`, the `@retry` decorator is placed on the entire `run_complaint_pipeline` function.
**Why it's bad:** If Agent 1 and Agent 2 succeed, but Agent 3 fails due to a brief API timeout, the *entire pipeline restarts from scratch*. This wastes API tokens, takes 3x as long, and creates duplicate logs.
**✅ Production Upgrade:**
Apply retry logic at the individual `Task` or `Agent` level. CrewAI allows setting `max_retries` natively on tasks. For external tools, apply the tenacity `@retry` decorator strictly to the tool's execution function (like `department_lookup_tool`).

### ❌ Flaw: State Management and Hardcoded Maps
You have a hardcoded `dept_to_acts` dictionary mapping departments to legal acts directly inside `crew.py` (Lines 118-134). Memory is handled via a custom `session_memory.py`.
**Why it's bad:** Hardcoded dictionaries in orchestration scripts are an anti-pattern. Custom file-based memory won't scale across multiple server instances.
**✅ Production Upgrade:**
- Move `dept_to_acts` into a proper Vector Database or Knowledge Graph. 
- Use a robust database (PostgreSQL or MongoDB) for session memory, and enable CrewAI's native Short-Term/Long-Term memory (which utilizes ChromaDB) for agent contextual awareness across sessions.

---

## 3. File Structure Enhancements

Current Structure issues:
- `researcher.py` is empty.
- `scratch_test.py` is lingering in the root.
- `crew.py` is acting as a monolithic god-script that handles business logic, error parsing, RAG execution, and API routing.

**✅ Recommended Production File Structure:**
```text
NyayaVaani/
├── backend/
│   ├── api.py           # Only FastAPI routing and Job Queue submission
│   ├── tasks.py         # Celery/Background workers
│   └── database.py      # Postgres/Mongo connection
├── src/
│   ├── agents/          # Agent definitions (pure Pydantic config)
│   ├── tasks/           # Task definitions (output_pydantic schemas)
│   ├── tools/           # Custom CrewAI tools (RAG Tool, SerpAPI Tool)
│   ├── crews/           # The unified CivicCrew definition
│   └── rag/             # ChromaDB and indexing logic
├── config/              # Centralized configuration (yaml/env)
└── tests/               # Unit and integration tests
```

### Summary of Next Steps for Production:
1. Refactor `crew.py` to use a single, unified `Crew` object.
2. Replace manual JSON extraction with CrewAI's `output_pydantic` on Tasks.
3. Turn the RAG functionality into a CrewAI `@tool` and assign it to the agents.
4. Move the pipeline execution to an asynchronous background task (Celery/Redis) to prevent HTTP timeouts.
