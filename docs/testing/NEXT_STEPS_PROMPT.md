# Code Puppy next-steps prompt — testing suite follow-through

Paste everything below the line into Code Puppy.

---

You are working in the HTT Control Tower repo (FastAPI + HTMX + Tailwind, Azure governance platform, 5 brand tenants). A full testing-suite audit was just completed — read `docs/testing/TESTING_SUITE_AUDIT_2026-06.md` first; it is the source of truth for what was added and what remains. The unified gate is `scripts/run_full_suite.sh` (Make targets: `full-suite`, `full-suite-fast`, `full-suite-load`). 71 new tests were added and are green; do not weaken or delete them to make other work pass.

Work these items in order. After each one, run `make full-suite-fast` and confirm every gate is still green before moving on. Use isolated pytest passes per test group (see the ct-pm3 note in the Makefile) — never collapse groups into one pytest run.

1. Fix the dependency conflict in requirements.txt. It pins pydantic 2.13.4 and pydantic-core 2.47.0, which are mutually incompatible, so `uv pip install -r requirements.txt` fails. Regenerate the file from uv.lock using the project's normal export tooling — do not hand-edit pins. Verify with a clean venv install from the regenerated file, then run the unit gate.

2. Repair tests/integration/test_frontend_e2e.py. Its auth_token fixture round-trips the