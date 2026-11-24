# quiz-validator

Heuristic AI-tell detector for machine-generated multiple-choice quiz questions. 11 calibrated checks. Domain-agnostic JSON config. Catches the patterns LLMs reliably produce.

## Why this exists

Every AI-generated practice exam reads the same way:

> Which of the following BEST describes a robust and scalable solution that leverages AWS services to seamlessly streamline cloud workloads?

Once you see the pattern, you can't unsee it. This validator flags it before the question ships.

For a top-down learning view of how CLI input, JSON schema checks, domain configs, rule evaluation, calibration, and failure handling interact, see [docs/LEARNING_GUIDE.md](docs/LEARNING_GUIDE.md).

## What it catches

| HARD rules (auto-fail) | SOFT rules (quality score 0-100) |
| --- | --- |
| Banned stem prefixes (`Which of the following BEST...`) | Specific numbers (TB / ms / $ / %) |
| LLM slop vocabulary (leverage, robust, seamless, synergy, paradigm) | Industry context (fintech, healthcare, media, ...) |
| Stem starter rotation | Confusing-pair distractors (SQS vs SNS, etc.) |
| Option length stdev (≥ 8) and spread (≥ 20) | Domain doc link in explanation |
| Em-dash ceiling (≤ 1 per question) |  |
| AI summary phrases (`In summary`, `In conclusion`) |  |

## Calibration finding

AWS's officially released SAA-C03 sample questions:
- HARD pass rate: **10/10** ✅
- Average quality score: **8/100**

The official samples are clean (no AI-tells) but bland (generic "A company" scenarios, no specific numbers, no industry context). Calibrated generation through this validator can produce questions that pass the same HARD checks *and* score 80+ on quality signals — richer scenarios while staying inside the strict rules.

## Usage

```bash
# Calibrate against your anchor (expect 100% HARD-pass on real exam samples)
python quiz_validator.py --domain aws-saa.json --calibrate

# Validate a single question
python quiz_validator.py --domain aws-saa.json path/to/question.json

# Batch
python quiz_validator.py --domain aws-saa.json --batch questions_dir/

# Answer-letter distribution chi-square
python answer_distribution.py questions_dir/
```

## Question JSON schema

```json
{
  "id": "Q-001",
  "domain": "D1_secure",
  "stem": "A healthcare startup stores 8 TB of patient records in Amazon S3 and...",
  "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
  "correct": "D",
  "explanation": "..."
}
```

## Domain config

See [`_schema.md`](_schema.md) for full field documentation. [`aws-saa.json`](aws-saa.json) is the working AWS SAA-C03 calibration.

To add a new domain (PMP, CFA, USMLE, language exam, custom subject):
1. Gather ~10 anchor questions from a legal public source
2. Copy `aws-saa.json` as `mydomain.json` and edit
3. Run `--calibrate` until anchor hits 100% HARD-pass
4. Use the validator on your generated questions

## Anchor included

[`anchor_aws_saa.json`](anchor_aws_saa.json) contains the 10 AWS-released SAA-C03 sample questions (publicly available from AWS Training & Certification). Use as a reference for tone and structure when designing new domains.

## Trade-offs

The checks are heuristic (regex + statistical), not ML-based:

- **Pros**: transparent, fast, no training data, no model dependency, debuggable per-rule
- **Cons**: gameable — anyone with the rule list can write past it; doesn't catch deeper LLM tells (overly-clean argument structure, suspicious internal consistency)

Gaming the validator is arguably the goal: if a model can pass these checks consistently, its output is indistinguishable from human-written on these axes. The validator is a forcing function, not a final arbiter.

## Full product

The validator is the open part. There's a larger commercial product around it (Obsidian vault template + Claude Code skill pack + 30 calibrated AWS questions + a guide for adding any domain): see the project website.

## License

MIT — use freely. Attribution welcome but not required.

## Discussion

Open an issue with `discussion:` prefix for trade-off discussions, new heuristic ideas, or new domain configs you'd like to contribute. PRs that add domains or relax rules across domains welcome.

## 경험 기록

이 프로젝트를 왜 시작했는지, 무엇을 직접 판단했는지, 결과가 어땠는지는 [docs/experience-record.md](docs/experience-record.md)에 정리했습니다.
