# Adding a Changelog Entry

This project uses [towncrier](https://pypi.org/project/towncrier/) to manage the changelog.

## Creating a News Fragment

When you make a change that should be included in the changelog, create a new file in this directory with the following naming convention:

```
<issue_number>.<type>.md
```

### Types

The valid types are:

- `breaking` - Breaking changes
- `bugfix` - Bug fixes
- `feature` - New features
- `misc` - Miscellaneous changes

### Examples

```
123.bugfix.md
456.feature.md
789.breaking.md
```

### Content

The file should contain a **single line** (or sentence) describing the change in **markdown format**. The line should be concise and focused on the change itself. Do not add issue numbers in the content; they will be automatically appended.

Example content for `123.bugfix.md`:
```markdown
Fix issue authenticating against private registries where the `X-Registry-Auth` header would require URL-safe substitutions.
```

Note: The issue/PR number will be automatically added from the filename.

Example content for `456.feature.md`:
```markdown
Add support for Docker context endpoints with TLS, reading configuration from `~/.docker/contexts/` and respecting `DOCKER_CONTEXT` environment variable.
```

### Guidelines

- Use markdown formatting (e.g., backticks for code, etc.)
- Keep it to a single sentence (break into multiple sentences if needed, but avoid making it too long)
- Focus on what changed and why, not implementation details
- Reference issue/PR numbers at the end in parentheses if applicable

### Building the Changelog

The changelog is automatically built during the release process. To preview what the changelog will look like, run:

```bash
uv run towncrier build --draft
```
