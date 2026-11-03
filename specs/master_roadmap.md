# Resolv Development Master Roadmap

This document outlines the end-to-end technical implementation plan for the Resolv CLI agent, broken down into granular technical steps.

## Phase 1: Foundation & Infrastructure
- **Step 001: Project Foundation & CLI Scaffolding** (Environment, .gitignore, Click setup)
- **Step 002: Core Logging Facade** (ResolvLogger, ANSI colors, dual-stream persistence)
- **Step 003: Configuration Schema & Loader** (Pydantic models for YAMLs, Env manager)
- **Step 004: Workspace Manager** (Init logic for `.resolv/` session storage)

## Phase 2: Agent Core & State Machine
- **Step 005: Base Agent Abstract Class** (Unified interface for LLM/Deterministic sub-agents)
- **Step 006: LiteLLM Gateway Integration** (Unified provider routing & fallback logic)
- **Step 007: State Management (LangGraph)** (Core state model `ContextState`)
- **Step 008: Checkpointing/Persistence** (Disk-based recovery & metadata serialization)

## Phase 3: Deterministic Tooling (The "Deterministic Execution" Layer)
- **Step 009: LocalGitSubAgent** (Session branch & worktree management)
- **Step 10: RemoteGitSubAgent** (Auth, repo path resolution)
- **Step 11: CodeGraphSubAgent** (AST/Grep exploration)
- **Step 12: DatabaseAgent** (Schema introspection)
- **Step 13: SandboxRunnerSubAgent** (Sandboxed command execution)

## Phase 4: AI Logic (The "LLM Driven" Layer)
- **Step 14: ContextAgent Implementation** (Intent extraction & requirements mapping)
- **Step 15: PlannerAgent Implementation** (Token budgetting & Pydantic roadmap generation)
- **Step 16: CodingAgent Implementation** (Structured edit & patch synthesis)
- **Step 17: SecurityAgent Implementation** (Entropy & credential leakage scan)
- **Step 18: ReviewAgent Implementation** (Rule compliance validation)

## Phase 5: Workflow Integration
- **Step 19: Stage 0 (Setup) Pipeline Integration**
- **Step 20: Stage 1 (Analyze) Pipeline Integration**
- **Step 21: Stage 2 (Plan) Pipeline Integration**
- **Step 22: Stage 3 (Apply) Pipeline Integration**
- **Step 23: Stage 4 (Build/Test) Integration** (Self-healing loop logic)
- **Step 24: Stage 5 (Review) Pipeline Integration**
- **Step 25: Stage 6 (Publish) Pipeline Integration** (GitHub PR creation)
- **Step 26: Stage 7 (Record) Pipeline Integration** (Audit logs & Langfuse)

## Phase 6: Finalization & Polish
- **Step 27: Error Handling & Graceful Exit** (Global catch-alls & cleanup)
- **Step 28: Dry-Run Mode Implementation**
- **Step 29: Verbose Logging & Audit Log Sanitization**
- **Step 30: Final POC Verification** (End-to-end simulation of a single issue fix)
