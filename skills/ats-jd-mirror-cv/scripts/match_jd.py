#!/usr/bin/env python3
"""Score a CV PDF against a job description's keywords.

Usage: python3 match_jd.py cv.pdf jd_keywords.json

jd_keywords.json:
  {"company": "Acme", "keywords": ["SaaS", "MEDDPICC", ...], "requirements_score": 90}

keywords: every JD term in the JD's own wording (stems are fine: "forecast" matches "forecasting").
requirements_score: 0-100, share of hard requirements met (years, industry, language, location).
Total = 60% keyword match + 40% requirements. Target: keyword match >= 90%.
Exit code 2 if keyword match is below 90%, so the build loop knows to fix misses.
"""
import json
import re
import subprocess
import sys


def pdf_text(path):
    t = subprocess.run(["pdftotext", path, "-"], capture_output=True, text=True).stdout
    t = re.sub(r"-\s*\n\s*", "-", t)          # re-join words hyphenated across lines
    return re.sub(r"\s+", " ", t).lower()


def main():
    cv, jd = sys.argv[1], json.load(open(sys.argv[2]))
    text = pdf_text(cv)
    kws = jd["keywords"]
    hit = [k for k in kws if k.lower() in text]
    miss = [k for k in kws if k.lower() not in text]
    kp = round(100 * len(hit) / max(len(kws), 1))
    req = jd.get("requirements_score")
    total = round(0.6 * kp + 0.4 * req) if req is not None else None
    print(f"Company: {jd.get('company', '?')}")
    print(f"Keyword match: {kp}% ({len(hit)}/{len(kws)})")
    if req is not None:
        print(f"Requirements: {req}%  ->  TOTAL: {total}%")
    print("Missing: " + (", ".join(miss) if miss else "none"))
    print("Em dash found!" if "—" in text else "No em dashes.")
    return 0 if kp >= 90 else 2


if __name__ == "__main__":
    sys.exit(main())
