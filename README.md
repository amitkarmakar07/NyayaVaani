<div align="center">

![NyayaVaani Banner](./assets/banner.png)

# ⚖️ NyayaVaani: Agentic AI Civic Assistant

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Gemini](https://img.shields.io/badge/Google%20Gemini-2.5%20Flash-orange?logo=google&logoColor=white)](https://deepmind.google/technologies/gemini/)
[![Whisper](https://img.shields.io/badge/OpenAI%20Whisper-V3-black?logo=openai&logoColor=white)](https://openai.com/research/whisper)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**NyayaVaani** (Voice of Justice) is an advanced multimodal AI platform designed to bridge the gap between Indian citizens and the government by automating civic grievance redressal and legal awareness through **Agentic AI** and **Hybrid Legal RAG**.

[Explore Demo](#-installation--setup) • [Features](#-key-features) • [Architecture](#-system-architecture) • [Roadmap](#-future-roadmap)

</div>

---

## 📖 Table of Contents
- [Project Overview](#-project-overview)
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Tech Stack](#-tech-stack)
- [Installation & Setup](#-installation--setup)
- [Screenshots](#-screenshots)
- [Future Roadmap](#-future-roadmap)
- [Author](#-author)

---

## 🌟 Project Overview

Filing a civic grievance in India is often a complex and intimidating process. **NyayaVaani** simplifies this by allowing users to speak or type their problems in natural language. The system's "AI Agents" then work collaboratively to identify the correct legal department, calculate severity, and draft perfectly formatted formal documents.

---

## 🚀 Key Features

### 🤖 Multi-Agent Agentic Pipeline
Unlike traditional chatbots, NyayaVaani uses a **collaborative agentic workflow** (via CrewAI):
- **Grievance Analyst**: Breaks down the user's issue and identifies legal violations.
- **Department Scout**: Performs real-time research to find Central/State authorities and active helplines.
- **Document Architect**: Drafts legally-grounded Letters, Emails, and SMS alerts.

### 📚 Hybrid Legal RAG
A high-accuracy legal knowledge base that prevents hallucinations:
- **Hybrid Search**: Semantic similarity (Dense) combined with keyword matching (BM25 Sparse).
- **Cross-Encoder Reranking**: Every retrieved chunk is reranked and graded for relevance before being used.
- **Strict Grounding**: Citations from Indian Statutes are provided for every legal answer.

### 🎙️ Multimodal Accessibility
- **Voice-to-Action**: Integrated with **OpenAI Whisper** for high-accuracy voice transcription.
- **Vernacular Support**: Designed to handle mixed language (Hinglish) inputs common in India.

### 🎨 Premium UI/UX
- **Clean Aesthetic**: A modern White and Orange theme designed for professional civic engagement.
- **Compact Ratio**: Optimized layout for 80% screen ratio, ensuring a focused user experience.

---

## 🏗️ System Architecture

### 🤖 1. CrewAI Multi-Agent Execution Architecture
The multi-agent workflow handles civic complaint breakdown, authority lookup, statutory legal research, formal complaint drafting, and social media escalation in a strict sequential pipeline, wrapped under end-to-end security guardrails and OpenTelemetry observability:

```mermaid
flowchart TD
    subgraph InputLayer ["1. Multimodal Input Layer"]
        A["Citizen Input\n(Text / Raw Audio Bytes)"] --> B{"Input Channel"}
        B -- Audio --> C["OpenAI Whisper v3 STT\n(Hindi / English / Hinglish)"]
        B -- Text --> D["Raw Text Prompt"]
        C --> D
    end

    subgraph InputGuardrailLayer ["2. Input Guardrails Mesh"]
        D --> E["NyayaVaaniGuardrail.validate_input_async()"]
        E --> E1["Layer 1: Regex Scanner\n(PII: Aadhaar/PAN & Jailbreak Check)"]
        E1 --> E2["Layer 2: Fast LLM Evaluator\n(gpt-4o-mini Topic & Safety Filter)"]
    end

    subgraph CrewAgenticPipeline ["3. CrewAI Multi-Agent Sequential Pipeline"]
        E2 -- "is_safe == True" --> F["NyayaVaaniCrew.kickoff()"]

        subgraph SequentialAgents ["Sequential Agent DAG"]
            F --> G["1. Grievance Analyst\n(analyzer_agent)"]
            G --> G_Out["Output: AnalyzerOutput\n(Category, Severity, Summary, Impact)"]
            
            G_Out --> H["2. Department Scout\n(router_agent)"]
            H <--> H_Tools["Tools: state_helpline_tool &\ndepartment_lookup_tool"]
            H --> H_Out["Output: RouterOutput\n(Nodal Dept, Helplines, Escalation Path)"]

            G_Out --> I["3. Legal Researcher\n(researcher_agent)"]
            I <--> I_Tools["Tool: legal_rag_tool\n(Retrieves Acts & Statutory Sections)"]
            
            H_Out & I_Tools --> J["4. Document Architect\n(writer_agent)"]
            J --> J_Out["Output: WriterOutput\n(Formal Letter, Email Draft, Rights)"]

            G_Out & H_Out --> K["5. Social Advocacy Scout\n(social_media_agent)"]
            K <--> K_Tools["Tool: twitter_handle_lookup_tool"]
            K --> K_Out["Output: SocialMediaOutput\n(Public Escalation Tweet & Handles)"]
        end
    end

    subgraph OutputGuardrailLayer ["4. Output Guardrail Shield"]
        J_Out & K_Out --> L["NyayaVaaniGuardrail.validate_output_async()"]
        L --> L1["Toxicity & Content Safety Scan"]
    end

    subgraph FinalOutputLayer ["5. Delivery & UI Integration"]
        L1 --> M["Aggregated Response Payload\n(Analysis, Dept Routes, Letter, Tweet)"]
        M --> N["Session Memory & Citizen UI"]
    end

    subgraph ObservabilityMesh ["🔭 End-to-End Observability Layer"]
        CrewAgenticPipeline -. "Spans, Latency, Token Usage" .-> OTLP["OpenTelemetry Collector"]
        InputGuardrailLayer -. "Span Traces" .-> OTLP
        OutputGuardrailLayer -. "Span Traces" .-> OTLP
        OTLP ==> LF["Langfuse Dashboard\n(CrewAIInstrumentor + LiteLLMInstrumentor)"]
    end
```

---

### 📚 2. Hybrid Legal RAG Pipeline Architecture
The RAG pipeline provides statutory answers to citizen legal questions using hybrid dense-sparse retrieval, cross-encoder reranking, confidence scoring, and strict citation enforcement:

```mermaid
flowchart TD
    subgraph RAGInputLayer ["1. RAG Query Input"]
        R_In["Citizen Legal Question\n(e.g., 'What are my rights under RTI?')"] --> R_Guard["NyayaVaaniGuardrail.validate_input_async()"]
    end

    subgraph RAGCorePipeline ["2. Hybrid Legal RAG Pipeline (LegalRAGPipeline)"]
        R_Guard -- "is_safe == True" --> R_Hybrid["HybridRetriever.hybrid_search()"]
        
        subgraph HybridSearch ["Hybrid Retrieval Subsystem"]
            R_Hybrid --> R_Dense["Dense Semantic Search\n(ChromaDB + BAAI/bge-m3 Embeddings)"]
            R_Hybrid --> R_Sparse["Sparse Keyword Search\n(BM25Okapi for Section / Act Titles)"]
            R_Dense & R_Sparse --> R_RRF["Reciprocal Rank Fusion (RRF)\nCombines Dense & Sparse Scores"]
        end

        subgraph RerankGrade ["Reranking & Confidence Evaluation"]
            R_RRF --> R_Rerank["Cross-Encoder Predictor\n(ms-marco-MiniLM-L-6-v2)"]
            R_Rerank --> R_Eval{"Evaluate Chunk Confidence"}
            R_Eval -- ">= 2 Top Chunks" --> C_High["Confidence: HIGH"]
            R_Eval -- "1 Top Chunk" --> C_Med["Confidence: MEDIUM"]
            R_Eval -- "0 Top Chunks" --> C_Low["Confidence: LOW\n(Triggers UI Safety Warning)"]
        end

        subgraph AnswerGen ["Strict Legal Answer Generation"]
            C_High & C_Med & C_Low --> R_Prompt["Strict System Prompt\n(Citation Enforcement & Zero Inference)"]
            R_Prompt --> R_LLM["LLM Generation\n(ChatGoogleGenerativeAI / ChatOpenAI)"]
        end
    end

    subgraph RAGOutputGuardrail ["3. Output Safety Filter"]
        R_LLM --> R_OutGuard["NyayaVaaniGuardrail.validate_output_async()"]
        R_OutGuard --> R_Final["Streaming Response + Citation Sources\n(Rendered on RAG Chatbot UI)"]
    end

    subgraph RAGObservability ["🔭 RAG Observability Subsystem"]
        RAGCorePipeline -. "Traces & CallbackHandler" .-> RAG_OTLP["OpenTelemetry / Langfuse Handler"]
        RAG_OTLP ==> RAG_LF["Langfuse Tracing Dashboard\n(Span Metrics, Rerank Scores, Confidence Logs)"]
    end
```

---

## 🛠️ Tech Stack

| Category | Technology |
| :--- | :--- |
| **Backend** | Python, FastAPI, Uvicorn |
| **LLM Orchestration** | CrewAI, LangChain |
| **Generative Models** | Google Gemini 2.5 Flash Lite |
| **Speech-to-Text** | OpenAI Whisper (v3) |
| **Vector DB** | ChromaDB |
| **Embeddings** | HuggingFace BGE-M3 |
| **Frontend** | HTML5, CSS3 (Vanilla), JavaScript (ES6) |

---

## 📦 Installation & Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/amitkarmakar07/NyayaVaani.git
   cd NyayaVaani
   ```

2. **Configure Environment**
   Create a `.env` file in the root:
   ```env
   GOOGLE_API_KEY=your_gemini_key
   OPENAI_API_KEY=your_whisper_key
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Launch Application**
   ```bash
   python -m backend.api
   ```
   *Open `http://localhost:8000/frontend/index.html` in your browser.*
---

## ⚖️ License
Distributed under the MIT License. See `LICENSE` for more information.

---

## 👨‍💻 Author
**Amit Karmakar**  
*Data Science & AI Developer*

[LinkedIn](https://www.linkedin.com/in/amit-karmakar-355817258/)
