# Language and grammar correction rules

When editing this repository, improve language quality in a safe, minimal, and non-breaking way.

## Goal
Correct grammar, spelling, punctuation, clarity, and consistency in:
- Markdown documentation
- README files
- comments
- docstrings
- code examples written as prose
- HTML visible text
- HTML accessibility text such as `alt`, `title`, `aria-label`, and `placeholder`
- user-facing messages in code, only when the meaning is clearly preserved

## Do not change
Do not modify any of the following unless explicitly asked:
- program logic or behavior
- variable names
- function names
- class names
- file names
- import paths
- URLs
- API names
- selectors
- IDs
- keys in JSON, YAML, or objects
- database fields
- CLI flags
- commands
- test expectations
- code formatting unrelated to the language fix

## Editing rules
- Prefer the smallest safe diff.
- Preserve the original meaning.
- Preserve the existing tone unless it is clearly confusing or unprofessional.
- Keep technical terminology unchanged.
- Keep product names, library names, and framework names unchanged.
- Do not rewrite text just for style preference.
- Do not make speculative edits.
- Do not “improve” wording inside code identifiers or structured data.
- Do not touch generated files.

## Code-specific rules
For Python and JavaScript:
- Fix grammar in comments, docstrings, help text, and clearly user-facing strings.
- Do not alter executable code unless required for a grammar fix in a user-facing string and the change is behavior-safe.
- Do not rename symbols to improve wording.

For HTML:
- Fix visible text and accessibility-related text.
- Do not change class names, IDs, data attributes, script content, or linked resource paths.
- Do not change markup structure unless needed to correct broken visible text.

## Documentation rules
For Markdown and docs:
- Correct grammar, spelling, punctuation, headings, and sentence clarity.
- Keep meaning, structure, and technical accuracy intact.
- Preserve code blocks exactly unless explicitly asked to edit them.

## Output behavior
When asked to perform these fixes:
- first identify the text issues
- then apply the corrections
- keep the diff minimal
- summarize what was changed
- call out anything ambiguous instead of guessing