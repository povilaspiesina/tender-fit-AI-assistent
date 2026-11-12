"""Build a private token vocabulary from the client's catalog product names.

Reads only product-name columns. Prices, SKUs and rows are never written.
Usage: python scripts/build_catalog_vocab.py <catalog_dir> <output_json>
"""

import collections
import json
import re
import sys
from pathlib import Path

import openpyxl

# Header names that hold product names or product categories in the supplier price lists.
# Matched in every workbook; prices, SKUs and other columns are never read.
NAME_HEADERS = ["Name", "Category", "PRODUCT NAME", "PRODUCT TYPE", "ProductName", "Productgroup",
                "Item Description - Long", "Product Group", "Product Name Part 1", "UNSPSC Code Description",
                "Product Name", "Article", "Sample", "Product Title", "Cat. Name", "Product Description"]
TOKEN = re.compile(r"[a-ząčęėįšųūž][a-ząčęėįšųūž0-9\-]{2,}")


def main(catalog_dir: Path, output: Path) -> None:
    doc_freq = collections.Counter()
    columns = NAME_HEADERS
    for path in sorted(catalog_dir.glob("*.xlsx")):
        if path.name.startswith("~$"):
            continue
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        for sheet in workbook.worksheets:
            rows = sheet.iter_rows(values_only=True)
            header = None
            for row in rows:
                cells = [str(c).strip() if c is not None else "" for c in row]
                if any(c in cells for c in columns):
                    header = cells
                    break
            if header is None:
                continue
            idx = [header.index(c) for c in columns if c in header]
            for row in rows:
                text = " ".join(str(row[i]) for i in idx if i < len(row) and row[i] is not None).lower()
                tokens = set(TOKEN.findall(text))
                doc_freq.update(tokens)
    vocab = {t: n for t, n in doc_freq.items() if n >= 3 and not t.isdigit()}
    output.write_text(json.dumps({"token_doc_freq": vocab}, ensure_ascii=False), encoding="utf-8")
    print("tokens", len(vocab))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
