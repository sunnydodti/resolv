# Resolv: CLI Agent Redesign Documentation

Welcome to the official design and development repository for **Resolv**, a Python-based autonomous, single-entry issue-to-PR CLI agent. 

## What is Resolv?
Resolv is an intelligent assistant designed to streamline developer workflows. It ingests issues, analyzes codebases, plans architectural changes, applies edits, tests them in sandboxed environments, and generates pull requests—all within a controlled, observable pipeline.

## Architecture Highlights
- **Deterministic-First:** Relies on pure Python/Git tools for 100% predictable operations.
- **AI-Orchestrated:** Uses LangGraph and LiteLLM for smart decision-making and routing.
- **Strict Observability:** Integrated with Langfuse for full execution tracing.
- **Safe & Resumable:** Checkpoints every state to local disk for auditability and recovery.

---

## Navigation Guide
- **[High-Level Design (HLD)](plan/plan.md):** The core architectural strategy.
- **[Master Roadmap](specs/master_roadmap.md):** The end-to-end 30-step development plan.
- **[Logging Specification](plan/logger.md):** Standards for CLI output and telemetry.
- **[Detailed Steps](specs/steps/):** Granular implementation tasks for each phase of the project.

---

## Getting Started
To begin development, start with the **[Master Roadmap](specs/master_roadmap.md)**. Each step is documented in the `specs/steps/` directory.

> **Note:** This project is currently in the redesign phase. Git interactions in this repo are `READONLY` unless explicitly approved.
