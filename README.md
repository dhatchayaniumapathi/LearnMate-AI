# LearnMate AI

> **An advanced, full-stack, AI-powered personalized learning platform tailored for college students.**

LearnMate AI empowers students with conversational Socratic tutoring, document-grounded question answering (RAG), automated assessment generation, spaced-repetition study planning, and adaptive performance analytics.

---

## Key Features

1. **AI Study Assistant & Conversational Tutor**
   - Context-aware, Socratic tutoring with short-term session memory and long-term learning profile retention.
   - Low-latency response streaming with real-time Markdown and KaTeX mathematical notation rendering.

2. **Multimodal Document-Based RAG**
   - Ingestion and semantic chunking of lecture slides, textbook PDFs, images, and notes.
   - Strict source grounding with clickable page and section citations.

3. **Automated Study Material Generation**
   - **Notes & Summaries:** Structured Cornell notes, executive summaries, and key concept glossaries.
   - **Quiz & Mock Test Generator:** MCQs, fill-in-the-blank, and conceptual questions with detailed distractor rationale.
   - **Flashcard Deck Generator:** Automated deck creation with question-answer pairs and difficulty tagging.

4. **Adaptive Learning Engine**
   - Evaluates quiz submissions and detects specific conceptual weaknesses.
   - Dynamically updates the student's mastery profile and surfaces targeted revision recommendations.

5. **Smart Study Planner with Spaced Repetition (SRS)**
   - Algorithmic review scheduling based on the SuperMemo-2 (SM-2) algorithm.
   - Automated exam countdown timetable prioritizing weak and high-weight subjects.

6. **Provider-Independent Multi-LLM Gateway**
   - Decoupled gateway supporting **Google Gemini**, **Groq**, **Anthropic Claude**, and **OpenAI**.
   - Independent embedding pipeline allowing local or cloud embedding providers without coupling to the chat LLM.
   - Capability-aware routing and graceful degradation when API keys are absent.

7. **Enterprise Security & Multi-Tenancy**
   - JWT authentication featuring short-lived access tokens and **rotating refresh tokens** in secure HTTP-only cookies.
   - Token family reuse detection to prevent replay attacks.
   - Strict row-level tenancy in PostgreSQL and user-scoped collections in ChromaDB.

---

## Technology Stack

### Frontend
- **Framework:** [React](https://react.dev/) + [Vite](https://vitejs.dev/) with [TypeScript](https://www.typescriptlang.org/)
- **Styling & Components:** [Tailwind CSS](https://tailwindcss.com/), [Shadcn UI](https://ui.shadcn.com/), [Lucide React](https://lucide.dev/)
- **State Management & Caching:** [Zustand](https://github.com/pmndrs/zustand), [TanStack Query](https://tanstack.com/query)
- **Content Rendering:** `react-markdown`, `remark-math`, `rehype-katex` ($LaTeX$), `recharts`

### Backend
- **Framework:** [FastAPI](https://fastapi.tiangolo.com/) (Async, Python 3.11+)
- **Data Validation & Settings:** [Pydantic v2](https://docs.pydantic.dev/) & Pydantic Settings
- **Primary Database:** [PostgreSQL](https://www.postgresql.org/) via [Neon Serverless](https://neon.tech/) with [SQLAlchemy 2.0 (Async)](https://www.sqlalchemy.org/) and [Alembic](https://alembic.sqlalchemy.org/)
- **Vector Database:** [ChromaDB](https://www.trychroma.com/) (User-isolated collections)
- **Orchestration:** [LangChain](https://www.langchain.com/) / LangChain Core
- **Authentication:** JWT (OAuth2 Password Bearer) with Argon2 password hashing and HTTP-only cookie token rotation

---

## System Architecture

```plaintext
                    +------------------------------------+
                    |   React + Vite Frontend (SPA)      |
                    | (Tailwind, Zustand, TanStack Query)|
                    +-----------------+------------------+
                                      |  HTTPS / SSE / REST
                                      v
                    +------------------------------------+
                    |        FastAPI API Gateway         |
                    |   - JWT & Refresh Token Rotation   |
                    |   - User Tenancy & Rate Limiter    |
                    +--------+------------------+--------+
                             |                  |
           +-----------------+                  +-----------------+
           v                                                      v
+-------------------------+                           +-------------------------+
|   Domain Core Services  |                           |  Decoupled Gateways     |
| - Document & Ingestion  |                           | - Provider-Agnostic LLM |
| - Conversational Tutor  |                           |   (Gemini, Groq, Claude)|
| - Assessment Generator  |                           | - Independent Embedding |
| - Adaptive Learning Eng |                           |   (BGE, OpenAI, Gemini) |
| - Spaced Repetition/SRS |                           +------------+------------+
+------------+------------+                                        |
             |                                                     |
             +----------------------+------------------------------+
                                    |
                    +---------------+---------------+
                    v                               v
       +-------------------------+     +-------------------------+
       |   Neon PostgreSQL DB    |     |   ChromaDB Vector Store |
       | (Users, Chats, Quizzes, |     | (User-Isolated Chunks & |
       | Plans, Mastery Records) |     |  Source Citations)      |
       +-------------------------+     +-------------------------+
```

---

## Development Roadmap & Milestones

- [ ] **Phase 1: Foundations, Database, Security & App Shell**
  - Project scaffolding, Neon PostgreSQL async engine, Alembic migrations.
  - JWT auth with rotating refresh-token cookies, token family reuse detection.
  - User profile endpoints and responsive React application shell.
- [ ] **Phase 2: Decoupled Vector Ingestion & Multi-Tenant Storage**
  - Document parser (PDF, images, text) with layout-aware semantic chunking.
  - ChromaDB integration with user-scoped collections and metadata filtering.
- [ ] **Phase 3: LLM Gateway & Conversational AI Tutor**
  - Provider-independent LLM Gateway with capability detection and dynamic configuration.
  - Initial provider integration (e.g., Google Gemini or Groq).
  - SSE streaming tutor chat with KaTeX math and Markdown formatting.
- [ ] **Phase 4: Content Generation & Adaptive Learning Engine**
  - Automated Cornell notes, summaries, and structured quiz generation.
  - Adaptive evaluation: error distractor analysis and concept mastery vector tracking.
- [ ] **Phase 5: Spaced Repetition (SM-2), Study Planner & Multi-Provider Extension**
  - SuperMemo-2 (SM-2) flashcard review queue.
  - Dynamic study schedule generator prioritizing weak topics.
  - Extension of LLM Gateway to Groq, Claude, and optional OpenAI.
- [ ] **Phase 6: Performance Analytics, Hardening & End-to-End Verification**
  - Graphical mastery charts, study streak tracking, and weak-spot diagnostics.
  - Comprehensive unit/integration testing and performance profiling.

---

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+ & npm
- PostgreSQL instance (e.g., [Neon.tech](https://neon.tech))

---

### Backend Setup (FastAPI)

1. **Navigate to the backend directory:**
   ```bash
   cd backend
   ```

2. **Create and activate a virtual environment:**
   ```bash
   # Windows (PowerShell)
   python -m venv .venv
   .venv\Scripts\Activate.ps1

   # Linux / macOS
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env to add your Neon DATABASE_URL and any optional LLM keys
   ```

5. **Start the development server:**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
   - API Root: `http://localhost:8000/`
   - Interactive Swagger Docs: `http://localhost:8000/docs`
   - Health Check: `http://localhost:8000/api/v1/health`

6. **Run backend tests:**
   ```bash
   pytest
   ```

---

### Frontend Setup (React + Vite + TypeScript)

1. **Navigate to the frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   ```

4. **Start the development server:**
   ```bash
   npm run dev
   ```
   - Frontend Dashboard: `http://localhost:5173/`

5. **Typecheck & Production Build:**
   ```bash
   npm run build
   ```

---

## License

This project is licensed under the MIT License - see the LICENSE file for details.
