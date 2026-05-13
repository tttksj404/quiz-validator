# Domain Config Schema

Each domain (AWS-SAA, PMP, CFA, custom) has a JSON config that the detector loads.

## Required fields

```json
{
  "domain_id": "aws-saa",
  "display_name": "AWS Solutions Architect Associate",
  "version": "1.0.0",
  "anchor_path": "anchors/aws_official_samples.json",

  "banned_stem_patterns": [
    "\\bwhich of the following best\\b",
    "\\bin the context of cloud architecture\\b"
  ],

  "banned_words": {
    "leverage": "use/apply",
    "robust": "use specific numbers"
  },

  "stem_starter_regex": [
    "^An?\\s+\\w+",
    "^After\\s+",
    "^During\\s+"
  ],

  "number_patterns": [
    "\\d+\\s*(TB|GB|MB|KB|PB)",
    "\\d+\\s*(ms|seconds?|minutes?|hours?)",
    "\\$\\s*\\d+"
  ],

  "industry_keywords": {
    "fintech": ["fintech", "trading", "banking"],
    "healthcare": ["healthcare", "HIPAA"]
  },

  "confusing_pairs": [
    ["SQS", "SNS", "EventBridge"],
    ["Multi-AZ", "Read Replica"]
  ],

  "ai_summary_phrases": [
    "\\bin summary\\b",
    "\\bin conclusion\\b"
  ],

  "doc_link_regex": "docs\\.aws\\.amazon\\.com|aws\\.amazon\\.com/\\w+",

  "thresholds": {
    "option_length_stdev_min": 8,
    "option_length_spread_min": 20,
    "em_dash_max": 1,
    "specific_numbers_min": 2
  },

  "hard_rules": [
    "banned_stem", "banned_words", "stem_starter",
    "option_length_stdev", "option_length_spread",
    "em_dash_limit", "explanation_no_ai_ending"
  ],

  "soft_rules": [
    "specific_numbers", "industry_context",
    "confusing_pair", "explanation_doc_link"
  ]
}
```

## How to create a new domain

1. Copy `aws-saa.json` as `mydomain.json`
2. Replace `domain_id`, `display_name`
3. Define `banned_stem_patterns` — patterns that mark AI-tell in your domain
4. Define `banned_words` — vocabulary that signals AI slop in your domain
5. Define `industry_keywords` — context vocabulary for your domain
6. Define `confusing_pairs` — concepts in your domain that test-takers commonly confuse
7. Collect 10 anchor questions from public/legal source
8. Run `python scripts/calibrate.py mydomain.json`
9. Adjust thresholds until anchor PASSes 100% HARD
10. Now generator + validator work for your domain
