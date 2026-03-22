# Claude Code Instructions - genro-scriba

**Parent Document**: This project follows all policies from the central [meta-genro-modules CLAUDE.md](https://github.com/softwellsrl/meta-genro-modules/blob/main/CLAUDE.md)

## Project-Specific Context

### Current Status
- Development Status: Alpha
- Has Implementation: Yes

### Project Description
Infrastructure configuration file generator for Genropy. Each supported tool
(Traefik, Docker Compose, etc.) has its own builder and compiler. The builder
models the tool's grammar using @element decorators, the compiler renders the
Bag tree to the tool's native format (YAML, TOML, etc.).

genro-scriba does NOT orchestrate anything — it writes configuration files.

### Key Components

- **ScribaApp**: Base class for all configuration apps (parametric by builder+compiler)
- **base_compiler**: Shared utility functions (walk, resolve, to_yaml_value)
- **traefik/**: TraefikBuilder, TraefikCompiler, TraefikApp (migrated from genro-traefik)
- **compose/**: ComposeBuilder, ComposeCompiler, ComposeApp

### Architecture Principles

1. Each builder has its own compiler — no shared compiler
2. Names follow the target tool's conventions (Traefik=camelCase, Compose=snake_case)
3. The builder IS the documentation — docstrings reference official tool docs
4. genro-scriba generates files, nothing more

### Dependencies

- `genro-bag>=0.1.0` (core builder infrastructure)
- `pyyaml>=6.0` (YAML serialization)

---

**All general policies are inherited from the parent document.**
