# Agents Guide

## For AI Agents (GitHub Copilot, Claude, etc.)

Before making any changes to this repository, **you must read and follow** the instructions in
[`.github/copilot-instructions.md`](.github/copilot-instructions.md).

That file contains the canonical coding standards, formatting rules, and documentation requirements
for this project. All code contributions — whether from humans or AI agents — must conform to those
guidelines.

## Task-specific instructions

When the user requests a specific task, read and follow the matching instruction file **before**
starting work:

| Task type | Instruction file | Trigger phrases |
|-----------|-----------------|-----------------|
| Create a subjective test / study | [`.github/create.instruction.md`](.github/create.instruction.md) | "create a study", "run a [method] test", "set up a study", "prepare a test" |
| Analyze test results | `.github/evaluate.instruction.md` *(tba)* | "analyze results", "parse results", "evaluate the study" |

These instruction files are self-contained runbooks. Follow them step by step.
