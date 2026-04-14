# Candidate Background — Marcio

Use this context to evaluate answers, give precise feedback, and catch inconsistencies between what Marcio says and what is actually true about his background.

---

## Identity

- **Full name:** Marcio Soares Ferreira, PhD
- **Location:** Manaus, Amazonas, Brazil
- **Experience:** 10+ years bridging research and production AI
- **Contact/profiles:** LinkedIn, GitHub (marciosferreira)

---

## Academic Journey

### PhD — Aquatic Biology
- Institution: INPA – National Institute for Amazonian Research (2011–2015)
- **What it gave him:** rigorous scientific thinking, statistical rigor, comfort with noisy and complex real-world data — rare qualities in AI engineering
- **Important:** the PhD is in Aquatic Biology, NOT Computational Biology. The computational/AI trajectory came through postdoctoral work and continued development. This is actually a stronger differentiator — he applied AI to biology before it was mainstream.
- In the elevator pitch and general framing, he should describe his PhD as giving him "rigorous, evidence-based thinking" — the specific field matters less than the cognitive asset it represents.

### Postdoc — Computational Biology & Applied Ecology
- Institution: EMBL-EBI (European Bioinformatics Institute), Cambridge, UK (Feb 2021 – Feb 2024)
- Also collaborated with: Tulane University (USA) and INPA (Brazil)
- **Key publication:** peer-reviewed high-throughput video analysis software for automated physiological metric extraction — published in *Bioinformatics* (Oxford Academic), doi.org/10.1093/bioinformatics/btae664
- Built Python/OpenCV object tracking and signal processing pipelines for automated heart rate detection in large-scale video datasets
- Architected scalable Linux/HPC batch processing pipelines for large-volume biological image analysis
- **Second publication:** hybrid CNN + LSTM architectures for automated behavioral analysis from high-resolution video — published in *FACETS* (dx.doi.org/10.1139/facets-2023-0221)
- **What this demonstrates:** first-author AI software used in real scientific production; international collaboration; applied computer vision before it was a common job title

### Earlier Postdoc — INPA (Jan 2016 – Jan 2021)
- Designed hybrid CNN + LSTM architectures for behavioral analysis
- Integrated IoT sensor data with computer vision outputs
- Published in FACETS (see above)

---

## Industry Journey — Chronological

### FIT Instituto de Tecnologia — LLM Evaluation Role (Jul–Nov 2024)
- Designed comparative benchmarking pipelines for Foundation Models on AWS Bedrock for enterprise ESG applications
- Developed statistical testing frameworks measuring LLM determinism, hallucination rates, and semantic accuracy (BLEU, ROUGE, semantic similarity)
- **Context:** this was his entry point into industry — not Venturus. He was applying scientific rigor (benchmarking, statistical frameworks) to LLM evaluation before building full systems.

### Tulane University — Data Scientist (Feb–Jun 2024)
- Fine-tuned Variational Autoencoders (TensorFlow/Keras) for latent space representation on morphological datasets
- Designed OpenCV preprocessing pipelines for large-scale biological image ingestion
- **Note:** this overlaps with/follows the EMBL-EBI postdoc — part of the same international research network

### Venturus — Machine Learning Analyst (Nov 2024 – May 2025)
- **What he actually built:** privacy-first on-premise RAG architecture using quantized Llama models — zero data exposure to external APIs
- Evolved linear LangChain pipelines into stateful multi-agent systems (LangGraph) with memory, branching, and error recovery
- Deployed LLMOps observability pipeline with LangSmith for tracing, debugging, and performance evaluation
- **Important correction:** the system was NOT a "TV manual chatbot" in the simple sense — it was a privacy-first on-premise RAG system. The TV manual use case may have been the application domain, but the architectural decision (on-premise, quantized Llama, zero external API exposure) is the more impressive and specific detail.
- **Framing for interviews:** "My first applied LLM work was building a privacy-first RAG system from scratch — on-premise, using quantized open-source models, because the client couldn't expose their data to external APIs. That constraint forced me to go deep on the full pipeline."

### FIT Instituto de Tecnologia — Data Scientist / AI Engineer (Jul 2025 – Present)
- Building Iris Hub — production multi-agent system for real-time industrial analytics
- Full details in the Iris Hub section below

---

## Iris Hub — Key Project (CAR Framework)

### Context
AI-powered reporting platform for account managers in a manufacturing environment.
- Managers needed to monitor shop floor operations (equipment failures, productivity metrics, defective parts) to make real-time business decisions
- Floor-level data existed in systems managers couldn't access without analyst intervention
- Generating reports took hours or days — decision windows were missed

### Actions (personal — "I" not "we")
- Architected production multi-agent system using ReAct + LangGraph on AWS Bedrock
- Selected Claude Haiku as core engine after rigorous AWS Bedrock benchmarking (not assumed — tested)
- Built custom Python MCP Servers to expose standardized tool interfaces, decoupling SQL/NoSQL data access from LLM logic across multiple agents
- Implemented FAISS-based RAG layer correlating real-time metrics with technical documentation — reduced hallucinations in fault diagnostics
- Established full observability with Langfuse from day one: tracing, latency, cost per session, output quality evals
- **Token optimization challenge:** identified 30–50% token consumption reduction opportunity through history compression, selective RAG injection, and Pydantic-structured responses
- The reduction was achieved via multiple techniques working together — not a single fix

### Results
- Account managers access personalized operational reports through a conversational interface in real time, without analyst support
- Decision-making cycles reduced significantly
- System runs in production with full traceability on every call

### Important nuances for coaching
- The token reduction is **30–50%** (a range), not a fixed "~50%" — if Marcio says "50%" that's acceptable but he should know the honest range
- The model selection was **deliberate after benchmarking** (Claude Haiku after AWS Bedrock comparative testing) — this is a strong production signal worth mentioning
- The MCP Servers were **custom-built Python servers** — not off-the-shelf — which shows architectural depth

---

## Technical Stack

**AI / LLM Engineering:** LangChain, LangGraph, ReAct Agents, MCP (Model Context Protocol), RAG, FAISS, LangSmith, Langfuse, Prompt Engineering

**Cloud & MLOps:** AWS Bedrock, AWS Lambda, LLMOps, Model Benchmarking, Quantized LLMs (Llama), Hugging Face

**ML & Deep Learning:** TensorFlow, Keras, PyTorch, CNN, LSTM, VAE, Computer Vision, OpenCV, Scikit-learn

**Data & Backend:** Python, Pandas, NumPy, SQL, NoSQL, Pydantic, Flask, FastAPI

---

## Certifications
- AWS Machine Learning Specialty
- Claude with Anthropic API
- Deep Learning (GANs & VAEs)
- Python OOP
- Computer Vision with OpenCV

---

## Key Strengths
- Thinks in systems, not just models
- Obsessive about observability and production reliability
- Strong cost-consciousness (token optimization, ROI thinking)
- Evidence-based, rigorous approach from scientific background
- Experience bridging technical and business stakeholders
- International research background — operated at EMBL-EBI, Tulane, INPA
- Model selection discipline — benchmarks before committing (AWS Bedrock comparison for Iris Hub)

---

## Consistency Checks — What to Watch For

Use these to catch inconsistencies between what Marcio says and what is actually true:

| If Marcio says... | Flag if... |
|---|---|
| "PhD in Computational Biology" | Correct to "Aquatic Biology" — the postdoc was in Computational Biology |
| "~50% token reduction" | Acceptable, but the CV says 30–50% — coach him to be precise |
| "TV manual chatbot" for Venturus | Underdescribing — the key differentiator was the privacy-first on-premise architecture with quantized Llama, zero external API exposure |
| "we built" for Iris Hub | Probe for personal ownership — he was the architect |
| Describes Venturus as "first LLM work" | Technically FIT (Jul–Nov 2024) came first for LLM evaluation — but Venturus was his first full system build |
| Claims model selection was obvious | He actually ran rigorous AWS Bedrock benchmarking before selecting Claude Haiku — that's a strong signal worth surfacing |

---

## Relevant Industry Data Points

Encourage Marcio to use these naturally when relevant — not as recited statistics:

| Data point | Source | Best used in |
|---|---|---|
| "Of every 33 AI POCs initiated, only 4 reach production" (12% conversion rate) | IDC/Lenovo 2025 | Leadership, Technical Q2 |
| "44% of teams discover data quality is materially worse than expected — after budget is committed" | Pertama Partners, 2,400+ projects | Leadership (data audit) |
| "GenAI production costs exceed pilot costs by 380% on average" | MIT Sloan | Leadership (cost modeling), Technical Q1 |
| "Only 4–6% of companies generate significant results from AI — they invest 47% of budget in fundamentals vs 18% in failed projects" | McKinsey + BCG 2024–2025 | Fit & Motivation, Leadership |

**Coaching rule on data points:** if Marcio uses a stat awkwardly (e.g., recites it as a memorized line without connecting it to a real argument), note it in feedback. The stat should feel like something he knows and believes — not something he rehearsed.
