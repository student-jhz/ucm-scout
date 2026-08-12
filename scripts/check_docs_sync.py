#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check structural consistency between the English and Chinese README.

English (README.en.md) is the primary / source-of-truth document. After
updating it, run this tool to find where the Chinese (README.md) has drifted:

  python scripts/check_docs_sync.py

The tool does NOT translate. It mechanically compares the parallel structure
(headings, ordered lists, table rows, code blocks) of both files. Sections or
items added/missing/misaligned in either language are reported so you can
manually translate and update the Chinese copy to keep it in full sync.

Files are configurable:
  python scripts/check_docs_sync.py --en README.en.md --zh README.md
"""
import argparse
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def is_blank(line):
    return not line.strip()


def parse_blocks(text):
    """Split markdown into structural blocks, stripping blank lines.

    Returns a list of block dicts:
      - {"type": "heading", "level": int}
      - {"type": "list", "ordered": bool, "count": int}       (one list = one block)
      - {"type": "table", "rows": int}                        (one table = one block)
      - {"type": "code", "lines": int}                        (one code fence = one block)
      - {"type": "para", "lines": int}                        (plain paragraph)
    """
    lines = text.splitlines()
    blocks = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if is_blank(line):
            i += 1
            continue
        # Heading
        m = re.match(r"^(\#{1,6})\s+", line)
        if m:
            blocks.append({"type": "heading", "level": len(m.group(1))})
            i += 1
            continue
        # Code fence
        if line.lstrip().startswith("```"):
            fence = line.lstrip()[:3]
            i += 1
            count = 0
            while i < n and not lines[i].lstrip().startswith(fence):
                count += 1
                i += 1
            i += 1  # skip closing fence
            blocks.append({"type": "code", "lines": count})
            continue
        # Table: starts with a header | ... | followed by a separator row
        if line.lstrip().startswith("|") and i + 1 < n and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            rows = 0
            while i < n and lines[i].lstrip().startswith("|"):
                rows += 1
                i += 1
            blocks.append({"type": "table", "rows": rows})  # includes header + separator
            continue
        # List (ordered or unordered). Consecutive list items = one block.
        if re.match(r"^\s*[-*]\s", line) or re.match(r"^\s*\d+\.\s", line):
            ordered = bool(re.match(r"^\s*\d+\.\s", line))
            count = 0
            while i < n and (re.match(r"^\s*[-*]\s", lines[i]) or re.match(r"^\s*\d+\.\s", lines[i])):
                if lines[i].strip():
                    count += 1
                i += 1
            blocks.append({"type": "list", "ordered": ordered, "count": count})
            continue
        # Blockquote (one block = consecutive quote lines)
        if line.lstrip().startswith(">"):
            qlines = 0
            while i < n and lines[i].lstrip().startswith(">"):
                qlines += 1
                i += 1
            blocks.append({"type": "quote", "lines": qlines})
            continue
        # Paragraph (could be several consecutive non-special lines)
        plines = 0
        while i < n and not is_blank(lines[i]):
            # stop at new structural markers that start on their own
            s = lines[i].lstrip()
            if (s.startswith(("#", "```", "|", ">", "- ", "* ")) or re.match(r"^\d+\.\s", s) or s.startswith("--")):
                break
            plines += 1
            i += 1
        blocks.append({"type": "para", "lines": plines})
    return blocks


# ---------------------------------------------------------------------------
# Structure key for comparison
# ---------------------------------------------------------------------------

def structure_key(blocks):
    """Return a flat list of comparison tokens for a doc.

    Headings carry their level (these are the alignment anchor, matched by
    order + level). Everything else is summarized by type+dimension only, so
    the comparator reports *how many* items differ without needing to translate.
    """
    key = []
    for b in blocks:
        if b["type"] == "heading":
            key.append(("H", b["level"]))
        elif b["type"] == "list":
            key.append(("L", b["count"]))
        elif b["type"] == "table":
            key.append(("T", b["rows"]))
        elif b["type"] == "code":
            key.append(("C", b["lines"]))
        elif b["type"] in ("para", "quote"):
            key.append(("P", b["lines"]))
        else:
            key.append(("?", 0))
    return key


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

def _term_name(kind):
    return {"H": "章节", "L": "列表", "T": "表格", "C": "代码块", "P": "段落/引用"}[kind]


def _compare_chunk(en_key, e0, zh_key, z0, e1, z1, out, ctx):
    """Compare the flat token slice [e0:e1) vs [z0:z1) (no headings inside)."""
    en_chunk = en_key[e0:e1]
    zh_chunk = zh_key[z0:z1]

    def nons(k):
        return [t for t in k if t[0] in ("L", "T", "C", "P")]

    en_n, zh_n = nons(en_chunk), nons(zh_chunk)

    # same-kind block counts
    en_dims = {t[0]: 0 for t in en_chunk}
    zh_dims = {t[0]: 0 for t in zh_chunk}
    for t in en_chunk:
        if t[0] in ("L", "T", "C", "P"):
            en_dims[t[0]] = en_dims.get(t[0], 0) + 1
    for t in zh_chunk:
        if t[0] in ("L", "T", "C", "P"):
            zh_dims[t[0]] = zh_dims.get(t[0], 0) + 1

    for kind in ("L", "T", "C", "P"):
        ev, zv = en_dims.get(kind, 0), zh_dims.get(kind, 0)
        if ev != zv:
            out.append(f"  {ctx}: {_term_name(kind)}数量不一致 (EN={ev} 项, ZH={zv} 项)")

    # pairwise counts for same-type blocks (position-based)
    for kind in ("L", "T", "C", "P"):
        en_vals = [t[1] for t in en_n if t[0] == kind]
        zh_vals = [t[1] for t in zh_n if t[0] == kind]
        count = min(len(en_vals), len(zh_vals))
        for j in range(count):
            if en_vals[j] != zh_vals[j]:
                out.append(f"  {ctx}: 第{j+1}个{_term_name(kind)}规模不一致 (EN size={en_vals[j]}, ZH size={zh_vals[j]})")


def diff_tokens(en_key, zh_key):
    """Align the two docs on heading sequences (by order + level) and compare
    the content between aligned headings. Headings are the only anchor (they
    appear in parallel order in both languages); everything else is compared
    by type/dimension counts, not by translated text."""
    out = []

    en_h = [i for i, t in enumerate(en_key) if t[0] == "H"]
    zh_h = [i for i, t in enumerate(zh_key) if t[0] == "H"]

    # heading structure signature = list of levels
    en_shape = [en_key[i][1] for i in en_h]
    zh_shape = [zh_key[i][1] for i in zh_h]

    if en_shape != zh_shape:
        out.append("章节结构不一致（两个文档的标题层级/顺序不同）：")
        out.append(f"    EN 章节层级: {en_shape}")
        out.append(f"    ZH 章节层级: {zh_shape}")

    # compare content section by section using min length to stay aligned
    common = min(len(en_h), len(zh_h))
    for k in range(common):
        e_start, e_end = en_h[k], (en_h[k + 1] if k + 1 < len(en_h) else len(en_key))
        z_start, z_end = zh_h[k], (zh_h[k + 1] if k + 1 < len(zh_h) else len(zh_key))
        # skip the heading token itself
        _compare_chunk(en_key, e_start + 1, zh_key, z_start + 1, e_end, z_end, out,
                       f"章节#{k + 1}")

    # leftover headings (only if shapes differ)
    if len(en_h) > len(zh_h):
        for k in range(common, len(en_h)):
            out.append(f"  [EN 新增] 中文缺少章节 #{k + 1}")
    elif len(zh_h) > len(en_h):
        for k in range(common, len(zh_h)):
            out.append(f"  [中文多余] 英文缺少章节 #{k + 1}")

    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Check EN/ZH README structural consistency.")
    ap.add_argument("--en", default="README.en.md", help="primary (English) doc")
    ap.add_argument("--zh", default="README.md", help="translated (Chinese) doc")
    ap.add_argument("--report", default="", help="also write a UTF-8 report file (e.g. sync_report.txt)")
    args = ap.parse_args()

    en_path, zh_path = Path(args.en), Path(args.zh)
    if not en_path.exists() or not zh_path.exists():
        print("missing file; ensure both --en and --zh exist")
        return 1

    en_blocks = parse_blocks(en_path.read_text(encoding="utf-8"))
    zh_blocks = parse_blocks(zh_path.read_text(encoding="utf-8"))
    en_key = structure_key(en_blocks)
    zh_key = structure_key(zh_blocks)

    issues = diff_tokens(en_key, zh_key)

    # heading count summary
    en_h = sum(1 for b in en_blocks if b["type"] == "heading")
    zh_h = sum(1 for b in zh_blocks if b["type"] == "heading")

    lines = []
    lines.append(f"英文(主文档)结构块: {len(en_blocks)}, 标题数: {en_h}")
    lines.append(f"中文(待同步) 结构块: {len(zh_blocks)}, 标题数: {zh_h}")
    lines.append("-" * 60)
    if not issues:
        lines.append("一致性检查通过：两份文档结构完全对齐。")
        lines.append("（仅代表结构同步；正文措辞请人工核对翻译质量。）")
    else:
        lines.append("发现以下结构差异（请对照英文人工翻译更新中文）：")
        for it in issues:
            lines.append("  " + it if it.startswith(" ") else "  " + it)
        lines.append("-" * 60)
        lines.append("提示：以上只反映『结构/数量』层面的差异。真正的翻译与语义")
        lines.append("一致性仍需人工校对，本工具用于防止遗漏、定位已过时片段。")

    text = "\n".join(lines)
    for ln in lines:
        print(ln)
    if args.report:
        Path(args.report).write_text(text + "\n", encoding="utf-8")
        print(f"(报告已写入: {args.report})")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
