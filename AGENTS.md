# Resolv Agent Instructions

## Environment Policy
- **Virtual Environment:** All dependencies must be managed within a local `.venv` directory in the repository root.
- **Dependency Management:** Use `poetry` with `virtualenvs.in-project = true`.
- **Global Isolation:** Do not install any dependencies into the global Python environment.
- **Git interaction:** READONLY ONLY. Never commit, push, or modify git history without explicit user approval.
- **All changes must be confirmed by user before being written to the repository.**
- **If git status shows modifications, report to user instead of auto-committing.**
- **Only build/test/execute; do not persist changes to .git without explicit written approval.**
