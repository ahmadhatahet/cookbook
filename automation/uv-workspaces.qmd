---
title: "Encapsulating Projects as Local Packages via UV"
---

Structuring your development directories as formal packages allows you to seamlessly resolve inner absolute module paths during dynamic `uv run` sessions without modifying execution paths manually.

### Directory Architecture
Organize your functional directories by placing source assets inside an isolated package domain:
```text
my-project/
├── pyproject.toml
├── uv.lock
└── src/
    ├── __init__.py
    ├── core.py
    └── main.py
```

### Workspace Configuration
Configure `pyproject.toml` to declare the workspace directory as an editable package installation root component:
```toml
[project]
name = "my-project"
version = "0.1.0"
dependencies = []
requires-python = ">=3.11"

[tool.uv]
dev-dependencies = []
# Instructs UV to treat this root or targeted source layout as an installable package
packages = ["src"]
```

### Execution and Importing Patterns
Because the workspace treats `src` as a root package asset, scripts inside any folder can clearly import from sibling modules:
```python
# Inside src/main.py
from src.core import processing_engine

if __name__ == "__main__":
    processing_engine.start()
```
Run targeted files natively by executing:
```bash
uv run python src/main.py
```
