---
name: project-knowledge-architecture
description: "Memory is a cache, ADRs are the record — how the knowledge layers divide"
metadata:
  type: project
  inherit: true   # a child must understand this model to use the structure
---

**Fact:** Memory is a **cache**: pointers, why/history and preferences only; no
fact may live only here. Layers: chat logs = forensic · session logs = narrative ·
**ADRs = binding** · memory = what the agent must know before reading anything.
Every page is Fact + Why + Authority under an 800B cap (whole file).

**Why:** Phil (2026-07-13): "we don't want vendor lock-in, so why is our cache in
a vendor folder?" — memory lives in-repo behind a junction. Heuristic
rot-detection failed; rot is prevented by structure instead.

**Authority:** AGENTS 7
