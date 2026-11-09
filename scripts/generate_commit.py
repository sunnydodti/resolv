#!/usr/bin/env python3
"""Generate a Conventional Commit message from staged changes using LiteLLM."""

import argparse
import subprocess
import sys

import litellm


def get_staged_diff() -> str:
    """Return the output of `git diff --cached`."""
    result = subprocess.run(
        ["git", "diff", "--cached"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def build_prompt(diff: str) -> str:
    """Build the prompt asking the LLM to draft a Conventional Commit."""
    return f"""You are an expert at writing Conventional Commit messages.

Given the following staged diff, draft a commit message that follows the Conventional Commits specification:

- Type: feat, fix, docs, style, refactor, perf, test, chore, ci, build, revert
- Subject line: imperative mood, less than 50 characters, no trailing period
- Body: wrap lines at 72 characters, briefly explain the "why"
- Footer: include an issue reference if applicable (e.g., "Closes #123")

Staged diff:
{diff}

Output only the commit message, nothing else."""


def generate_commit_message(prompt: str, model: str) -> str:
    """Call LiteLLM to generate the commit message."""
    response = litellm.completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


def commit_with_message(message: str) -> None:
    """Pipe the generated message directly into `git commit -m`."""
    subprocess.run(["git", "commit", "-m", message], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a Conventional Commit message from staged changes."
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Commit directly using the generated message.",
    )
    parser.add_argument(
        "--model",
        default="gpt-3.5-turbo",
        help="LiteLLM model to use (default: gpt-3.5-turbo).",
    )
    args = parser.parse_args()

    diff = get_staged_diff()
    if not diff.strip():
        print("No staged changes found.", file=sys.stderr)
        sys.exit(1)

    prompt = build_prompt(diff)
    message = generate_commit_message(prompt, args.model)

    print(message)

    if args.commit:
        commit_with_message(message)


if __name__ == "__main__":
    main()