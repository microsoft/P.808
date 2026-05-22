# Agents Guide

## For AI Agents (GitHub Copilot, Claude, etc.)

Before making any changes to this repository, **you must read and follow** the instructions in
[`.github/copilot-instructions.md`](.github/copilot-instructions.md).

That file contains the canonical coding standards, formatting rules, and documentation requirements
for this project. All code contributions — whether from humans or AI agents — must conform to those
guidelines.

## Custom agents

This repository defines custom agents in `.github/agents/`. Use `/agent` in Copilot CLI
to browse and select them, or reference them by name in a prompt.

| Agent | File | Trigger phrases |
|-------|------|-----------------|
| `create-study` | [`.github/agents/create-study.agent.md`](.github/agents/create-study.agent.md) | "create a study", "run a [method] test", "set up a study", "prepare a test" |
| `analyze-results` | [`.github/agents/analyze-results.agent.md`](.github/agents/analyze-results.agent.md) | "analyze results", "parse results", "evaluate the study", "process the answers" |

## Task-specific instructions (future)

| Task type | Instruction file | Trigger phrases |
|-----------|-----------------|-----------------|
| *(reserved)* | — | — |
