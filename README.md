<div align="center">

# FlowPilot

### From Meetings to Momentum

**AI-Powered Autonomous Meeting-to-Action Intelligence System**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Agents](https://img.shields.io/badge/AI_Agents-5-orange)](docs/architecture.md)

*Every week, enterprises hold 62 million meetings. 71% are unproductive -- not because the discussions are bad, but because decisions vanish the moment the meeting ends.*

**FlowPilot fixes this.**

</div>

---

## What It Does

FlowPilot is a **multi-agent AI system** that processes meeting transcripts and autonomously converts them into tracked, accountable action items -- with self-correction at every stage and a complete audit trail.

**5 Specialized Agents. Full Autonomy. Zero Lost Action Items.**

| Agent | Role | Self-Correction |
|-------|------|-----------------|
| Transcription Agent | Parses meetings into structured segments with speaker ID | Re-processes low-confidence segments; falls back to rule-based parsing |
| Decision Extractor | Extracts decisions, actions, deadlines, owners | Resolves missing owners via org chart; fixes vague deadlines |
| Task Orchestrator | Creates tasks, balances workloads, checks dependencies | Redistributes overloaded assignees; breaks circular dependencies |
| Follow-Up Agent | Sends reminders, detects stalls, escalates | Escalates missed deadlines to managers; proposes new timelines |
| Audit Agent | Maintains decision trail, generates analytics | Persists full audit; computes meeting effectiveness scores |

---

## Quick Start

### Option 1: Local Setup (3 commands)
```bash
git clone https://github.com/your-team/flowpilot.git && cd flowpilot
pip install -r requirements.txt
uvicorn main:app --reload
```

### Option 2: Docker (1 command)
```bash
docker-compose up --build
```

**No API key required!** FlowPilot runs in mock mode with realistic demo data by default. Add your OpenAI or Gemini key in `.env` for live LLM processing.

Visit: `http://localhost:8000/docs` for the interactive API docs.

---

## Process a Meeting

```bash
curl -X POST http://localhost:8000/api/v1/meetings/process \
  -H "Content-Type: application/json" \
  -d @data/sample_meetings/sprint_planning.json
```

**Response includes:**
- Structured transcript with speaker tags
- Extracted decisions and action items
- Auto-created tasks with assignments
- Self-correction events (owner resolution, workload rebalancing)
- Full audit trail tracing every task back to its source sentence
- Meeting effectiveness analytics

---

## Architecture

```
Meeting Input --> [Transcription] --> [Decision Extraction] --> [Task Orchestration]
                        |                     |                        |
                   Self-correct:         Self-correct:           Self-correct:
                   low-quality           missing owners          overloaded assignees
                   re-processing         org chart lookup        task redistribution
                        |                     |                        |
                        v                     v                        v
                  [Follow-Up & Compliance] --> [Audit & Analytics]
                        |                           |
                   Self-correct:              Persist to DB
                   missed deadlines           Generate report
                   auto-escalation            Effectiveness score
```

Each agent operates with **built-in error recovery**: Retry (3x with backoff) -> Fallback (rule-based) -> Skip (non-critical) -> Escalate (human-in-the-loop).

See [full architecture documentation](docs/architecture.md) for detailed agent specs.

---

## Sample Meetings Included

| Meeting | Scenario | Key Test |
|---------|----------|----------|
| Sprint Planning | Clear action items, deadlines, blockers | Happy path + workload conflict |
| Product Review | Ambiguous ownership, conflicting priorities | Owner resolution, priority ranking |
| Strategy Meeting | High-level decisions needing task breakdown | Decision decomposition |
| Retro (Failed Follow-up) | Previous sprint's actions not completed | Escalation, re-prioritization |

---

## Impact Model

For a 500-person enterprise:

| Metric | Value |
|--------|-------|
| Hours saved annually | 84,000+ |
| Annual cost savings | $5.93M |
| Meeting ROI improvement | 3x |
| Follow-through rate | 30% --> 85% |
| Payback period | 7.4 days |
| Audit compliance | 100% |

See [detailed impact analysis](docs/impact_model.md).

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.11 + FastAPI |
| LLM | GPT-4o-mini / Gemini 2.0 Flash (auto-fallback) |
| Database | SQLite (zero-config) |
| Real-time | WebSockets |
| Frontend | React + Tailwind CSS |
| Containerization | Docker |

---

## Run Tests

```bash
cd flowpilot
python -m tests.test_pipeline
```

---

## Project Structure

```
flowpilot/
|-- main.py                          # FastAPI entry point
|-- src/
|   |-- agents/                      # 5 specialized AI agents
|   |   |-- transcription_agent.py
|   |   |-- decision_extractor.py
|   |   |-- task_orchestrator.py
|   |   |-- followup_agent.py
|   |   |-- audit_agent.py
|   |-- orchestrator/                # Pipeline coordination
|   |   |-- pipeline.py
|   |   |-- state_machine.py
|   |   |-- error_handler.py
|   |-- models/                      # Data models & database
|   |-- api/                         # REST + WebSocket endpoints
|   |-- utils/                       # LLM wrapper, notifications
|-- tests/                           # Test suite
|-- data/sample_meetings/            # 4 realistic sample transcripts
|-- docs/                            # Architecture + Impact docs
|-- demo/                            # Demo walkthrough script
```

---

## Team

**The Innovators** | IIT Guwahati

- **Samiksha Mitra** -- Pre-final year B.Tech, IIT Guwahati. Overall Coordinator of 4i Labs. Multi-agent systems, FastAPI, quantitative research.
- **Rupangkan Mazumdar** -- IIT Guwahati. Frontend, prototyping, presentations. Co-built WeGovern (Phase 1 winner).

---

## License

MIT License. Built for the ET AI Hackathon 2026 Phase 2.
