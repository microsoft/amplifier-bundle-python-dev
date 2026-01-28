# Python Development Philosophy

This document outlines the core development principles for Python code in the Amplifier ecosystem.

## Core Philosophy: Pragmatic Professionalism

We value **readability over cleverness**, **completion over ambition**, and **context-aware pragmatism over dogmatic rule-following**.

---

## The Six Principles

### 1. Readability is the Goal, Not the Rule

Code should be immediately understandable to any developer. When style rules conflict with clarity, clarity wins.

- **Line length (100-120 chars)**: Prevents awkward breaks in method chains and lambdas
- **Type hints**: Use `Optional[str]` over `str | None` when it reads clearer
- **Conditionals**: Use ternary (`x if cond else y`) OR if/else based on what reads naturally
- **Consistency**: Double quotes, 4-space indents - reduce cognitive load

**Test**: *"Would a new team member understand this in 5 seconds?"*

### 2. Complete or Not At All

Production code should be **finished**. These patterns indicate incomplete code:

| Pattern | What It Signals |
|---------|-----------------|
| `raise NotImplementedError` | Unfinished method (unless `@abstractmethod`) |
| `# TODO:` / `# FIXME:` | Deferred work |
| Empty `pass` statement | Placeholder (unless structural) |
| `mock_*` / `fake_*` / `dummy_*` | Test doubles in production |
| `return "not implemented"` | Deferred implementation |
| `# coming soon` | Feature not ready |

**Key insight**: Every placeholder is a lie to the next developer.

**Legitimate exceptions**:
- `@abstractmethod` with `raise NotImplementedError`
- Exception classes: `class MyError(Exception): pass`
- Protocol definitions: `class MyProtocol(Protocol): ...`
- CLI command groups: `@click.group()\ndef cli(): pass`
- Test files (mocks and stubs are expected)

### 3. Context Wins Over Dogma

Rules exist to serve the code, not the other way around. Know when to break them.

| Situation | Exception | Reason |
|-----------|-----------|--------|
| SQLAlchemy filters | Allow `== True` | Framework requirement |
| Test files | Skip docstrings | Names and assertions are docs |
| `__init__.py` | Allow "unused" imports | Re-exports are intentional |
| Debugging | Allow intermediate variable | Clearer for breakpoints |

**Test**: *"Is this exception for framework needs, or am I just avoiding the fix?"*

### 4. Test Isolation and Clarity

Tests should be isolated, focused, and obviously correct.

- **Mark integration tests explicitly**: `@pytest.mark.integration`
- **Use `importlib` mode**: Allows duplicate test file names across packages
- **Mocks belong in tests**: Not in production code
- **Test names are documentation**: `test_login_fails_with_invalid_token`

### 5. Type Safety as Aid, Not Straitjacket

Types help humans and tools understand code. They're not a coverage metric.

- **Basic mode, not strict**: Catch real errors without demanding perfection
- **Ignore missing stubs**: Don't fail on incomplete ecosystem type hints
- **Focus on boundaries**: Public APIs, function signatures, return types
- **Infer when obvious**: Don't annotate `x = 5` as `x: int = 5`

**Test**: *"Do types answer what this accepts and returns?"*

### 6. Imports Tell a Story

Imports declare dependencies. Make them scannable.

```python
# Good: Clear, sorted, one per line
from pathlib import Path
from typing import Any

import click
from pydantic import BaseModel

from .models import CheckResult
from .config import load_config
```

**Rules**:
- One import per line (each is a declaration)
- Clear ordering: stdlib → third-party → first-party → local
- Group with blank lines between sections
- Combine `from x import a, b` for related items only

### 7. Respect Encapsulation Boundaries

**Never access private attributes (`_name`) from outside a class.** Private attributes are implementation details that can change without notice.

| Pattern | Problem | Correct Approach |
|---------|---------|------------------|
| `getattr(obj, "_internal", None)` | Bypasses encapsulation | Request a public API |
| `obj._private_attr` | Depends on implementation | Use protocol/interface |
| Chained unwrapping | Compounds fragility | Expose capability at top level |

```python
# BAD: Reaching into private internals
bundle_resolver = getattr(resolver, "_bundle", resolver)
activator = getattr(bundle_resolver, "_activator", None)

# GOOD: Use or request a public API
activator = resolver.get_activator()
```

**Key insight**: If you can't do something through the public interface, the fix is to extend the interface—not bypass it.

**Test**: *"Would this code break if the internal implementation changed?"*

---

## The Golden Rule

> Write code as if the next person to read it is a sleep-deprived developer at 2 AM during an incident. Make their life easier.

---

## Quick Reference

### Always Do
- Add type hints to public functions
- Use descriptive variable names
- Keep functions focused (one responsibility)
- Handle errors explicitly
- Write docstrings for public APIs

### Never Do
- Leave TODOs in production code
- Use single-letter variables (except `i`, `j` in loops, `_` for ignored)
- Catch bare `Exception` without re-raising or logging
- Use mutable default arguments (`def foo(items=[]): ...`)
- Import `*` in production code

### Consider Context
- Long lines: Break if it helps, don't break if it hurts
- Comments: Explain *why*, not *what*
- Abstractions: Add only when you have 3+ concrete cases
- Type unions: `Optional` for nullable, `|` for true unions
