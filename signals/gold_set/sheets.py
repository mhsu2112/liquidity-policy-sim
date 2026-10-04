"""Build the two labelers' Excel files (session M2.3; Clarifications 19 and 24).

Each file has a Practice tab and a Main tab, in the same order for both labelers. Each row shows
only a neutral ID (PR01..., G001...) and the passage text: no source, date, link, period or type
(Clarification 19). The labeler fills three shaded columns: Answer (dropdown 1, 2, 3, 4, N),
Unsure (dropdown Y) and Note. The files' author, company and title properties are left blank.

Output: signals/gold_set/sheets/gold_set_L1.xlsx and gold_set_L2.xlsx (git-ignored).
Run: python -m signals.gold_set.sheets   (or: make gold-sheets)
"""

import csv
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from signals.corpus.build_corpus import PRIVATE_PATH
from signals.gold_set.draw import KEY_PATH

HERE = Path(__file__).resolve().parent
SHEET_DIR = HERE / "sheets"
COLUMNS = ["ID", "Passage", "Answer", "Unsure", "Note"]
FILL_IN = PatternFill("solid", fgColor="DDEBF7")     # light blue: the columns the labeler fills


def load_rounds():
    """{'practice': [(gold_id, text)], 'main': [...]} in key order (the drawn order)."""
    with open(PRIVATE_PATH, newline="") as f:
        text = {r["id"]: r["passage"] for r in csv.DictReader(f)}
    rounds = {"practice": [], "main": []}
    with open(KEY_PATH, newline="") as f:
        for k in csv.DictReader(f):
            rounds[k["round"]].append((k["gold_id"], text[k["corpus_id"]]))
    return rounds


def _tab(ws, items):
    ws.append(COLUMNS)
    for gold_id, passage in items:
        ws.append([gold_id, passage, None, None, None])
    n = len(items) + 1
    answer = DataValidation(type="list", formula1='"1,2,3,4,N"', allow_blank=True, showErrorMessage=True,
                            errorTitle="Answer", error="Choose 1, 2, 3, 4 or N.")
    unsure = DataValidation(type="list", formula1='"Y"', allow_blank=True, showErrorMessage=True,
                            errorTitle="Unsure", error="Enter Y, or leave blank.")
    for dv, col in ((answer, "C"), (unsure, "D")):
        ws.add_data_validation(dv)
        dv.add(f"{col}2:{col}{n}")
    for width, col in zip([8, 100, 9, 9, 30], "ABCDE"):
        ws.column_dimensions[col].width = width
    for row in ws.iter_rows(min_row=1, max_row=n):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            if cell.row > 1 and cell.column_letter in "CDE":
                cell.fill = FILL_IN
    for cell in ws[1]:
        cell.font = Font(bold=True)
    ws.freeze_panes = "A2"


def build(path, rounds):
    wb = Workbook()
    ws = wb.active
    ws.title = "Practice"
    _tab(ws, rounds["practice"])
    _tab(wb.create_sheet("Main"), rounds["main"])
    p = wb.properties                     # nothing that identifies who made the file
    p.creator = p.lastModifiedBy = p.title = p.subject = p.description = p.keywords = p.category = ""
    wb.save(path)


def run():
    SHEET_DIR.mkdir(exist_ok=True)
    rounds = load_rounds()
    for labeler in ("L1", "L2"):
        build(SHEET_DIR / f"gold_set_{labeler}.xlsx", rounds)
    print(f"wrote {SHEET_DIR}/gold_set_L1.xlsx and gold_set_L2.xlsx "
          f"(practice {len(rounds['practice'])}, main {len(rounds['main'])})")


if __name__ == "__main__":
    run()
