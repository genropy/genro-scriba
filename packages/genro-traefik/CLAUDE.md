# Claude Code Instructions - genro-traefik

**Parent Document**: This project follows all policies from the central [meta-genro-modules CLAUDE.md](https://github.com/softwellsrl/meta-genro-modules/blob/main/CLAUDE.md)

## Project-Specific Context

### Current Status
- Development Status: Alpha
- Has Implementation: Yes

### Project Description
Traefik v3 configuration builder for Genropy. Models the entire Traefik v3 grammar
(static + dynamic configuration, HTTP/TCP/UDP/TLS, all 23+ middleware types) using
the genro-bag builder system with @element/@abstract decorators.

The builder IS the documentation — every @element docstring is an encyclopedic
reference for the corresponding Traefik concept.

### Key Components

- **TraefikBuilder**: Complete Traefik v3 grammar (~150 @element, ~7 @abstract)
- **TraefikCompiler**: Schema-driven YAML compiler using compile_kwargs
- **TraefikApp**: Application wrapper with recipe(), to_yaml(), check()

### Dependencies

- `genro-bag>=0.1.0` (core builder infrastructure)
- `pyyaml>=6.0` (YAML serialization)

### Architecture

The compile_kwargs system drives all YAML rendering:
- `compile_yaml_key` — YAML key name (overrides snake_to_camel)
- `compile_yaml_type` — rendering mode: "named", "list", "csv"
- `compile_yaml_list_key` — groups auto-labeled children as YAML list

---

**All general policies are inherited from the parent document.**
