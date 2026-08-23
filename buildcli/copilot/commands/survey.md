---
description: Profile the repository and generate the shared agent context, split into domain bands.
arguments: Optional band focus (service, interface, store, verify, delivery)
output: .buildcli/context.md
usage: Paste this prompt into Copilot Chat
---

## Prompt

Survey this repository and generate `.buildcli/context.md`.

Steps:
1. Detect languages, frameworks, runtimes, and package managers from the repository files.
2. Identify what this system connects to: databases, queues, third-party APIs, auth providers, cloud services.
3. Infer the architecture and module boundaries from code and config.
4. Write `.buildcli/context.md` with the header blocks (Metadata, Stack, Architecture, Engineering Standards, Agent Instructions) plus five bands: `[band:service]`, `[band:interface]`, `[band:store]`, `[band:verify]`, `[band:delivery]`.
5. Return a summary of findings, per-band confidence, and everything marked `NEEDS CLARIFICATION`.

Rules:
- Facts from files beat inference.
- Each band stays self-contained and under roughly 300 words — skills load one band, never the whole file.
- No fact repeated across bands.
- Mark uncertain items `NEEDS CLARIFICATION` rather than guessing.
