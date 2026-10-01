# Coursera AI Course Automation Agent (`coursera-agent`)

A production-grade, local Coursera course automation agent built in Python for macOS. The agent automates the mechanical parts of completing Coursera courses—such as navigating syllabus structures, processing videos and reading materials, and logging progress in SQLite—while pairing Google Gemini with a local LM Studio LLM for educational reasoning.

---

## 1. Primary Objectives & Highlights

- **Python 3.11+ Async Architecture**: Built from the ground up on `asyncio`, async Playwright, and async SQLite (`SQLAlchemy` + `aiosqlite`).
- **Persistent Browser Profile**: Keeps you logged into Coursera safely without ever storing or handling passwords.
- **Dual AI Router & Consensus Engine**: Primary reasoning with Google Gemini (`from google import genai`) and local OpenAI-compatible models (via LM Studio at `http://127.0.0.1:1234/v1`).
- **AI Verification & Confidence**: Cross-examines candidate answers and flags disagreements for review.
- **Strict Assessment Boundary**: Distinguishes between practice activities and graded assessments. For graded quizzes, the agent extracts visible questions, generates candidate reasoning, and **pauses to require the user to submit in the browser**. It will **never** auto-submit graded assessments.
- **Crash Recovery & Resume**: Resumes from the exact module and lesson state if interrupted.
- **Visual Intelligence**: Captures targeted screenshots of diagram/canvas questions for multimodal analysis.
- **macOS Native Notifications**: Desktop banner alerts with sound when assessments require attention or modules finish.

---

## 2. Architecture Overview

```text
                                +-------------------+
                                |    CLI / Main     |
                                +---------+---------+
                                          |
                      +-------------------+-------------------+
                      |                                       |
            +---------v---------+                   +---------v---------+
            | Automation Engine |                   | Diagnostics Doctor|
            +----+---------+----+                   +-------------------+
                 |         |
    +------------+         +------------+
    |                                   |
+---v----------------+             +----v----------------+
| Browser / Session  |             | AI Router           |
| (Playwright async) |             | (Gemini + LMStudio) |
+---+----------------+             +----+----------------+
    |                                   |
+---v----------------+             +----v----------------+
| Coursera Detectors |             | Verification &      |
| & Navigation       |             | Confidence System   |
+---+----------------+             +----+----------------+
    |                                   |
+---v----------------+             +----v----------------+
| Assessment Engine  |             | SQLite State Store  |
| (Review Barrier)   |             | & Content Cache     |
+--------------------+             +---------------------+
```

---

## 3. Project Structure

```text
coursera/
├── main.py                     # Primary entry point
├── cli.py                      # Argument parser & command dispatch
├── config.py                   # Pydantic configuration schemas & loader
├── config.yaml                 # Agent configuration
├── .env.example                # Environment variable template
├── requirements.txt            # Python dependencies
├── README.md                   # Complete system documentation
├── pytest.ini                  # Test suite runner configuration
│
├── browser/
│   ├── __init__.py
│   ├── manager.py              # Persistent Chromium context manager
│   ├── session.py              # Authentication state detection & login prompt
│   └── recovery.py             # Page crash recovery & navigation reloads
│
├── coursera/
│   ├── __init__.py
│   ├── course.py               # Course title, slug, and metadata discovery
│   ├── modules.py              # Module / week accordion scanner
│   ├── lessons.py              # Lesson classification & state tracking
│   ├── navigation.py           # Single-Page App (SPA) navigation & completion controls
│   ├── detectors.py            # Video, reading, practice, and graded detectors
│   └── completion.py           # Course completion & certificate detectors
│
├── assessments/
│   ├── __init__.py
│   ├── models.py               # Question, option, and assessment Pydantic models
│   ├── detector.py             # Graded vs practice classifier
│   ├── extractor.py            # Visible DOM and diagram extractor
│   ├── parser.py               # Text sanitizer and question type inferrer
│   ├── analyzer.py             # Orchestrator querying AI Router
│   └── session.py              # Interactive human review screen & barrier
│
├── ai/
│   ├── __init__.py
│   ├── base.py                 # AIProvider abstract base class
│   ├── router.py               # Primary, fallback, and verification router
│   ├── gemini.py               # Modern google-genai SDK client (types, vision)
│   ├── local_llm.py            # LM Studio / OpenAI-compatible client
│   ├── verifier.py             # Dual-model opinion comparator & confidence scoring
│   ├── prompts.py              # Structured educational prompts
│   ├── schemas.py              # Pydantic structured output models
│   └── cache.py                # SHA-256 content-hash caching in SQLite
│
├── automation/
│   ├── __init__.py
│   ├── state_machine.py        # Lifecycle state machine (START -> DONE)
│   ├── scheduler.py            # Natural human pacing and reading delay simulator
│   └── engine.py               # Main automation loop
│
├── database/
│   ├── __init__.py
│   ├── database.py             # Async SQLAlchemy + aiosqlite engine
│   ├── models.py               # ORM tables (courses, lessons, assessments, etc.)
│   ├── repositories.py         # Repository pattern CRUD layer
│   └── migrations.py           # Table initialization
│
├── notifications/
│   ├── __init__.py
│   ├── macos.py                # Native macOS notifications via osascript
│   └── terminal.py             # Rich console banners, progress cards, and alerts
│
├── utils/
│   ├── __init__.py
│   ├── logger.py               # Formatted console & file logger (logs/agent.log)
│   ├── retry.py                # Exponential backoff decorator
│   ├── screenshots.py          # Categorized screenshot manager
│   ├── timing.py               # High-precision execution timer
│   └── health.py               # System diagnostic checker (--doctor)
│
├── tests/
│   ├── test_ai.py              # AI schemas and verifier tests
│   ├── test_router.py          # Fallback and cross-verification tests
│   ├── test_course.py          # Slug and lesson classification tests
│   ├── test_assessment.py      # Assessment parser and type inference tests
│   ├── test_database.py        # SQLite persistence and cache tests
│   └── test_recovery.py        # State machine crash recovery tests
│
├── logs/                       # Saved application logs (agent.log)
├── screenshots/                # Categorized diagnostic screenshots
└── browser_profile/            # Persistent Chromium profile
```

---

## 4. Installation & Prerequisites

### 1. Set Up Virtual Environment

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Install Playwright Chromium

```bash
playwright install chromium
```

---

## 5. Environment & Model Setup

### Google Gemini API Setup
1. Obtain an API key from Google AI Studio.
2. Export the environment variable or add it to `.env`:
   ```bash
   echo 'export GEMINI_API_KEY="your_api_key_here"' >> ~/.zshrc
   source ~/.zshrc
   ```
   Or create `.env`:
   ```env
   GEMINI_API_KEY=your_api_key_here
   ```
3. Test your Gemini setup:
   ```bash
   python main.py --test-gemini
   ```

### LM Studio Setup (Local Offline Fallback)
1. Download and start [LM Studio](https://lmstudio.ai/).
2. Load any instruction-tuned model (e.g. `Qwen 2.5 3B/7B`, `Llama 3.2 3B`, or `Mistral`).
3. Start the local server on `http://127.0.0.1:1234`.
4. Test the local model connection:
   ```bash
   python main.py --test-local
   ```

---

## 6. Configuration (`config.yaml`)

Edit `config.yaml` to customize your course URL, browser settings, or AI providers:

```yaml
course:
  url: "https://www.coursera.org/learn/python"
  name: "Programming for Everybody (Getting Started with Python)"

browser:
  profile_path: "./browser_profile"
  headless: false
  viewport_width: 1440
  viewport_height: 900
  slow_mo: 0

automation:
  auto_resume: true
  retry_count: 5
  retry_delay: 2
  screenshots: true

ai:
  primary_provider: "gemini"

  gemini:
    enabled: true
    api_key_env: "GEMINI_API_KEY"
    model: "gemini-2.5-flash"

  local:
    enabled: true
    base_url: "http://127.0.0.1:1234/v1"
    model: "qwen3.5-4b"

  verification:
    enabled: true
    confidence_threshold: 0.80

notifications:
  enabled: true
  on_start: true
  on_assessment: true
  on_error: true
  on_completion: true
  on_certificate: true

database:
  path: "./database/coursera.db"

logging:
  level: "INFO"
  file: "./logs/agent.log"
```

---

## 7. CLI Commands Reference

| Command | Description |
|---|---|
| `python main.py` | Run automation with course configured in `config.yaml` |
| `python main.py --course "URL"` | Run automation on a specific Coursera course URL |
| `python main.py --resume` | Resume automation from the last recorded state in SQLite |
| `python main.py --status` | Display progress, completed lessons, and latest run in SQLite |
| `python main.py --doctor` | Run comprehensive environment and connectivity diagnostics |
| `python main.py --test-gemini` | Test Google Gemini API connectivity |
| `python main.py --test-local` | Inspect local LM Studio OpenAI-compatible endpoint |
| `python main.py --test-ai` | Test dual AI routing and verification with a sample question |
| `python main.py --discover` | Discover and print course outline tree without navigating |

---

## 8. Assessment Safety Boundary

The system strictly enforces an educational barrier:

1. **Practice / Ungraded Activities**:
   - The agent analyzes the problem and displays suggested explanations and methodology in the console.
2. **Graded Assessments**:
   - Detects the graded assessment and extracts visible question text and options.
   - If canvas, diagrams, or visual questions are present, captures a screenshot and sends it to Gemini Vision.
   - Computes candidate answers with both Gemini and the Local LLM, cross-checking their agreement.
   - Stores the reasoning in SQLite.
   - **Pauses automation** and displays the formatted question card and reasoning in the terminal.
   - Sends a native macOS desktop notification.
   - **Waits for human confirmation**: The user must review the AI reasoning, choose their answers, and submit in the browser. The agent will **never** programmatically select or submit graded answers.

---

## 9. Running the Test Suite

Execute the full asynchronous test suite with pytest:

```bash
pytest tests/ -v
```

All 16 test cases cover:
- Pydantic schema validation & prompt generation
- Dual-model verification & agreement calculations
- Course slug & lesson type classifications
- Assessment parser, question cleaner, and type inference
- SQLite async repositories & SHA-256 caching
- State machine transitions & crash recovery

---

## 10. Known Limitations & Best Practices

- **Manual Initial Login**: On the very first run, you must log into Coursera in the Chromium window. Your session cookies are stored in `./browser_profile/` and will be reused automatically on all subsequent runs.
- **Never Hard-code Passwords**: The agent will never ask for your Coursera password or save credentials in code.
- **Proctoring / Security Checkpoints**: If Coursera prompts with a CAPTCHA or identity verification screen, complete it manually in the browser window; the agent will detect page stability and resume once cleared.
