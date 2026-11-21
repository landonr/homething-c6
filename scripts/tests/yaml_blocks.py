"""Text helpers that cut an ESPHome config into its top-level blocks."""

import re


def top_level_block(text: str, key: str) -> str:
    """Returns the lines under one top-level key, up to the next top-level key.

    A top-level comment does not end the block, so a comment in front of the
    next key stays with the block above it.
    """
    lines = text.splitlines()
    try:
        start = lines.index(f"{key}:")
    except ValueError:
        raise AssertionError(f"no top-level {key}: block") from None
    body = []
    for line in lines[start + 1:]:
        if line and not line[0].isspace() and not line.startswith("#"):
            break
        body.append(line)
    return "\n".join(body) + "\n"


def without_comments(block: str) -> str:
    return "\n".join(line for line in block.splitlines() if not line.lstrip().startswith("#")) + "\n"


def list_entries(block: str) -> list[str]:
    """Splits a top-level list block into its entries."""
    entries = re.split(r"(?m)^  - ", without_comments(block))[1:]
    if not entries:
        raise AssertionError("the block has no list entries")
    return ["  - " + entry for entry in entries]
