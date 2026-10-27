"""Eval harness (PRD §9) — scheduled for D7 per .ztacp/plan.md.

Planned metrics: diagnosis accuracy (top-1/top-3), groundedness after
verifier, fix success rate, FP rate on healthy control, median diagnosis
time. Ground truth: mock datasets carry ground_truth_mode; real datasets
read data/manifest.json (zone B).
"""
