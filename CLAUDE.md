# Claude Code Instructions

Before making any changes to this repository, read and follow the coding standards in
[`.github/copilot-instructions.md`](.github/copilot-instructions.md).

## Custom Agents

This repository defines reusable agent runbooks in `.github/agents/`.
When a user asks to create a study, run a test, or set up a subjective quality experiment,
follow the instructions in the relevant agent file.

| Agent | File | Trigger phrases |
|-------|------|-----------------|
| `create-study` | [`.github/agents/create-study.agent.md`](.github/agents/create-study.agent.md) | "create a study", "run a [method] test", "set up a study", "prepare a test" |

When triggered, read the full agent file and execute its workflow step by step.
