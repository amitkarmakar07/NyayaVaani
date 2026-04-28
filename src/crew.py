"""
crew.py — NyayaVaani Main Orchestration
Wires all 3 agents sequentially with memory.
Entry point for complaint processing pipeline.
"""

import json
import re
import time
from typing import Dict, Optional
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from crewai import Crew, Process
from langchain_google_genai import ChatGoogleGenerativeAI

from src.agents.analyzer import get_analyzer_agent, get_analyzer_task
from src.agents.router import get_router_agent, get_router_task
from src.agents.writer import get_writer_agent, get_writer_task
from src.rag.retriever import get_rag
from config import config


def extract_json_from_text(text: str) -> dict:
    """Robustly extract JSON from LLM output."""
    if not text:
        return {"raw_output": ""}

    # 1. Try direct parse
    try:
        return json.loads(text.strip())
    except Exception:
        pass

    # 2. Try to find JSON block with regex
    # Pattern to find anything between the first { and the last }
    json_pattern = r'(\{[\s\S]*\})'
    match = re.search(json_pattern, text)
    if match:
        raw_json = match.group(1)
        try:
            return json.loads(raw_json)
        except Exception:
            # Try to fix common JSON issues like trailing commas or single quotes
            try:
                # Basic cleanup
                clean_json = re.sub(r',\s*\}', '}', raw_json)
                clean_json = re.sub(r',\s*\]', ']', clean_json)
                return json.loads(clean_json)
            except Exception:
                pass

    # 3. Try markdown blocks
    patterns = [
        r'```json\s*([\s\S]*?)\s*```',
        r'```\s*([\s\S]*?)\s*```'
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except Exception:
                continue

    logger.warning(f"Could not parse JSON from agent output. Length: {len(text)}")
    return {"raw_output": text}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=20))
def run_complaint_pipeline(
    complaint_text: str,
    user_state: str,
    user_name: str = "Citizen",
    user_address: str = "Not provided",
    user_contact: str = "Not provided"
) -> Dict:
    """
    Full complaint processing pipeline.
    Returns structured output for all 3 agents + RAG legal context.
    """

    logger.info("=" * 60)
    logger.info("NyayaVaani Complaint Pipeline Started")
    logger.info(f"Complaint: {complaint_text[:100]}...")
    logger.info(f"State: {user_state}")
    logger.info("=" * 60)

    try:
        # Initialize Agents (once per run)
        analyzer_agent = get_analyzer_agent()
        router_agent = get_router_agent()
        writer_agent = get_writer_agent()

        # ─── STEP 1: Agent 1 — Complaint Analysis ───────────────────
        logger.info("Running Agent 1: Complaint Analyzer...")
        analyzer_task = get_analyzer_task(analyzer_agent, complaint_text, user_state)
        analyzer_crew = Crew(
            agents=[analyzer_agent],
            tasks=[analyzer_task],
            process=Process.sequential,
            memory=False,
            verbose=False
        )
        analysis_result = analyzer_crew.kickoff()
        time.sleep(3)
        analysis_text = str(analysis_result)
        analysis_data = extract_json_from_text(analysis_text)
        logger.success(f"Agent 1 done. Category: {analysis_data.get('department_category', 'unknown')}")

        # ─── STEP 2: RAG — Fetch Legal Context ──────────────────────
        logger.info("Fetching legal context via Corrective RAG...")
        rag = get_rag()
        department_category = analysis_data.get("department_category", "general")
        problem_summary = analysis_data.get("problem_summary", complaint_text)

        # Map department categories to relevant legal acts for better retrieval
        dept_to_acts = {
            "road": "RTI Act, Consumer Protection Act, public grievance redressal",
            "electricity": "Electricity Act 2003, consumer rights, RTI Act",
            "water": "RTI Act, public utility rights, Consumer Protection Act",
            "ration": "National Food Security Act NFSA 2013, RTI Act",
            "police": "CrPC 1973, IPC 1860, citizen rights against police",
            "property_tax": "RTI Act, municipal corporation grievance",
            "hospital": "Consumer Protection Act 2019, medical negligence rights",
            "education": "Right to Education RTE Act 2009, RTI Act",
            "pension": "RTI Act, pension grievance redressal",
            "land": "Land Acquisition Act 2013, RTI Act",
            "pollution": "Environment Protection Act 1986, pollution control",
            "consumer": "Consumer Protection Act 2019, Consumer Forum filing",
            "banking": "Banking Regulation Act 1949, RBI consumer grievance",
            "corruption": "Prevention of Corruption Act 1988, Lokpal Act 2013",
            "telecom": "Consumer Protection Act 2019, TRAI regulations",
        }
        relevant_acts = dept_to_acts.get(department_category, "RTI Act 2005, citizen grievance rights")

        rag_query = (
            f"{problem_summary}. "
            f"What are citizen rights and legal remedies for {department_category} complaint in India? "
            f"Relevant laws: {relevant_acts}"
        )
        rag_result = rag.retrieve_and_grade(rag_query, department=department_category)

        # If low confidence, try a fallback query focused on RTI (universal legal mechanism)
        if rag_result["confidence"] == "low":
            logger.warning("Low RAG confidence. Trying fallback RTI query...")
            fallback_query = (
                f"Right to Information RTI Act how to file application "
                f"for {department_category} grievance redressal citizen rights"
            )
            fallback_result = rag.retrieve_and_grade(fallback_query, department="general")
            if fallback_result["confidence"] != "low":
                rag_result = fallback_result
                logger.success(f"Fallback RTI query succeeded. Confidence: {fallback_result['confidence']}")

        # Format RAG context for writer agent
        rag_context = ""
        if rag_result["chunks"]:
            for chunk in rag_result["chunks"]:
                rag_context += f"\n[{chunk['source']} | Page {chunk['page']}]\n{chunk['content']}\n"
        else:
            rag_context = "No specific legal context found. Apply RTI Act 2005 general provisions."

        logger.success(f"RAG done. Confidence: {rag_result['confidence']} | Chunks: {len(rag_result['chunks'])}")

        # ─── STEP 3: Agent 2 — Department Router ────────────────────
        logger.info("Running Agent 2: Department Router...")
        router_task = get_router_task(
            agent=router_agent,
            analyzed_complaint=json.dumps(analysis_data, ensure_ascii=False),
            user_state=user_state
        )
        router_crew = Crew(
            agents=[router_agent],
            tasks=[router_task],
            process=Process.sequential,
            memory=False,
            verbose=False
        )
        router_result = router_crew.kickoff()
        time.sleep(3)
        router_text = str(router_result)
        router_data = extract_json_from_text(router_text)
        logger.success(f"Agent 2 done. Department: {router_data.get('department_name', 'unknown')}")

        # ─── STEP 4: Agent 3 — Output Writer ────────────────────────
        logger.info("Running Agent 3: Output Writer...")
        writer_task = get_writer_task(
            agent=writer_agent,
            analyzed_complaint=json.dumps(analysis_data, ensure_ascii=False),
            department_details=json.dumps(router_data, ensure_ascii=False),
            rag_legal_context=rag_context,
            user_name=user_name,
            user_address=user_address,
            user_state=user_state,
            user_contact=user_contact
        )
        writer_crew = Crew(
            agents=[writer_agent],
            tasks=[writer_task],
            process=Process.sequential,
            memory=False,
            verbose=False
        )
        writer_result = writer_crew.kickoff()
        writer_text = str(writer_result)
        writer_data = extract_json_from_text(writer_text)
        logger.success("Agent 3 done. All 3 outputs generated.")

        # ─── FINAL RESPONSE ─────────────────────────────────────────
        return {
            "status": "success",
            "analysis": analysis_data,
            "department": router_data,
            "outputs": writer_data,
            "rag_meta": {
                "confidence": rag_result["confidence"],
                "sources": [c["source"] for c in rag_result["chunks"]],
                "chunks_used": len(rag_result["chunks"])
            }
        }

    except Exception as e:
        logger.error(f"Pipeline error: {str(e)}")
        # If it's a validation error, log more details
        if "ValidationError" in str(e):
            logger.error("DETAILED VALIDATION ERROR DETECTED")
        raise e


def run_followup(
    question: str,
    conversation_history: list,
    original_complaint: dict
) -> str:
    """
    Handle follow-up questions using RAG + conversation context.
    Used for multi-turn chat after initial complaint processing.
    """
    logger.info(f"Follow-up question: {question[:80]}...")

    rag = get_rag()

    # Enrich query with complaint context
    dept_category = original_complaint.get("analysis", {}).get("department_category", "")
    enriched_query = f"{question} (context: {dept_category} complaint)"

    rag_result = rag.answer_question(enriched_query, department=dept_category)

    # Build conversation context
    history_text = ""
    for msg in conversation_history[-6:]:  # last 6 messages for context window
        role = "Citizen" if msg["role"] == "user" else "NyayaVaani"
        history_text += f"{role}: {msg['content']}\n"

    # Final answer with conversation grounding
    llm = ChatGoogleGenerativeAI(
        model=config.LLM_MODEL,
        google_api_key=config.GOOGLE_API_KEY,
        temperature=config.LLM_TEMPERATURE,
        max_tokens=config.LLM_MAX_TOKENS
    )

    from langchain.prompts import ChatPromptTemplate
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are NyayaVaani — a helpful Indian civic grievance assistant.
Answer the citizen's follow-up question using:
1. The conversation history for context
2. The legal context provided

Rules:
- Be concise and helpful
- Reference specific Acts only if in provided legal context
- If unsure, guide to official portal
- Keep answer under 150 words
- Use simple English
"""),
        ("human", """Conversation History:
{history}

Legal Context:
{legal_context}

Citizen's Question: {question}

Answer:""")
    ])

    chain = prompt | llm
    response = chain.invoke({
        "history": history_text,
        "legal_context": rag_result.get("answer", ""),
        "question": question
    })

    return response.content