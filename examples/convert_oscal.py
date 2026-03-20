#!/usr/bin/env python3
"""Convert NIST OSCAL JSON catalogs to nist_strm element format.

Reads the canonical OSCAL JSON for:
  - NIST CSF 2.0 (catalog with functions/categories/subcategories)
  - NIST SP 800-53 rev5 (catalog with families/controls/enhancements)

Outputs nist_strm-compatible element JSON files.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def extract_prose(parts: list[dict], name: str = "statement") -> str:
    """Recursively extract prose from OSCAL parts."""
    texts = []
    for part in parts:
        if part.get("name") == name:
            prose = part.get("prose", "")
            if prose:
                texts.append(prose)
        # Recurse into sub-parts
        for sub in part.get("parts", []):
            if sub.get("name") == name or sub.get("name") == "item":
                prose = sub.get("prose", "")
                if prose:
                    texts.append(prose)
                for subsub in sub.get("parts", []):
                    prose = subsub.get("prose", "")
                    if prose:
                        texts.append(prose)
    return " ".join(texts)


def convert_csf2(input_path: str, output_path: str) -> None:
    """Convert NIST CSF 2.0 OSCAL catalog to nist_strm elements."""
    with open(input_path) as f:
        data = json.load(f)

    catalog = data["catalog"]
    functions = catalog["groups"]

    elements = []

    for func in functions:
        func_id = func["id"].upper()
        func_title = func["title"]

        # Function-level description from parts
        func_prose = ""
        for part in func.get("parts", []):
            if part.get("prose"):
                func_prose = part["prose"]
                break

        # Register function as element
        elements.append({
            "id": f"csf-{func_id}",
            "element_type": "function",
            "identifier": func_id,
            "text": f"{func_title}. {func_prose}".strip(),
            "parent_id": None,
            "metadata": {"level": "function"},
        })

        # Categories (controls within a function)
        for cat in func.get("controls", []):
            cat_id = cat["id"].upper()
            cat_title = cat.get("title", cat_id)
            cat_prose = extract_prose(cat.get("parts", []))
            if not cat_prose:
                cat_prose = cat_title

            elements.append({
                "id": f"csf-{cat_id}",
                "element_type": "category",
                "identifier": cat_id,
                "text": f"{cat_title}: {cat_prose}".strip(),
                "parent_id": f"csf-{func_id}",
                "metadata": {"level": "category", "function": func_id},
            })

            # Subcategories (controls within a category)
            for subcat in cat.get("controls", []):
                sc_id = subcat["id"].upper()
                sc_title = subcat.get("title", sc_id)
                sc_prose = extract_prose(subcat.get("parts", []))
                if not sc_prose:
                    sc_prose = sc_title

                elements.append({
                    "id": f"csf-{sc_id}",
                    "element_type": "subcategory",
                    "identifier": sc_id,
                    "text": f"{sc_id}: {sc_prose}".strip(),
                    "parent_id": f"csf-{cat_id}",
                    "metadata": {
                        "level": "subcategory",
                        "function": func_id,
                        "category": cat_id,
                    },
                })

    output = {
        "document": {
            "id": "nist-csf-2.0",
            "title": "NIST Cybersecurity Framework 2.0",
            "short_name": "CSF 2.0",
            "version": "2.0",
            "author": "National Institute of Standards and Technology",
            "url": "https://csrc.nist.gov/projects/cybersecurity-framework",
            "date": "2024-02-26",
        },
        "elements": elements,
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    funcs = sum(1 for e in elements if e["element_type"] == "function")
    cats = sum(1 for e in elements if e["element_type"] == "category")
    subcats = sum(1 for e in elements if e["element_type"] == "subcategory")
    print(f"CSF 2.0: {funcs} functions, {cats} categories, {subcats} subcategories -> {output_path}")


def convert_sp800_53(input_path: str, output_path: str, families: list[str] | None = None) -> None:
    """Convert NIST SP 800-53 rev5 OSCAL catalog to nist_strm elements.

    Args:
        families: Optional list of family IDs to include (e.g. ['ac', 'at', 'au']).
                  If None, includes all families.
    """
    with open(input_path) as f:
        data = json.load(f)

    catalog = data["catalog"]
    groups = catalog["groups"]

    elements = []

    for group in groups:
        fam_id = group["id"].upper()
        fam_title = group["title"]

        if families and group["id"] not in families:
            continue

        # Family-level element
        elements.append({
            "id": f"sp53-{fam_id}",
            "element_type": "family",
            "identifier": fam_id,
            "text": f"{fam_title} ({fam_id})",
            "parent_id": None,
            "metadata": {"level": "family"},
        })

        # Controls
        for ctrl in group.get("controls", []):
            ctrl_id = ctrl["id"].upper()
            ctrl_title = ctrl.get("title", ctrl_id)
            ctrl_prose = extract_prose(ctrl.get("parts", []))
            if not ctrl_prose:
                ctrl_prose = ctrl_title

            # Combine title and statement
            full_text = f"{ctrl_id} {ctrl_title}: {ctrl_prose}"

            elements.append({
                "id": f"sp53-{ctrl_id}",
                "element_type": "control",
                "identifier": ctrl_id,
                "text": full_text.strip(),
                "parent_id": f"sp53-{fam_id}",
                "metadata": {"level": "control", "family": fam_id},
            })

    output = {
        "document": {
            "id": "nist-sp800-53r5",
            "title": "NIST SP 800-53 Revision 5: Security and Privacy Controls",
            "short_name": "SP 800-53r5",
            "version": "5.1.1",
            "author": "National Institute of Standards and Technology",
            "url": "https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final",
            "date": "2020-09-23",
        },
        "elements": elements,
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    fams = sum(1 for e in elements if e["element_type"] == "family")
    ctrls = sum(1 for e in elements if e["element_type"] == "control")
    print(f"SP 800-53r5: {fams} families, {ctrls} controls -> {output_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Convert OSCAL catalogs to nist_strm format")
    parser.add_argument("--csf-input", default="/tmp/csf2_raw.json")
    parser.add_argument("--sp53-input", default="/tmp/sp800_53_raw.json")
    parser.add_argument("--output-dir", default="examples")
    parser.add_argument(
        "--sp53-families",
        nargs="*",
        default=None,
        help="SP 800-53 families to include (e.g. ac at au). Default: all",
    )
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if Path(args.csf_input).exists():
        convert_csf2(args.csf_input, str(out / "nist_csf2_elements.json"))
    else:
        print(f"CSF input not found: {args.csf_input}", file=sys.stderr)

    if Path(args.sp53_input).exists():
        convert_sp800_53(
            args.sp53_input,
            str(out / "nist_sp800_53_elements.json"),
            families=args.sp53_families,
        )
    else:
        print(f"SP 800-53 input not found: {args.sp53_input}", file=sys.stderr)
