<div align="center">

![NyayaVaani Banner](./assets/banner.png)

# ⚖️ NyayaVaani: Agentic AI Civic Assistant

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Gemini](https://img.shields.io/badge/Google%20Gemini-2.5%20Flash-orange?logo=google&logoColor=white)](https://deepmind.google/technologies/gemini/)
[![Whisper](https://img.shields.io/badge/OpenAI%20Whisper-V3-black?logo=openai&logoColor=white)](https://openai.com/research/whisper)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**NyayaVaani** (Voice of Justice) is an advanced multimodal AI platform designed to bridge the gap between Indian citizens and the government by automating civic grievance redressal and legal awareness through **Agentic AI** and **Corrective RAG**.

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

### 📚 Corrective RAG (CRAG)
A high-accuracy legal knowledge base that prevents hallucinations:
- **Hybrid Search**: Semantic similarity (Dense) combined with keyword matching (BM25 Sparse).
- **Self-Grading**: Every retrieved chunk is graded for relevance by an LLM before being used.
- **Strict Grounding**: Citations from Indian Statutes are provided for every legal answer.

### 🎙️ Multimodal Accessibility
- **Voice-to-Action**: Integrated with **OpenAI Whisper** for high-accuracy voice transcription.
- **Vernacular Support**: Designed to handle mixed language (Hinglish) inputs common in India.

### 🎨 Premium UI/UX
- **Clean Aesthetic**: A modern White and Orange theme designed for professional civic engagement.
- **Compact Ratio**: Optimized layout for 80% screen ratio, ensuring a focused user experience.

---

## 🏗️ System Architecture

```mermaid
graph TD
    A[Citizen Input: Text/Voice] --> B{Input Type}
    B -- Voice --> C[OpenAI Whisper STT]
    B -- Text --> D[FastAPI Backend]
    C --> D
    
    D --> E[CrewAI Agentic Pipeline]
    subgraph "Multi-Agent System"
        E --> E1[Grievance Analyst]
        E1 --> E2[Department Scout]
        E2 --> E3[Document Architect]
    end
    
    D --> F[Corrective RAG Pipeline]
    subgraph "CRAG"
        F --> F1[Hybrid Search: ChromaDB + BM25]
        F1 --> F2[LLM Relevance Grader]
        F2 --> F3[Source Grounded Generation]
    end
    
    E3 --> G[Formal Letter / Email / SMS]
    F3 --> H[Legal Advice with Citations]
    G --> I[Citizen Dashboard]
    H --> I
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

## 🛣️ Future Roadmap

- [ ] **Multi-lingual Support**: Expanding to 12+ regional Indian languages.
- [ ] **Direct Portal Integration**: One-click submission to CPgrams and State portals.
- [ ] **AI Video Summaries**: Explaining legal rights via AI-generated video avatars.
- [ ] **Mobile App**: Dedicated Flutter app for field-use by citizens.

---

## ⚖️ License
Distributed under the MIT License. See `LICENSE` for more information.

---

## 👨‍💻 Author
**Amit Karmakar**  
*Data Science & AI Developer*

[LinkedIn](https://www.linkedin.com/in/amitkarmakar07/) • [Portfolio](https://amitkarmakar.com/) • [GitHub](https://github.com/amitkarmakar07)
