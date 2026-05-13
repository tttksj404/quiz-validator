#!/usr/bin/env python3
"""Check answer letter distribution + chi-square against expected 25% each.

Usage:
  python answer_distribution.py <questions_dir>
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from collections import Counter


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python answer_distribution.py <questions_dir>")
        return 1
    d = Path(sys.argv[1])
    files = list(d.glob("*.json"))
    if not files:
        print(f"No JSON files in {d}")
        return 1
    answers = []
    for f in files:
        q = json.loads(f.read_text(encoding="utf-8"))
        correct = q.get("correct", "")
        for ch in correct.split(","):
            answers.append(ch.strip())
    counter = Counter(answers)
    total = len(answers)
    expected = total / 4

    print(f"=== Answer distribution: {total} answers across {len(files)} questions ===\n")
    chi_sq = 0.0
    print(f"{'Letter':<8} {'Count':<8} {'Pct':<8} {'Expected':<10}")
    print("-" * 40)
    for letter in ["A", "B", "C", "D", "E"]:
        count = counter.get(letter, 0)
        if count == 0 and letter == "E":
            continue
        pct = 100 * count / total
        chi_sq += ((count - expected) ** 2) / expected if expected > 0 else 0
        print(f"{letter:<8} {count:<8} {pct:<7.1f}% {expected:.1f}")

    print(f"\nChi-square statistic: {chi_sq:.2f}")
    print(f"Threshold (4 categories, df=3, p=0.05): 7.81")
    if chi_sq > 7.81:
        print("[X] FAIL: distribution significantly skewed from 25% each.")
        print("    Rewrite some questions to shift the correct letter.")
        return 1
    print("[OK] Distribution within acceptable range.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
