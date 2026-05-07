# course_config_loader.py
# Author: Levester Williams
# 1 May 2026

"""Course configuration loading helpers.

This module reads the workbook that drives the reporting pipeline and
normalizes each usable row into a tuple containing the course name,
Canvas course ID, and destination Box folder ID.
"""

from pathlib import Path
from typing import List, Tuple

from openpyxl import load_workbook


def read_course_config_xlsx(path: str | Path) -> List[Tuple[str, str, str]]:
    """Read course configuration rows from an Excel workbook.

    Parameters
    ----------
    path : str or pathlib.Path
        Path to the course configuration workbook.

    Returns
    -------
    list of tuple of str
        Normalized rows in the form
        ``(course_name, course_id, box_folder_id)``.

    Notes
    -----
    Rows missing a course ID or Box folder ID are skipped.
    """
    workbook = load_workbook(filename=Path(path))
    worksheet = workbook.active

    rows: List[Tuple[str, str, str]] = []
    for index, row in enumerate(worksheet.iter_rows(min_row=2, values_only=True), start=2):
        course_name, course_id, box_folder_id = row

        if not course_id or not box_folder_id:
            print(f"Skipping row {index}: missing required fields")
            continue

        rows.append((
            str(course_name or "Unknown Course"),
            str(course_id),
            str(box_folder_id),
        ))

    return rows
