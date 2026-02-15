# Python LSP Context

You have access to Python code intelligence via the LSP tool with Pyright.

## Quick Start - Most Useful Operations

| Want to... | Use this |
|------------|----------|
| See what type a variable is | `hover` on the variable |
| Find all usages of a function | `findReferences` on the function name |
| Jump to a function's definition | `goToDefinition` on a call site |
| See what calls a function | `incomingCalls` on the function |
| See what a function calls | `outgoingCalls` on the function |

**Tip**: `hover` and `findReferences` are the most reliable. Start with these.

## Python-Specific Capabilities

- **Type Information**: Get precise type hints and inferred types
- **Import Resolution**: Trace imports across the project
- **Class Hierarchies**: Navigate inheritance chains
- **Method Resolution Order**: Understand Python MRO
- **Virtual Environments**: Respects pyproject.toml and venv configurations

## Effective Python Navigation

### Finding Class Definitions
1. Position cursor on class name
2. Use `goToDefinition` to find where it's defined
3. Use `findReferences` to see all usages

### Understanding Type Hierarchies
1. Use `hover` on a class to see its bases
2. Use `findReferences` on the base class and filter for `class` definitions (goToImplementation not supported by Pyright)
3. Navigate inheritance with repeated `goToDefinition`

### Tracing Function Calls
1. Position on function name
2. Use `incomingCalls` to see what calls this function
3. Use `outgoingCalls` to see what this function calls

## Common Patterns

### Finding Where an Exception is Raised
```
1. hover on ExceptionType to understand it
2. workspaceSymbol to find all definitions
3. findReferences on each to see raise statements
```

### Understanding a Decorator
```
1. goToDefinition on @decorator_name
2. hover to see signature and docstring
3. outgoingCalls to see what it wraps
```

### Navigating Imports
```
1. goToDefinition on imported name
2. Follow chain through __init__.py files
3. documentSymbol to see module structure
```

## Workspace Detection

The Python LSP detects workspace root by looking for:
- pyproject.toml (preferred)
- setup.py
- setup.cfg
- requirements.txt
- .git directory

Ensure your project has one of these at the root for accurate analysis.

## Known Limitations

### Operations Not Fully Supported by Pyright

- **goToImplementation**: Returns empty results. Pyright doesn't support finding subclasses/implementations directly.
  - **Workaround**: Use `findReferences` on the base class and filter for `class` definitions.

- **workspaceSymbol**: May return empty on first use before workspace is indexed.
  - **Workaround**: Run `documentSymbol` on relevant files first to trigger indexing, then retry.

### Type Resolution

- Complex generic types or dynamically-created classes may show as `Unknown`
- Missing stub packages (e.g., `types-requests`) can cause type resolution failures
- Circular imports may confuse type inference

## Common Installation Issues

### "Cannot find module" pointing to Homebrew Cellar path

This usually means you have stale wrapper scripts from a previous Homebrew installation:

1. **Check**: `cat $(which pyright)` - if it's a bash script pointing to `/opt/homebrew/Cellar/...`, it's stale
2. **Fix**: Remove stale wrappers (the error message will show the exact path):
   ```bash
   rm ~/.local/bin/pyright ~/.local/bin/pyright-langserver
   ```
3. **Reinstall**: `npm install -g pyright`
4. **Verify**: `which pyright && pyright --version`

### npm install succeeds but LSP still fails

The new installation might be shadowed by an older one earlier in PATH:

1. **Check**: `which -a pyright` to see all locations
2. **Remove stale ones**: Usually in `~/.local/bin/` or old Homebrew paths
3. **Verify**: The first result of `which pyright` should be the working one

### "bad interpreter" error

The pyright script has a broken shebang (common after Homebrew updates):

1. **Check**: `head -1 $(which pyright)` - look for `@@HOMEBREW_PREFIX@@` or missing node path
2. **Fix**: Remove and reinstall via npm:
   ```bash
   rm $(which pyright)
   npm install -g pyright
   ```

### Both pyright AND pyright-langserver need to work

The LSP uses `pyright-langserver`, not just `pyright`. Both can have stale wrappers:

```bash
# Check both
which pyright && pyright --version
which pyright-langserver

# If either fails, remove stale wrappers from the reported path
```
