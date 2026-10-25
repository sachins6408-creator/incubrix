# AI Use Disclosure

This document discloses the use of AI tools in the development and verification of **IncuBrix**:

1. **AI Assistant**: Antigravity (Powered by Google Gemini models).
2. **Key Contributions**:
   - Initial scaffolding and implementation of the modular architecture (`core`, `media`, `nlp`, `engine`, `rendering`, `storage`, `api`).
   - Implementation of the deterministic grammar parser and regex rules for natural-language video editing instructions.
   - Design of the content-anchored canonical timeline with SHA-256 canonical hashing.
   - Generation of the FFmpeg `filter_complex` compilation pipeline handling cuts, speed scaling (video + audio), captions, and segment reordering.
   - Construction of the dark-themed editor interface and front-end controller.
   - Writing 42 pytest automated tests across 7 test modules and 15 scripted session scenarios.
   - Real-environment execution and verification of the dance video (`D:\dance`) ensuring zero byte corruption.
