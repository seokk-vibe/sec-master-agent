#!/usr/bin/env python3
"""Convert an Excel .xlsx workbook into per-sheet Markdown files.

This script avoids external dependencies by parsing XLSX XML files directly.
It is designed for interface/spec documents where each sheet should become
its own Markdown file.
"""

from __future__ import annotations

import argparse
import posixpath
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple
from xml.etree import ElementTree as ET


NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkgrel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

INVALID_FILENAME_CHARS = re.compile(r'[^0-9A-Za-z._\-가-힣]+')


@dataclass
class SheetData:
    name: str
    rows: List[List[str]]


def col_to_index(cell_ref: str) -> int:
    """Convert Excel cell ref to zero-based column index (e.g. 'B12' -> 1)."""
    letters = []
    for char in cell_ref:
        if char.isalpha():
            letters.append(char.upper())
        else:
            break

    if not letters:
        return 0

    value = 0
    for char in letters:
        value = value * 26 + (ord(char) - ord("A") + 1)
    return value - 1


def get_text_from_node(node: ET.Element) -> str:
    """Collect all text in a node (handles rich text runs)."""
    texts = []
    for text_node in node.findall(".//main:t", NS):
        texts.append(text_node.text or "")
    return "".join(texts)


def load_shared_strings(zf: zipfile.ZipFile) -> List[str]:
    """Load shared strings table if present."""
    try:
        with zf.open("xl/sharedStrings.xml") as f:
            root = ET.parse(f).getroot()
    except KeyError:
        return []

    shared = []
    for si in root.findall("main:si", NS):
        shared.append(get_text_from_node(si))
    return shared


def workbook_sheet_paths(zf: zipfile.ZipFile) -> List[Tuple[str, str]]:
    """Return (sheet_name, worksheet_xml_path) preserving workbook sheet order."""
    with zf.open("xl/workbook.xml") as f:
        wb_root = ET.parse(f).getroot()
    with zf.open("xl/_rels/workbook.xml.rels") as f:
        rel_root = ET.parse(f).getroot()

    rel_map: Dict[str, str] = {}
    for rel in rel_root.findall("pkgrel:Relationship", NS):
        rel_id = rel.attrib.get("Id", "")
        target = rel.attrib.get("Target", "")
        if rel_id and target:
            rel_map[rel_id] = target

    result: List[Tuple[str, str]] = []
    sheets_node = wb_root.find("main:sheets", NS)
    if sheets_node is None:
        return result

    for sheet in sheets_node.findall("main:sheet", NS):
        sheet_name = sheet.attrib.get("name", "sheet")
        rel_id = sheet.attrib.get(f"{{{NS['rel']}}}id")
        if not rel_id:
            continue

        target = rel_map.get(rel_id)
        if not target:
            continue

        worksheet_path = posixpath.normpath(posixpath.join("xl", target))
        result.append((sheet_name, worksheet_path))

    return result


def parse_sheet_rows(zf: zipfile.ZipFile, worksheet_path: str, shared_strings: List[str]) -> List[List[str]]:
    """Parse worksheet XML into row-major list of string cells."""
    with zf.open(worksheet_path) as f:
        root = ET.parse(f).getroot()

    sheet_data = root.find("main:sheetData", NS)
    if sheet_data is None:
        return []

    parsed_rows: List[List[str]] = []
    last_row_number = 0

    for row_node in sheet_data.findall("main:row", NS):
        row_num_raw = row_node.attrib.get("r")
        row_num = int(row_num_raw) if row_num_raw and row_num_raw.isdigit() else last_row_number + 1

        while len(parsed_rows) < row_num - 1:
            parsed_rows.append([])

        cell_map: Dict[int, str] = {}
        max_col = -1

        for cell in row_node.findall("main:c", NS):
            ref = cell.attrib.get("r", "")
            col_idx = col_to_index(ref)
            max_col = max(max_col, col_idx)

            cell_type = cell.attrib.get("t")
            value = ""

            if cell_type == "inlineStr":
                inline = cell.find("main:is", NS)
                value = get_text_from_node(inline) if inline is not None else ""
            elif cell_type == "s":
                v = cell.find("main:v", NS)
                if v is not None and v.text and v.text.isdigit():
                    idx = int(v.text)
                    if 0 <= idx < len(shared_strings):
                        value = shared_strings[idx]
            elif cell_type == "b":
                v = cell.find("main:v", NS)
                value = "TRUE" if (v is not None and v.text == "1") else "FALSE"
            else:
                v = cell.find("main:v", NS)
                value = v.text if (v is not None and v.text is not None) else ""

            cell_map[col_idx] = value

        if max_col < 0:
            parsed_rows.append([])
        else:
            row = [""] * (max_col + 1)
            for col_idx, value in cell_map.items():
                row[col_idx] = value
            parsed_rows.append(row)

        last_row_number = row_num

    return parsed_rows


def normalize_rows(rows: List[List[str]]) -> List[List[str]]:
    """Trim trailing empty cells and coerce values to stripped strings."""
    normalized = []
    for row in rows:
        values = [str(v).strip() if v is not None else "" for v in row]
        while values and not values[-1]:
            values.pop()
        normalized.append(values)
    return normalized


def split_blocks(rows: List[List[str]]) -> List[List[List[str]]]:
    """Split rows into blocks separated by empty rows."""
    blocks: List[List[List[str]]] = []
    current: List[List[str]] = []

    for row in rows:
        if not row or all(not cell for cell in row):
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(row)

    if current:
        blocks.append(current)
    return blocks


def is_json_like(text: str) -> bool:
    stripped = text.strip()
    return (stripped.startswith("{") and stripped.endswith("}")) or (
        stripped.startswith("[") and stripped.endswith("]")
    )


def sanitize_sheet_name(name: str, fallback: str) -> str:
    cleaned = INVALID_FILENAME_CHARS.sub("-", name).strip("-._")
    return cleaned or fallback


def escape_md_cell(value: str) -> str:
    return value.replace("|", r"\|").replace("\n", "<br>")


def block_to_markdown(block: List[List[str]]) -> str:
    """Convert one logical block to Markdown."""
    # Single-column block -> free text / JSON block
    if all(len(row) <= 1 for row in block):
        lines = [row[0] if row else "" for row in block]
        text = "\n".join(lines).strip()
        if not text:
            return ""
        if is_json_like(text):
            return f"```json\n{text}\n```"
        return text

    # Table-like block
    width = max(len(row) for row in block)
    rows = [row + [""] * (width - len(row)) for row in block]

    if len(rows) == 1:
        header = [f"column_{idx + 1}" for idx in range(width)]
        return "\n".join(
            [
                "| " + " | ".join(header) + " |",
                "| " + " | ".join("---" for _ in header) + " |",
                "| " + " | ".join(escape_md_cell(c) for c in rows[0]) + " |",
            ]
        )

    header = [cell if cell else f"column_{idx + 1}" for idx, cell in enumerate(rows[0])]
    body = rows[1:]

    lines = []
    lines.append("| " + " | ".join(escape_md_cell(c) for c in header) + " |")
    lines.append("| " + " | ".join("---" for _ in header) + " |")
    for row in body:
        lines.append("| " + " | ".join(escape_md_cell(c) for c in row) + " |")
    return "\n".join(lines)


def sheet_to_markdown(workbook_name: str, sheet: SheetData) -> str:
    rows = normalize_rows(sheet.rows)
    blocks = split_blocks(rows)

    sections = [f"# {workbook_name} - {sheet.name}"]
    for block in blocks:
        rendered = block_to_markdown(block)
        if rendered:
            sections.append(rendered)

    return "\n\n".join(sections).rstrip() + "\n"


def load_workbook(path: Path) -> List[SheetData]:
    with zipfile.ZipFile(path, "r") as zf:
        shared_strings = load_shared_strings(zf)
        sheets = workbook_sheet_paths(zf)
        result: List[SheetData] = []
        for sheet_name, xml_path in sheets:
            rows = parse_sheet_rows(zf, xml_path, shared_strings)
            result.append(SheetData(name=sheet_name, rows=rows))
        return result


def convert_workbook(input_path: Path, output_dir: Path, prefix: str) -> List[Path]:
    sheets = load_workbook(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    generated: List[Path] = []
    for idx, sheet in enumerate(sheets, start=1):
        safe_sheet = sanitize_sheet_name(sheet.name, fallback=f"sheet-{idx}")
        output_path = output_dir / f"{prefix}-{safe_sheet}.md"
        md = sheet_to_markdown(prefix, sheet)
        output_path.write_text(md, encoding="utf-8")
        generated.append(output_path)
    return generated


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert XLSX file(s) into per-sheet Markdown files."
    )
    parser.add_argument("input", type=Path, help="Path to .xlsx file or directory")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for generated Markdown files (default: input directory)",
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default=None,
        help="Output file prefix (default: input filename stem)",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path: Path = args.input
    if not input_path.exists():
        parser.error(f"Input file not found: {input_path}")

    if input_path.is_dir():
        workbook_paths = sorted(input_path.glob("*.xlsx"))
        if not workbook_paths:
            parser.error(f"No .xlsx files found in directory: {input_path}")
        default_output_dir = input_path
    else:
        if input_path.suffix.lower() != ".xlsx":
            parser.error("Only .xlsx is supported")
        workbook_paths = [input_path]
        default_output_dir = input_path.parent

    output_dir = args.output_dir if args.output_dir else default_output_dir

    all_generated: List[Path] = []
    for workbook in workbook_paths:
        prefix = args.prefix if args.prefix and len(workbook_paths) == 1 else workbook.stem
        try:
            generated = convert_workbook(workbook, output_dir, prefix)
            all_generated.extend(generated)
        except zipfile.BadZipFile:
            parser.error(f"Invalid XLSX file: {workbook}")
        except KeyError as exc:
            parser.error(f"Missing required XLSX entry in {workbook}: {exc}")

    print(f"Generated {len(all_generated)} Markdown file(s):")
    for path in all_generated:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
