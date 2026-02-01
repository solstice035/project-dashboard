# Skills Reference

This document provides a reference copy of the relevant skills for dashboard development work.

**Generated:** 2026-02-01  
**Source:** `/Users/nick/clawd/skills/`

---

## Table of Contents

1. [Brainstorming](#brainstorming)
2. [PRD (Product Requirements Document)](#prd)
3. [TRD (Technical Requirements Document)](#trd)
4. [Test-Driven Development](#test-driven-development)
5. [Project Init](#project-init)
6. [Project Kickoff](#project-kickoff)
7. [Jeeves Kanban](#jeeves-kanban)

---

## Brainstorming

**Use:** Before any creative work - creating features, building components, adding functionality.

### Process

1. **Understanding the idea**
   - Check current project state (files, docs, commits)
   - Ask questions one at a time
   - Prefer multiple choice questions
   - Focus on: purpose, constraints, success criteria

2. **Exploring approaches**
   - Propose 2-3 approaches with trade-offs
   - Lead with recommended option and reasoning

3. **Presenting the design**
   - Break into 200-300 word sections
   - Validate each section before continuing
   - Cover: architecture, components, data flow, error handling, testing

### After Design

- Write to `docs/plans/YYYY-MM-DD-<topic>-design.md`
- Commit to git
- Proceed to implementation if ready

### Key Principles

- **One question at a time**
- **Multiple choice preferred**
- **YAGNI ruthlessly**
- **Explore 2-3 alternatives**
- **Incremental validation**

---

## PRD

**Use:** After brainstorming to formalize requirements. Defines WHAT and WHY.

### Workflow Position

```
brainstorming → PRD → TRD → writing-plans → test-driven-development
```

### Complexity Levels

**Simple** (< 1 day, familiar problem):
- Problem Statement
- User Stories (MVP)
- Scope

**Complex** (multiple user types, > 1 day):
- Full user journeys
- Detailed acceptance criteria
- All sections

### Auto-escalate to Complex if:
- External API integrations
- New data models
- Auth changes
- Payment/PII handling
- Multiple user types

### Output

Save to: `docs/plans/YYYY-MM-DD-<feature>-prd.md`

### Sections

1. **Problem Statement** - What, why, cost of inaction
2. **User Definition** - Who, context, current workaround
3. **User Journeys** - Entry → Actions → Decisions → Exit
4. **User Stories** - As a [user], I want [goal], so that [benefit]
5. **Success Metrics** - Functional, qualitative, measurable
6. **Scope** - In scope (MVP), out of scope (v2), assumptions, dependencies

### Key Principles

- **One section at a time** - Validate incrementally
- **Business language only** - No tech jargon
- **User-centric** - Everything from user perspective
- **Explicit scope** - What's OUT matters as much as IN
- **Defer v2** - Ruthless about MVP

---

## TRD

**Use:** After PRD to define HOW to build it.

### Workflow Position

```
PRD → TRD → [Complex? consensus] → writing-plans
```

### Complexity Levels

**Simple** (single component, < 1 day):
- Architecture Overview
- Technology Choices
- Key Decisions
- Risks

**Complex** (multiple components, > 1 day):
- All simple sections PLUS:
- Data Model
- API Design
- Component Interactions
- Integration Points
- Testing Strategy
- Deployment
- Observability
- Environment Config

### Output

Save to: `docs/plans/YYYY-MM-DD-<feature>-trd.md`

### Key Sections

1. **Architecture Overview** - 2-3 paragraphs, optional ASCII diagram
2. **Technology Choices** - Table: Component | Choice | Rationale
3. **Key Decisions** - Decision, rationale, alternatives rejected
4. **Data Model** - Entities, relationships, storage approach
5. **API Design** - Interfaces, operations, error cases
6. **Risks** - Risk, impact, likelihood, mitigation

### Key Principles

- **Adaptive depth** - Don't over-document simple projects
- **PRD traceability** - Every decision traces to a requirement
- **Decision rationale** - Future-you needs WHY, not just WHAT
- **Diagrams over prose** - ASCII pictures beat paragraphs

---

## Test-Driven Development

**Use:** When implementing any feature or bugfix.

### The Iron Law

```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

Write code before test? **Delete it. Start over.**

### Red-Green-Refactor

1. **RED** - Write failing test (one behavior, clear name)
2. **Verify RED** - Watch it fail for the right reason
3. **GREEN** - Write minimal code to pass
4. **Verify GREEN** - All tests pass
5. **REFACTOR** - Clean up while staying green
6. **Repeat**

### Good Tests

| Quality | Good | Bad |
|---------|------|-----|
| Minimal | One thing per test | Multiple behaviors |
| Clear | Name describes behavior | `test1`, `test works` |
| Real | Test actual code | Test mocks |

### Common Rationalizations (All Wrong)

- "Too simple to test" → Simple code breaks. Test takes 30 seconds.
- "I'll test after" → Tests passing immediately prove nothing.
- "TDD slows me down" → TDD is faster than debugging.
- "Keep as reference" → Delete means delete.

### Red Flags - STOP and Start Over

- Code before test
- Test passes immediately
- Can't explain why test failed
- "Just this once"

### Verification Checklist

- [ ] Every function has a test
- [ ] Watched each test fail before implementing
- [ ] Each test failed for expected reason
- [ ] Wrote minimal code to pass
- [ ] All tests pass
- [ ] Output pristine (no warnings)
- [ ] Edge cases covered

---

## Project Init

**Use:** Starting work on a project that lacks a CLAUDE.md.

### Process

1. **Auto-Detection** - Scan for package.json, pyproject.toml, etc.
2. **Extract** - Commands, dependencies, structure, env vars
3. **Fill Gaps** - Ask about purpose, patterns, do's/don'ts
4. **Generate** - Create CLAUDE.md

### Detection Files

| File | Indicates |
|------|-----------|
| `package.json` | Node.js |
| `pyproject.toml` | Python |
| `Cargo.toml` | Rust |
| `tsconfig.json` | TypeScript |
| `docker-compose.yml` | Docker |

### CLAUDE.md Sections

- Overview
- Tech Stack
- Getting Started
- Commands
- Architecture
- Environment Variables
- Key Patterns
- Notes for Claude (Do/Don't)

---

## Project Kickoff

**Use:** Starting a new development project or automation.

### Workflow

1. **Gather Requirements** - Name, description, type, goal
2. **Create Structure** - `src/`, `tests/`, `docs/`, README
3. **Generate README** - Purpose, status, quick start
4. **Initialize Git** - Init, add, initial commit
5. **Add to Kanban** - Create task in backlog
6. **Create Obsidian Note** - Project documentation

### Templates

- **Python**: requirements.txt, pyproject.toml, src/__init__.py
- **Node**: package.json, .nvmrc, src/index.js
- **Skill**: SKILL.md, skill structure
- **Automation**: Script in /scripts/

### Post-Kickoff Checklist

- [ ] Initial commit made
- [ ] Kanban task created
- [ ] Obsidian note created
- [ ] README complete
- [ ] First milestone defined

---

## Jeeves Kanban

**Use:** Managing Jeeves-specific tasks (not personal tasks - those go to Todoist).

### API Reference

Base URL: `http://localhost:8889/api`

**List Tasks:**
```bash
curl -s http://localhost:8889/api/kanban/tasks
```

**Add Task:**
```bash
curl -s -X POST http://localhost:8889/api/kanban/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "Task", "column": "backlog", "priority": 2}'
```

**Update/Move Task:**
```bash
curl -s -X PUT http://localhost:8889/api/kanban/tasks/ID \
  -H "Content-Type: application/json" \
  -d '{"column": "in-progress"}'
```

**Delete Task:**
```bash
curl -s -X DELETE http://localhost:8889/api/kanban/tasks/ID
```

### Columns

1. **📥 Backlog** - Ideas and future
2. **✅ Ready** - Ready to start
3. **🚀 In Progress** - Currently working
4. **👀 Review** - Awaiting review
5. **🎉 Done** - Completed

### Priority

- 1 = Low
- 2 = Normal
- 3 = High
- 4 = Urgent

### Web UI

- URL: http://localhost:8889
- Tab: "Kanban"
- Features: Drag-and-drop, add/edit/delete

---

## Complete Development Workflow

```
1. Idea
      ↓
2. brainstorming     → Explore and design
      ↓
3. prd               → Define WHAT/WHY
      ↓
4. trd               → Define HOW
      ↓
5. writing-plans     → Break into tasks
      ↓
6. test-driven-dev   → Implement with TDD
      ↓
7. Ship it! 🚀
```

---

*This document is a reference copy. For the authoritative versions, see the skill files in `/Users/nick/clawd/skills/`.*
