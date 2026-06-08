# Copilot Instructions

## Code Style and Formatting

### Function Documentation

#### Python

Every function **must** include a docstring **inside** the function body, immediately after the
`def` line. Use the following format:

```python
def calculate_mos(ratings, num_subjects):
    """
    Calculate the Mean Opinion Score from a list of ratings.

    :param ratings: List of numeric ratings.
    :param num_subjects: Number of subjects who provided ratings.
    :return: The computed MOS value as a float.
    """
    ...
```

#### JavaScript

Every function **must** have a JSDoc comment **above** the function declaration:

```javascript
/**
 * Calculate the Mean Opinion Score from a list of ratings.
 *
 * @param {number[]} ratings - List of numeric ratings.
 * @param {number} numSubjects - Number of subjects who provided ratings.
 * @returns {number} The computed MOS value.
 */
function calculateMos(ratings, numSubjects) {
    ...
}
```

### Python Spacing and Syntax

Follow [PEP 8](https://peps.python.org/pep-0008/) conventions:

- Use **4 spaces** per indentation level. Do **not** use tabs.
- Surround top-level function and class definitions with **two blank lines**.
- Surround method definitions inside a class with **one blank line**.
- Use **spaces around operators** (`=`, `+=`, `==`, `!=`, `<`, `>`, `in`, `not in`, etc.).
- **No spaces** immediately inside parentheses, brackets, or braces:
  - ✅ `func(a, b)` — ❌ `func( a, b )`
  - ✅ `data[0]` — ❌ `data[ 0 ]`
  - ✅ `{'key': value}` — ❌ `{ 'key' : value }`
- Place **one space after commas** in argument lists, collections, and imports.
- **No trailing whitespace** on any line.
- Keep lines to a maximum of **120 characters**.
- Use **snake_case** for functions and variables, **PascalCase** for classes, and **UPPER_SNAKE_CASE** for constants.
- Imports should be grouped in the following order, separated by a blank line:
  1. Standard library imports
  2. Third-party imports
  3. Local / project imports

### Line Endings

All files in this repository **must** use **CRLF** (`\r\n`) line endings, not LF (`\n`).
Configure your editor and Git accordingly:

```
git config core.autocrlf true
```

Or use a `.gitattributes` file:

```
* text=auto eol=crlf
```

### Indentation

- **Python and JavaScript source files**: use **spaces** (4 spaces per level).
- **Markdown files**: use **tabs** (1 tab per level).

## Custom Agents

This repository provides custom agents in `.github/agents/`. Use `/agent` in Copilot CLI
to browse and select them, or reference them by name in a prompt.

| Agent | Purpose | Example prompts |
|-------|---------|-----------------|
| `create-study` | Create subjective speech quality tests (ACR, DCR, CCR, P.835, P.804) | "create a study", "run a P.804 test", "set up a P.835 study" |
| `analyze-results` | Analyze crowdsourced test results — data cleaning, MOS aggregation | "analyze results", "parse results", "evaluate the study" |

See [`AGENTS.md`](../AGENTS.md) for full details and trigger phrases.
