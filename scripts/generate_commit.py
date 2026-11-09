#!/usr/bin/env python3
"""Generate a Conventional Commit message from staged changes using an LLM."""

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
    """Build the prompt for the LLM."""
    return (
        "You are an expert at writing Conventional Commit messages.\n"
        "Given the following staged diff, draft a commit message that follows the\n"
        "Conventional Commit specification:\n\n"
        "- type(scope): subject\n- subject must be fewer than 50 characters\n- body lines must be fewer than 72 characters\n- briefly explain why the change was made\n- include a footer with an issue reference (e.g. Closes #123)\n\n"
        "Staged diff:\n"
        f"{diff}\n\n"
        "Output only the commit message, nothing else."
    )


def call_llm(prompt: str, model: str) -> str:
    """Call LiteLLM and return the generated commit message."""
    response = litellm.completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


def apply_commit(message: str) -> None:
    """Run `git commit -m <message>`."""
    subprocess.run(["git", "commit", "-m", message], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a Conventional Commit message from staged changes."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Pipe the generated message directly into `git commit -m`.",
    )
    parser.add_argument(
        "--model",
        default="gpt-3.5-turbo",
        help="LiteLLM model name to use (default: gpt-3.5-turbo).",
    )
    args = parser.parse_args()

    diff = get_staged_diff()
    if not diff.strip():
        print("No staged changes found.", file=sys.stderr)
        sys.exit(1)

    prompt = build_prompt(diff)
    message = call_llm(prompt, args.model)

    if args.apply:
        apply_commit(message)
    else:
        print(message)


if __name__ == "__main__":
    main()