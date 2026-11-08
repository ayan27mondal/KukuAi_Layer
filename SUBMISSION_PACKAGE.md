# AI Lawyer - Project Overview

## Project Overview
AI Lawyer is a conversational assistant for people in India who need help understanding common legal problems. It gathers basic facts, searches a local legal knowledge base, and explains possible next steps in plain language. It provides general legal information, not legal advice.

## Key Features

| Feature | Description |
|---------|-------------|
| **Problem areas** | Deposit, consumer, salary, civil, and family information |
| **Languages** | English, Hindi, and Hinglish; Bengali and Assamese depend on the selected model |
| **Knowledge base** | Topic-specific notes are stored in the project's `corpus/` folder |
| **Source-aware answers** | Answers use retrieved notes and display chunk citations |
| **Document drafts** | Supported categories can produce DOCX and PDF drafts with placeholders for missing information |
| **Practice mode** | Users can rehearse selected conversations and receive feedback |
| **Safety escalation** | The app flags crisis, criminal, domestic-violence, and court-stage situations, among others |
| **Provider options** | Groq and Gemini can be configured; offline mock mode is available for demos and tests |

## Architecture

```
User message → safety checks → gather case facts → retrieve relevant notes
             → prepare and check response → show answer and disclaimer
```

## Corpus coverage

The corpus is split into topic-specific files. It covers the following areas:

| Topic | Examples of coverage |
|---|---|
| **Deposit** | Model Tenancy Act material and state-specific rent-law notes |
| **Consumer** | Consumer Protection Act, e-Daakhil, fees, limitation, and CCPA |
| **Salary** | Wages, bonus, gratuity, PF, and related topics |
| **Civil** | Civil procedure, contracts, cheque-related matters, arbitration, RERA, MSME, and IBC |
| **Family** | Marriage, maintenance, domestic violence, custody, and succession topics |
| **General and additional topics** | Legal aid, notices, evidence, RTI, FIR, bail, MACT, commercial courts, and partnership |

## Trying the project

### Quick Start (No API Keys)
```bash
cd ai_lawyer
python demo_prototype.py
```

### With a configured model provider
```bash
cp .env.example .env
# Add GROQ_API_KEY and/or GEMINI_API_KEY
streamlit run app.py
```

### Run the evaluation
```bash
python tests/run_eval.py --provider groq,gemini --delay 4
```

## Sample Conversation Flows

### 1. Deposit Dispute (Assam)
```
User: "My landlord has not returned my Rs 40,000 deposit. I moved out three months ago."
Assistant: Asks for details such as the state and whether there was a written agreement.
User: "Assam. There was no written agreement."
Assistant: Summarizes the facts, lists evidence to gather, and shows relevant source notes.
User: "Draft a notice."
Assistant: Offers a template-based draft with placeholders to review and complete.
User: "Let's practise."
Assistant: Starts a role-play and gives feedback when the user ends the practice.
```

### 2. Consumer Complaint (Maharashtra)
```
User: "My laptop is defective and TechMart will not refund Rs 62,000."
Assistant: Asks for details such as the state, purchase date, and available proof.
User: "Maharashtra. I have the invoice and photos."
Assistant: Searches the consumer notes and explains possible next steps with citations.
User: "Draft a complaint."
Assistant: Creates a draft for the user to check and complete.
```

### 3. Safety Escalation
```
User: "I want to end my life."
Assistant: Shows the configured crisis response and directs the user to emergency and crisis support.

User: "My landlord says he'll have me arrested."
Assistant: Escalates the criminal or police-related concern rather than treating it as an ordinary civil question.
```

## Tests

The automated tests cover areas including:

- Pipeline flow, including fact collection, answers, drafts, and practice
- ChromaDB indexing, search, persistence, and fallback
- Safety escalation rules
- LLM utilities and corpus parsing
- Citation validation

## Tech Stack
- **Interface**: Streamlit for the chat and controls
- **Model providers**: Groq and Gemini, selected through configuration
- **Retrieval**: Local BM25 by default, with optional ChromaDB vector search
- **Embeddings**: Gemini when the ChromaDB backend is used
- **Answer checks**: A citation validator checks generated responses against retrieved notes
- **Voice**: Groq Whisper or Gemini for speech input; gTTS for supported speech output
- **Documents**: Jinja2 templates, python-docx, and ReportLab
- **Tests**: pytest, using mock mode for offline checks

## Safety and responsible use
- The assistant is for general legal information, not legal advice.
- It is designed not to promise outcomes or offer litigation strategy.
- It checks citations against retrieved knowledge-base notes; this does not prove that a legal statement is correct or current.
- Deterministic escalation rules handle certain high-risk situations.
- Responses include a disclaimer and refer users to legal aid where appropriate.
- Real-provider mode sends relevant text or audio to the configured external provider. Avoid entering sensitive details unless you have reviewed the provider's privacy terms.

## Provider notes
Model names and free-tier terms change. Check the providers' current documentation before a demo or deployment.

| Provider | Configured use |
|---|---|
| Groq | Chat responses and speech recognition |
| Gemini | Chat responses and optional ChromaDB embeddings |

## Submission Checklist
- [ ] Demo runs: `python demo_prototype.py`
- [ ] Tests pass: `python -m pytest tests -v`
- [ ] Real evaluation: `python tests/run_eval.py --provider groq,gemini --delay 4`
- [ ] Output folder: `tests/outputs/groq+gemini/` with REPORT.md + metrics.json
- [ ] Streamlit app: `streamlit run app.py` (with API keys)
- [ ] Hindi PDF font: `assets/fonts/NotoSansDevanagari-Regular.ttf`

## Project files

- `app.py` starts the Streamlit interface.
- `demo_prototype.py` runs scripted scenarios in mock mode.
- `lawyer/` contains the workflow, retrieval, model, voice, document, and safety modules.
- `corpus/` contains the legal notes used for retrieval.
- `templates/` contains the document layouts used to create drafts.
- `tests/` contains automated tests and model-evaluation cases.
- `docs/DEMO_SCRIPT.md` has a suggested walkthrough for a short demonstration.

For setup and the full architecture explanation, see `README.md`.