# data — Campaign Doctor synthetic data

Owner: W-3 (currently S-1 acting, contingency #1). Schemas: `/contracts/data.schemas.md`.

## Generation

```bash
python3 data/generate.py --out data/datasets --seed 42
```

- 8 campaigns: `control_healthy` + modes 1–7 from PRD §8 (manifest.json holds seeds and modes).
- Determinism: the same seed → identical files (tests in `data/tests/`).
- Stdlib only; tests: `backend/.venv/bin/python -m pytest data/tests -q`.
