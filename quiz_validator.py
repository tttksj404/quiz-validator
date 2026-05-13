#!/usr/bin/env python3
"""Domain-agnostic AI-pattern detector for quiz questions.

Loads domain config JSON, validates questions against HARD/SOFT rules.
Works with any domain (AWS-SAA, PMP, CFA, custom).

Usage:
  python quiz_validator.py --domain <path/to/domain.json> <question.json>
  python quiz_validator.py --domain <path/to/domain.json> --batch <dir>
  python quiz_validator.py --domain <path/to/domain.json> --calibrate
      # Runs anchor through detector; expects 100% HARD-PASS

Exit code:
  0 = HARD PASS
  1 = HARD FAIL

Question JSON schema:
  {
    "id": "Q-001",
    "stem": "...",
    "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
    "correct": "B",
    "explanation": "..."
  }
"""
from __future__ import annotations
import argparse
import json
import re
import statistics
import sys
from pathlib import Path
from typing import Any


class DomainConfig:
    """Loaded domain config with compiled regex."""

    def __init__(self, path: Path) -> None:
        self.path = path
        data = json.loads(path.read_text(encoding="utf-8"))
        self.domain_id: str = data["domain_id"]
        self.display_name: str = data["display_name"]
        self.banned_stem_patterns = [re.compile(p, re.IGNORECASE) for p in data["banned_stem_patterns"]]
        self.banned_words: dict[str, str] = data["banned_words"]
        self.stem_starter_regex = [re.compile(p, re.IGNORECASE) for p in data["stem_starter_regex"]]
        self.number_patterns = [re.compile(p, re.IGNORECASE) for p in data["number_patterns"]]
        self.industry_keywords: dict[str, list[str]] = data["industry_keywords"]
        self.confusing_pairs: list[list[str]] = data["confusing_pairs"]
        self.ai_summary_phrases = [re.compile(p, re.IGNORECASE) for p in data["ai_summary_phrases"]]
        self.doc_link_regex = re.compile(data["doc_link_regex"]) if data.get("doc_link_regex") else None
        self.thresholds: dict[str, float] = data["thresholds"]
        self.hard_rules: set[str] = set(data["hard_rules"])
        self.soft_rules: set[str] = set(data["soft_rules"])
        self.anchor_path: str = data.get("anchor_path", "")


# ============================================================
# Checks (all take cfg + question, return list of results)
# ============================================================

def check_banned_stem(cfg: DomainConfig, stem: str) -> list[tuple[str, bool, str]]:
    for pat in cfg.banned_stem_patterns:
        if pat.search(stem):
            return [("banned_stem", False, f"matched: {pat.pattern}")]
    return [("banned_stem", True, "no AI-tell stems")]


def check_banned_words(cfg: DomainConfig, text: str) -> list[tuple[str, bool, str]]:
    found = []
    text_lower = text.lower()
    for word in cfg.banned_words:
        if re.search(rf"\b{re.escape(word)}\b", text_lower):
            found.append(word)
    if found:
        return [("banned_words", False, f"found: {', '.join(found[:5])}")]
    return [("banned_words", True, "no slop vocabulary")]


def check_stem_starter(cfg: DomainConfig, stem: str) -> list[tuple[str, bool, str]]:
    for pat in cfg.stem_starter_regex:
        if pat.match(stem.strip()):
            return [("stem_starter", True, "matches allowed starter")]
    return [("stem_starter", False, "stem doesn't match any allowed starter regex")]


def check_specific_numbers(cfg: DomainConfig, stem: str) -> list[tuple[str, bool, str]]:
    count = 0
    matches = []
    for pat in cfg.number_patterns:
        for m in pat.finditer(stem):
            count += 1
            matches.append(m.group(0))
    threshold = int(cfg.thresholds.get("specific_numbers_min", 2))
    if count >= threshold:
        return [("specific_numbers", True, f"{count} numbers: {matches[:3]}")]
    return [("specific_numbers", False, f"only {count} (need >={threshold})")]


def check_industry_context(cfg: DomainConfig, stem: str) -> list[tuple[str, bool, str]]:
    for industry, keywords in cfg.industry_keywords.items():
        for kw in keywords:
            if re.search(rf"\b{re.escape(kw)}\b", stem, re.IGNORECASE):
                return [("industry_context", True, f"detected: {industry}")]
    return [("industry_context", False, "no industry context detected")]


def check_option_length_variance(cfg: DomainConfig, options: list[str]) -> list[tuple[str, bool, str]]:
    cleaned = [re.sub(r"^[A-E]\)\s*", "", opt).strip() for opt in options]
    lengths = [len(c) for c in cleaned]
    if len(lengths) < 2:
        return [("option_length_stdev", False, "need >=2 options"),
                ("option_length_spread", False, "need >=2 options")]
    stdev = statistics.stdev(lengths)
    spread = max(lengths) - min(lengths)
    stdev_min = cfg.thresholds.get("option_length_stdev_min", 8)
    spread_min = cfg.thresholds.get("option_length_spread_min", 20)
    results = []
    results.append(("option_length_stdev",
                    stdev >= stdev_min,
                    f"stdev {stdev:.1f} (need >={stdev_min})"))
    results.append(("option_length_spread",
                    spread >= spread_min,
                    f"max-min {spread} (need >={spread_min})"))
    return results


def check_em_dash(cfg: DomainConfig, text: str) -> list[tuple[str, bool, str]]:
    count = text.count("—") + text.count(" -- ")
    threshold = int(cfg.thresholds.get("em_dash_max", 1))
    if count <= threshold:
        return [("em_dash_limit", True, f"{count} em-dashes (max {threshold})")]
    return [("em_dash_limit", False, f"{count} em-dashes (>{threshold}, AI tell)")]


def check_confusing_pair(cfg: DomainConfig, options: list[str]) -> list[tuple[str, bool, str]]:
    all_text = " ".join(options)
    for pair in cfg.confusing_pairs:
        hits = sum(1 for item in pair if re.search(rf"\b{re.escape(item)}\b", all_text, re.IGNORECASE))
        if hits >= 2:
            return [("confusing_pair", True, f"contains pair: {pair[:hits]}")]
    return [("confusing_pair", False, "no confusing concept pair in options")]


def check_explanation_no_ai_ending(cfg: DomainConfig, explanation: str) -> list[tuple[str, bool, str]]:
    for pat in cfg.ai_summary_phrases:
        if pat.search(explanation):
            return [("explanation_no_ai_ending", False, f"AI summary phrase: {pat.pattern}")]
    return [("explanation_no_ai_ending", True, "no AI summary phrases")]


def check_explanation_doc_link(cfg: DomainConfig, explanation: str) -> list[tuple[str, bool, str]]:
    if not cfg.doc_link_regex:
        return [("explanation_doc_link", True, "no doc_link_regex configured (skip)")]
    if cfg.doc_link_regex.search(explanation):
        return [("explanation_doc_link", True, "doc link present")]
    return [("explanation_doc_link", False, "no domain doc link")]


# ============================================================
# Audit
# ============================================================

def audit_question(cfg: DomainConfig, q: dict[str, Any]) -> tuple[bool, list[tuple[str, bool, str]], int]:
    """Returns (hard_pass, all_results, quality_score)."""
    stem = q.get("stem", "")
    options = q.get("options", [])
    explanation = q.get("explanation", "")
    full_text = stem + " " + " ".join(options) + " " + explanation

    all_results: list[tuple[str, bool, str]] = []
    all_results.extend(check_banned_stem(cfg, stem))
    all_results.extend(check_banned_words(cfg, full_text))
    all_results.extend(check_stem_starter(cfg, stem))
    all_results.extend(check_specific_numbers(cfg, stem))
    all_results.extend(check_industry_context(cfg, stem))
    all_results.extend(check_option_length_variance(cfg, options))
    all_results.extend(check_em_dash(cfg, full_text))
    all_results.extend(check_confusing_pair(cfg, options))
    all_results.extend(check_explanation_no_ai_ending(cfg, explanation))
    all_results.extend(check_explanation_doc_link(cfg, explanation))

    hard_pass = all(r[1] for r in all_results if r[0] in cfg.hard_rules)
    soft_results = [r for r in all_results if r[0] in cfg.soft_rules]
    soft_passed = sum(1 for r in soft_results if r[1])
    quality_score = round(100 * soft_passed / len(soft_results)) if soft_results else 0
    return hard_pass, all_results, quality_score


def print_report(cfg: DomainConfig, qid: str, results: list[tuple[str, bool, str]], qscore: int) -> None:
    print(f"\n=== {qid} ===")
    for name, ok, msg in results:
        kind = "H" if name in cfg.hard_rules else "S"
        mark = "PASS" if ok else "FAIL"
        print(f"  [{kind}/{mark}] {name}: {msg}")
    print(f"  Quality score (soft signals): {qscore}/100")


# ============================================================
# Calibration (run detector against domain's anchor)
# ============================================================

def calibrate(cfg: DomainConfig) -> int:
    anchor_path = Path(cfg.anchor_path)
    if not anchor_path.is_absolute():
        # Try several resolution strategies for portability
        candidates = [
            cfg.path.parent / cfg.anchor_path,         # alongside config (standalone repo)
            cfg.path.parent.parent / cfg.anchor_path,  # one level up (full vault layout)
            Path.cwd() / cfg.anchor_path,              # current working directory
        ]
        for cand in candidates:
            if cand.exists():
                anchor_path = cand
                break
        else:
            print(f"Anchor not found. Tried: {[str(c) for c in candidates]}")
            return 1
    elif not anchor_path.exists():
        print(f"Anchor not found: {anchor_path}")
        return 1
    data = json.loads(anchor_path.read_text(encoding="utf-8"))
    questions = data["questions"]
    n = len(questions)
    print(f"=== Calibration: {n} {cfg.display_name} anchor questions ===\n")

    hard_pass_count = 0
    qscores: list[int] = []
    rule_pass: dict[str, int] = {}
    for q in questions:
        hp, results, qs = audit_question(cfg, q)
        qscores.append(qs)
        if hp:
            hard_pass_count += 1
        for name, ok, _msg in results:
            rule_pass[name] = rule_pass.get(name, 0) + (1 if ok else 0)

    print(f"Overall HARD-PASS: {hard_pass_count}/{n} = {100*hard_pass_count/n:.0f}%")
    print(f"Avg quality score: {sum(qscores)/n:.0f}/100\n")
    print(f"{'Rule':<35} {'Pass':<10} {'Type'}")
    print("-" * 60)
    for rule, count in sorted(rule_pass.items(), key=lambda x: x[1]):
        kind = "HARD" if rule in cfg.hard_rules else "SOFT"
        pct = 100 * count / n
        print(f"{rule:<35} {count}/{n:<6} {kind} ({pct:.0f}%)")

    if hard_pass_count == n:
        print(f"\n[OK] Calibration PASSED: all {n} anchor questions HARD-pass")
        return 0
    print(f"\n[X] Calibration FAILED: {n - hard_pass_count} anchor questions HARD-fail")
    print("    Adjust thresholds or move rule from HARD to SOFT in domain config.")
    return 1


# ============================================================
# CLI
# ============================================================

def main() -> int:
    parser = argparse.ArgumentParser(description="Domain-agnostic quiz validator")
    parser.add_argument("--domain", required=True, help="path to domain config JSON")
    parser.add_argument("question_file", nargs="?", help="path to question JSON")
    parser.add_argument("--batch", help="directory of question JSONs")
    parser.add_argument("--calibrate", action="store_true", help="run detector against anchor")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    cfg = DomainConfig(Path(args.domain))

    if args.calibrate:
        return calibrate(cfg)

    if args.batch:
        d = Path(args.batch)
        files = list(d.glob("*.json"))
        if not files:
            print(f"No .json files in {d}")
            return 1
        total = len(files)
        passed = 0
        qscores: list[int] = []
        for f in files:
            q = json.loads(f.read_text(encoding="utf-8"))
            hp, results, qs = audit_question(cfg, q)
            qscores.append(qs)
            if hp:
                passed += 1
            if args.verbose or not hp:
                print_report(cfg, q.get("id", f.stem), results, qs)
        avg_q = sum(qscores) / len(qscores) if qscores else 0
        print(f"\n=== BATCH ({cfg.display_name}): HARD {passed}/{total}, avg quality {avg_q:.0f}/100 ===")
        return 0 if passed == total else 1

    if not args.question_file:
        parser.print_help()
        return 1
    q = json.loads(Path(args.question_file).read_text(encoding="utf-8"))
    hp, results, qs = audit_question(cfg, q)
    print_report(cfg, q.get("id", "?"), results, qs)
    print(f"\nVerdict: HARD {'PASS' if hp else 'FAIL'}, quality {qs}/100")
    return 0 if hp else 1


if __name__ == "__main__":
    sys.exit(main())
