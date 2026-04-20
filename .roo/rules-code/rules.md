# Custom Instructions for Roo

## Documentation Context
- **Primary Source:** Always check `./.docs/` for library documentation, API references, and usage examples before writing code or suggesting implementations.
- **Search Strategy:** If a task involves a specific library, use `ls` or `read_file` on the corresponding file in `./.docs/` to verify current method signatures and patterns.
- **Strict Adherence:** Do not assume external documentation is up-to-date if a local version exists in the `./.docs/` directory.

## Debugging Workflow
- When debugging errors related to external dependencies, cross-reference the error trace with the local docs in `./.docs/`.
- Look for "Breaking Changes" or "Migration" sections in those local files if a library update was recently performed.

## Code Generation
- Ensure all generated code snippets follow the patterns defined in the local documentation.
- Use the exact naming conventions and architecture patterns found in `./.docs/`.
- Ensure all generated code adheres to Python 3.11+.