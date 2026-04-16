# Deep Agents Blackboard Demo Design

Date: 2026-04-17

## Goal

This project is a study-oriented Deep Agents demo centered on the blackboard pattern.

The goal is not to reimplement a custom blackboard runtime. The goal is to show how the blackboard pattern can be expressed with Deep Agents-native capabilities:

- planning
- shared filesystem state
- subagents
- skills
- MCP
- memory
- permissions
- human-in-the-loop
- streaming

The demo should make agent behavior highly visible, even if that introduces some redundancy.

## Core Principles

1. Canonical execution data lives in structured outputs.
2. Blackboard Markdown files are always written for human observability.
3. The blackboard is a shared working surface, not the system of record.
4. Subagents collaborate through the blackboard.
5. The orchestrator supervises consistency, memory promotion, and streaming.
6. Learning value and traceability are prioritized over minimalism.

## Architecture

### Agents

- `Orchestrator`
- `Planner`
- `Critic`
- `Synthesizer`

### Responsibilities

#### Orchestrator

- interpret the user request
- manage progress with `write_todos`
- initialize and maintain blackboard state
- decide when to call subagents
- collect detailed structured outputs from subagents
- update summary and governance files on the blackboard
- decide which knowledge should be proposed for memory promotion
- perform actual writes to `/memories/`
- trigger human approval on memory writes
- stream intermediate and final results through SSE

#### Planner

- read the goal and current blackboard state
- produce a concrete execution plan
- update `plan.md`
- optionally use skills and MCP
- return detailed structured output including trace entries, MCP usage notes, and memory proposals

#### Critic

- read the goal and plan
- identify risks, gaps, and failure modes
- update `critique.md`
- optionally use skills and MCP
- return detailed structured output including trace entries, MCP usage notes, and memory proposals

#### Synthesizer

- read the plan and critique
- reconcile competing considerations
- produce the final strategy
- update `synthesis.md`
- optionally use skills and MCP
- return detailed structured output including trace entries, decision candidates, and memory proposals

## Blackboard Model

The blackboard is represented as a human-readable projection under `/workspace/blackboard/`.

Canonical state is still carried through structured outputs and agent runtime state, but the blackboard is always updated so users can inspect what happened.

### Blackboard Files

- `goal.md`
- `plan.md`
- `critique.md`
- `synthesis.md`
- `trace.md`
- `memory-proposals.md`
- `mcp-log.md`
- `state-summary.md`
- `decisions.md`
- `open-questions.md`

### File Ownership

#### Primary ownership

- `Orchestrator`: `goal.md`, `state-summary.md`, `decisions.md`
- `Planner`: `plan.md`
- `Critic`: `critique.md`
- `Synthesizer`: `synthesis.md`

#### Shared auxiliary updates

- `Planner`: may append to `trace.md`, `mcp-log.md`, `open-questions.md`, `memory-proposals.md`
- `Critic`: may append to `trace.md`, `mcp-log.md`, `open-questions.md`, `memory-proposals.md`
- `Synthesizer`: may append to `trace.md`, `mcp-log.md`, `decisions.md`, `memory-proposals.md`

In practice, subagents return structured entries and the orchestrator materializes them into Markdown so formatting stays consistent.

### Update Policy

- first creation uses write
- subsequent changes prefer edit
- `trace.md` and `mcp-log.md` are append-oriented
- `state-summary.md` is rewritten to reflect the latest state
- `decisions.md` and `open-questions.md` are updated incrementally and may be reorganized

## Data Flow

1. User sends a request to `FastAPI /chat`.
2. `Orchestrator` creates the initial goal representation and blackboard files.
3. `Orchestrator` manages progress with `write_todos`.
4. `Planner` reads blackboard state and updates `plan.md`.
5. `Critic` reads blackboard state and updates `critique.md`.
6. `Synthesizer` reads blackboard state and updates `synthesis.md`.
7. Each subagent returns detailed structured output to the orchestrator.
8. `Orchestrator` updates `trace.md`, `state-summary.md`, `decisions.md`, and `memory-proposals.md`.
9. If memory promotion is appropriate, `Orchestrator` performs the actual `/memories/` write with HITL.
10. SSE exposes the intermediate and final flow to the user.

## Structured Output Strategy

Structured outputs remain the canonical form for machine coordination.

Each subagent should return, at minimum:

- role-specific result payload
- blackboard update summary
- trace entries
- MCP usage records
- memory proposals
- open questions
- decision suggestions when relevant

This creates intentional redundancy:

- structured outputs support runtime consistency
- blackboard files support learning and observability

## Trace Design

`trace.md` is a hybrid of event log and reasoning log.

Each trace entry should aim to include:

- actor
- action
- target
- reason
- result
- next

Subagents do not directly own trace formatting. They return trace-ready entries, and the orchestrator writes them into `trace.md`.

## Skills Design

The demo uses both common and role-specific skills.

### Common skill

Contains project-wide guidance for:

- blackboard usage
- MCP logging rules
- memory proposal rules
- trace writing conventions
- observability expectations

### Role-specific skills

- `Planner` skill: decomposition, sequencing, dependency awareness
- `Critic` skill: risk review, contradiction search, failure analysis
- `Synthesizer` skill: convergence, tradeoff resolution, final recommendation shaping

## MCP Design

All agents may use MCP tools.

Rule:

- every MCP use must record why it was used
- every MCP use must summarize what was obtained
- both details must be reflected in structured output and `mcp-log.md`

This keeps the system flexible without losing visibility into external dependencies.

## Memory Design

Memory is enabled from the first version of the demo.

### Memory rules

- all agents may read memory
- all agents may propose memory promotion
- only the orchestrator performs actual writes to `/memories/`
- memory writes are subject to HITL

This is a proposal-first model:

- subagents suggest what should persist
- the orchestrator decides what to promote
- humans can approve or block long-term writes

### Blackboard vs Memory

- blackboard: current thinking and transient collaboration state
- memory: reusable knowledge worth carrying across runs

## Permissions and Safety

The first version uses relatively permissive filesystem permissions for learning value.

Initial bias:

- `/workspace/**`: read and write
- `/memories/**`: read and write

Operational discipline still matters:

- blackboard ownership rules should be followed
- memory writes should remain orchestrator-led
- HITL should only gate memory writes in v1

Future iterations may tighten permissions by agent or path.

## Streaming Design

SSE should expose:

- orchestrator progress
- subagent invocation boundaries
- blackboard update events
- HITL pauses for memory writes
- final response output

The streaming experience is part of the learning goal, not just transport.

## Implementation Plan

### Phase 1

- create orchestrator
- create FastAPI SSE endpoint
- initialize blackboard directory and minimal files

### Phase 2

- add `Planner`, `Critic`, and `Synthesizer`
- add blackboard file update routines
- add detailed structured outputs

### Phase 3

- add `trace.md`, `state-summary.md`, `decisions.md`, `open-questions.md`
- verify subagent collaboration through blackboard files

### Phase 4

- add `/memories/` backend routing
- add memory proposal handling
- add HITL for memory writes

### Phase 5

- add common and role-specific skills
- add MCP integration and `mcp-log.md`

## Main Risks

### Redundancy drift

Structured outputs and Markdown files may diverge.

Mitigation:

- treat structured outputs as canonical
- let the orchestrator render blackboard projections

### Blackboard sprawl

Too many files may become noisy.

Mitigation:

- keep ownership explicit
- keep `state-summary.md` current
- revisit file count after the first implementation

### Feature overload

Adding MCP, memory, HITL, skills, and multiple subagents at once could blur what is essential.

Mitigation:

- build in phases
- validate the blackboard loop before layering more capabilities

## Success Criteria

The design succeeds if:

- the blackboard pattern is clearly visible in the running system
- Deep Agents-native capabilities remain the foundation
- users can inspect agent reasoning and coordination in detail
- memory promotion is observable and gated
- MCP usage is visible and attributable
- the repo functions as a coherent study demo, not a pile of unrelated examples
