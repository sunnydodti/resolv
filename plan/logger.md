# ResolvLogger Specification

## 1. Architectural Requirement
All CLI outputs (status, transitions, debug traces, warnings, errors, hints, prompts) MUST pass through a centralized logger facade (`ResolvLogger`). **Direct `print()` statements or unmediated `stdout`/`stderr` writes are strictly prohibited.**

## 2. Log Tag & Color Palette
All output must be tagged and color-coded using ANSI TrueColor (#RRGGBB).

| Tag | Level | Color (Hex) | Description |
| :--- | :--- | :--- | :--- |
| **[I]** | Info | #8A9BB8 | Pipeline milestones, stage starts, progress. |
| **[S]** | Success | #8FBC8F | Stage completions, passed checks, success. |
| **[W]** | Warning | #DEC686 | Skips, fuzzy matches, self-healing triggers. |
| **[E]** | Error | #D48E8E | Failures, test crashes, syntax errors. |
| **[D]** | Debug | #A498C0 | Tool payloads, AST traces (only if `--verbose`). |
| **[H]** | Hint | #87B8D4 | Contextual advice, human-in-the-loop tips. |
| **[?]** | Input | #D2D7DC | Interactive prompts and confirmations. |

## 3. Formatting Rules
*   **Facade Pattern:** A unified logger instance mediates all outputs.
*   **Fallback:** ANSI TrueColor rendering with graceful 256-color pale palette fallbacks for non-TrueColor terminals.
*   **Debug Trace Suppression:** `[D]` tagged output is silenced by default; enabled only with `--verbose`.
*   **Dual Stream Persistence:** 
    *   **Stdout:** ANSI-rendered output for the terminal.
    *   **File:** Synchronous, plain-text (ANSI-stripped) log written to `.resolv/sessions/<project>/<issue_id>/audit.log`.

## 4. Implementation Guidelines
*   **Interactive Prompts:** Display options vertically with clear indexing and explicit defaults (e.g., `[Y/n] (default: Y)`).
*   **Thread Safety:** The logger must be thread-safe for potential concurrent agent execution.
*   **Sanitization:** Ensure the logger handles sensitive data masking (API keys, secrets) before writing to `audit.log`.
