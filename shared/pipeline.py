# Author: Levester Williams
# 9 June 2025
#
# Platform info:
# - python 3.12.0

"""High-level orchestration for the Canvas to Box reporting pipeline."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

from shared.box_upload import upload_file_to_box
from shared.canvas_discussions import CanvasDiscussions
from shared.course_config_loader import read_course_config_xlsx


@dataclass
class CourseRunResult:
    """Summary of a single course reporting run.

    Attributes
    ----------
    course_name : str
        Human-readable course name from the configuration workbook.
    course_id : str
        Canvas course identifier used for API requests.
    box_folder_id : str
        Box folder identifier targeted for upload.
    output_path : str or None
        Local path of the generated workbook when one was created.
    uploaded_box_file_id : str or None
        Box file ID for the uploaded workbook when upload succeeded.
    """

    course_name: str
    course_id: str
    box_folder_id: str
    output_path: str | None
    uploaded_box_file_id: str | None


def _resolve_course_config_path(config_path: str | None = None) -> Path:
    """Resolve the workbook path used to load course configuration.

    Parameters
    ----------
    config_path : str or None, optional
        Explicit workbook path supplied by the caller.

    Returns
    -------
    pathlib.Path
        Resolved path to the configuration workbook.

    Notes
    -----
    Resolution order is:

    1. ``config_path`` argument
    2. ``COURSE_CONFIG_PATH`` environment variable
    3. ``courses.xlsx`` in the function app root
    """
    if config_path:
        return Path(config_path)

    env_path = os.getenv("COURSE_CONFIG_PATH")
    if env_path:
        return Path(env_path)

    return Path(__file__).resolve().parent.parent / "courses.xlsx"


def run_course_reports(config_path: str | None = None) -> List[CourseRunResult]:
    """Run the full reporting job for every configured course.

    Parameters
    ----------
    config_path : str or None, optional
        Optional override for the course configuration workbook path.

    Returns
    -------
    list of CourseRunResult
        Per-course results for reports that were generated and uploaded.

    Notes
    -----
    The workflow for each course is:

    - load enrollees from Canvas
    - build discussion participation data
    - generate an Excel workbook
    - upload the workbook to Box
    """
    resolved_config_path = _resolve_course_config_path(config_path)
    course_rows = read_course_config_xlsx(resolved_config_path)

    if not course_rows:
        logging.warning("No valid course rows found in %s.", resolved_config_path)
        return []

    results: List[CourseRunResult] = []
    for course_name, course_id, box_folder_id in course_rows:
        logging.info("Processing course %s (%s).", course_name, course_id)

        canvas = CanvasDiscussions("LPS_Production", "Student", course_id)
        canvas.course_name = course_name

        course_enrollees = canvas.get_enrollees(course_id)
        if canvas.get_enrollment_type() != "StudentEnrollment":
            if canvas.get_enrollment_type() == "TaEnrollment":
                canvas.set_enrollment_type("Teacher")
            else:
                canvas.set_enrollment_type("TA")
            course_enrollees += canvas.get_enrollees(course_id)

        if not course_enrollees:
            logging.warning("No enrollees found for %s.", course_name)
            continue

        data, _ = canvas.get_course_discussion_data(course_id, course_enrollees)
        if not data:
            logging.warning("No discussion data found for %s.", course_name)
            continue

        xlsx_path = canvas.write_module_breakdown_xlsx(data)
        uploaded_box_file_id = upload_file_to_box(xlsx_path, box_folder_id)

        results.append(
            CourseRunResult(
                course_name=course_name,
                course_id=course_id,
                box_folder_id=box_folder_id,
                output_path=str(xlsx_path),
                uploaded_box_file_id=uploaded_box_file_id,
            )
        )

        logging.info(
            "Uploaded report for %s to Box folder %s as file %s.",
            course_name,
            box_folder_id,
            uploaded_box_file_id,
        )

    return results
