#!/usr/bin/env python3
"""Generate a Conventional Commit message from staged changes using LiteLLM."""

import argparse
import subprocess
import sys

try:
    import litellm
except ImportError:
    litellm = None


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
        "Given the following staged diff, draft a concise commit message.\n"
        "Rules:\n"
        "- Subject line must be under 50 characters.\n"
        "- Body lines must be wrapped at 72 characters.\n"
        "- Include a brief explanation of why the change was made.\n"
        "- Format: type(scope): subject\n"
        "- Optional body after a blank line.\n"
        "\n"
        "Staged diff:\n"
        f"{diff}\n"
    )


def generate_message(diff: str, model: str = "gpt-3.5-turbo") -> str:
    """Call LiteLLM to generate the commit message."""
    if litellm is None:
        print("LiteLLM is not installed. Install it with: pip install litellm", file=sys.stderr)
        sys.exit(1)

    prompt = build_prompt(diff)
    response = litellm.completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


def commit(message: str) -> None:
    """Commit using the generated message."""
    subprocess.run(["git", "commit", "-m", message], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a Conventional Commit message from staged changes using LiteLLM."
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Directly commit using the generated message instead of just printing it.",
    )
    parser.add_argument(
        "--model",
        default="gpt-3.5-turbo",
        help="LiteLLM model to use (default: gpt-3.5-turbo).",
    )
    args = parser.parse_args()

    diff = get_staged_diff()
    if not diff.strip():
        print("No staged changes found. Stage your changes first with `git add`.", file=sys.stderr)
        sys.exit(1)

    message = generate_message(diff, model=args.model)
    print(message)

    if args.commit:
        commit(message)


if __name__ == "__main__":
    main()