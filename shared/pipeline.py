# Author: Levester Williams
# 9 June 2025
# Platform info:
# - python 3.12.0

"""High-level orchestration for the Canvas to Box reporting pipeline."""

from __future__ import annotations

from datetime import datetime
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List
from zoneinfo import ZoneInfo

from shared.box_upload import download_file_from_box, upload_file_to_box
from shared.canvas_discussions import CanvasDiscussions
from shared.course_config_loader import read_course_config_xlsx, read_scheduled_run_dates

BOX_COURSE_CONFIG_FILE_ID = "123456789012"
BOX_SCHEDULE_FILE_ID = "234567890123"
RUN_TIME_ZONE = "America/New_York"


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
    3. a downloaded copy of the Box-hosted workbook in the temp directory
    """
    if config_path:
        return Path(config_path)

    env_path = os.getenv("COURSE_CONFIG_PATH")
    if env_path:
        return Path(env_path)

    temp_path = Path(tempfile.gettempdir()) / "canvas-discussion-reports" / "courses.xlsx"
    return download_file_from_box(BOX_COURSE_CONFIG_FILE_ID, temp_path)


def _resolve_schedule_config_path(schedule_path: str | None = None) -> Path | None:
    """Resolve the workbook path used to load scheduled run dates.

    Parameters
    ----------
    schedule_path : str or None, optional
        Explicit schedule workbook path supplied by the caller.

    Returns
    -------
    pathlib.Path or None
        Resolved path to the schedule workbook, or ``None`` when
        workbook-driven scheduling is disabled.

    Notes
    -----
    Resolution order is:

    1. ``schedule_path`` argument
    2. ``SCHEDULE_CONFIG_PATH`` environment variable
    3. a downloaded copy of the Box-hosted schedule workbook
    4. ``None`` when ``BOX_SCHEDULE_FILE_ID`` is blank
    """
    if schedule_path:
        return Path(schedule_path)

    env_path = os.getenv("SCHEDULE_CONFIG_PATH")
    if env_path:
        return Path(env_path)

    if not BOX_SCHEDULE_FILE_ID.strip():
        return None

    temp_path = Path(tempfile.gettempdir()) / "canvas-discussion-reports" / "schedule.xlsx"
    return download_file_from_box(BOX_SCHEDULE_FILE_ID, temp_path)


def run_course_reports(
    config_path: str | None = None,
    schedule_path: str | None = None,
) -> List[CourseRunResult]:
    """Run the full reporting job for every configured course.

    Parameters
    ----------
    config_path : str or None, optional
        Optional override for the course configuration workbook path.
    schedule_path : str or None, optional
        Optional override for the schedule workbook path.

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
    today = datetime.now(ZoneInfo(RUN_TIME_ZONE)).date()
    resolved_schedule_path = _resolve_schedule_config_path(schedule_path)

    if resolved_schedule_path is not None:
        scheduled_run_dates = read_scheduled_run_dates(resolved_schedule_path)
        if scheduled_run_dates and today not in scheduled_run_dates:
            logging.info(
                "Skipping report run on %s because it is not listed in %s.",
                today.isoformat(),
                resolved_schedule_path,
            )
            return []

    else:
        logging.info("No separate schedule workbook configured. Running on every Monday timer trigger.")

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
