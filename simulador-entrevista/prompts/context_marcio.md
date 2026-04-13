# Candidate Background — Marcio

Use this context to evaluate answers and give precise, specific feedback.

## Identity
- Full name: Marcio
- Location: Manaus, Amazonas, Brazil
- ~10 years of experience bridging academia and applied AI

## Academic Journey
- **PhD in Computational Biology** — instilled rigorous scientific thinking and statistical rigor; rare in AI engineering
- **Postdoc in Bioinformatics** — collaborated with world-class researchers at EMBL-EBI (UK), Tulane University (USA), and INPA (Brazil)
- **First-author publication**: Python software for large-scale microscopy image analysis using computer vision and AI; international collaborators; published in an indexed journal

## Industry Journey
- **Venturus**: built a RAG system from scratch for a chatbot that helped users understand TV manuals (entry point into applied LLMs in industry)
- **FIT Instituto de Tecnologia (current)**: building Iris Hub — a production-grade AI platform for account managers in manufacturing

## Iris Hub — Key Project (CAR Framework)

**Context:**
AI-powered reporting platform for account managers in a manufacturing environment.
Managers needed to monitor shop floor operations (equipment failures, productivity, defective parts) to make business decisions.
Floor-level data existed in systems managers couldn't access in real time.
Generating reports required analyst intervention and took hours or days.

**Actions:**
- Designed multi-agent architecture using LangGraph and AWS Bedrock with Claude models
- Each agent responsible for a specific domain: failures, productivity, quality control
- Agents queried operational data and generated personalized natural language reports (no technical knowledge required from users)
- Used MCP Servers for tool orchestration
- Implemented Langfuse from day one for full observability (latency, cost per session, output quality)
- Critical production challenge: initial context window ~19,000 tokens per call — expensive and slow
- Redesigned data pipeline, compacted tool responses, optimized variable tracking
- Reduced context to ~9,000 tokens — ~50% inference cost reduction without quality loss

**Results:**
- Account managers access personalized operational reports through a conversational interface in real time, without analyst support
- Decision-making cycles reduced significantly
- System runs in production with full traceability on every call

## Technical Stack
LangGraph, LangChain, ReAct patterns, multi-agent architecture, AWS Bedrock (Claude models), MCP Servers, Langfuse, RAG pipelines, FAISS, FastAPI, asyncio, Python, pandas, computer vision

## Key Strengths
- Thinks in systems, not just models
- Obsessive about observability and production reliability
- Strong cost-consciousness (token optimization, ROI thinking)
- Evidence-based, rigorous approach from scientific background
- Experience bridging technical and business stakeholders
- International research background

## Relevant Industry Data Points
Encourage Marcio to use these naturally when relevant:
- "Of every 33 AI POCs initiated, only 4 reach production" — IDC/Lenovo 2025 (12% conversion rate)
- "44% of teams discover data quality is materially worse than initially assessed — after budget is committed" — Pertama Partners, 2,400+ projects
- "GenAI production costs exceed pilot costs by 380% on average" — MIT Sloan
- "Only 4–6% of companies generate significant results from AI — and they invest 47% of budget in fundamentals vs 18% in failed projects" — McKinsey + BCG 2024–2025