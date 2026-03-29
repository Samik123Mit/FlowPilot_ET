# FlowPilot Demo Script

## Prerequisites
- FlowPilot server running (`uvicorn main:app --reload`)
- Browser open to dashboard at `http://localhost:8000`

---

## Demo Flow (3 minutes)

### Step 1: Upload Meeting Transcript (0:00-0:30)
1. Open the FlowPilot dashboard
2. Click "Process New Meeting"
3. Paste the Sprint Planning transcript (from `data/sample_meetings/sprint_planning.json`)
4. Click "Run Pipeline"

**Narration:** "We're feeding in a real engineering sprint planning meeting with 5 participants, overlapping responsibilities, and some vague action items."

### Step 2: Watch Agent Pipeline Process (0:30-1:00)
1. Agent Activity Log shows each agent activating in sequence
2. Transcription Agent: parses 8 segments, identifies 5 speakers, scores quality at 92%
3. Decision Extractor: finds 4 decisions, 5 action items, flags 3 ambiguities
4. **KEY MOMENT:** "Notice the yellow correction badge -- the agent detected 'someone should look into the auth module' has no clear owner. It cross-referenced the org chart and auto-assigned it to David Kim based on his security skills."

### Step 3: Task Board Populates (1:00-1:30)
1. Switch to the Kanban board view
2. Show 5 tasks auto-created with priorities, deadlines, and assignees
3. **KEY MOMENT:** "See this correction -- Maria Lopez was at 120% capacity. The orchestrator automatically reassigned 'Schedule John-Maria sync' to Tom Wilson who had available bandwidth."
4. Show the dependency chain visualization

### Step 4: Self-Correction Showcase (1:30-2:00)
1. Click on the Self-Corrections panel
2. Show 3-4 correction events with before/after states
3. "Every self-correction is logged with full context -- what was wrong, what the agent did, and why."

### Step 5: Audit Trail Deep-Dive (2:00-2:30)
1. Click on any task in the Kanban board
2. Show the audit trail: meeting transcript sentence -> decision -> action item -> task
3. "Click any task and trace it all the way back to the exact moment in the meeting where it was decided. Full lineage, fully auditable."

### Step 6: Analytics Dashboard (2:30-2:50)
1. Show meeting effectiveness score (82%)
2. Show action item completion predictions
3. Show team workload heatmap
4. Show risk factors flagged by the audit agent

### Step 7: Close (2:50-3:00)
"FlowPilot doesn't just take notes. It takes ownership. Five specialized agents, self-correcting at every stage, with a complete audit trail. Team: The Innovators, IIT Guwahati."

---

## Backup: API Demo (if dashboard has issues)

```bash
curl -X POST http://localhost:8000/api/v1/meetings/process \
  -H "Content-Type: application/json" \
  -d @data/sample_meetings/sprint_planning.json
```

Show the JSON response with decisions, tasks, corrections, and audit trail.
