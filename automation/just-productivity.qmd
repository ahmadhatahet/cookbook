---
title: "Tactical Automation with Just"
---

The `just` tool provides a modern alternative to traditional Makefiles for managing operational tasks.

### Installation & Global Setup
Install `just` across core operating systems via standard package managers:
```bash
# macOS
brew install just

# Linux (Ubuntu/Debian)
sudo apt install just
```

### Directory-Level Implementation
Create a standard project recipe runner file named `justfile` in the root of your project directory:
```makefile
# Definal default behavior
default:
    @just --list

# Set up operational virtual environments
setup:
    uv sync

# Execute local code suites
run-app:
    uv run python -m src.main
```

### Execution Commands
Invoke targets directly inside the project root terminal directory:
```bash
just setup      # Triggers project dependency alignment
just run-app    # Boots localized execution target
```
