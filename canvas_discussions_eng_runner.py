#
# Levester Williams
# 9 June 2025
#
# Platform info:
# - python 3.12.0

from canvas_discussions_engagement import CanvasDiscussions
import course_config_loader
import box_upload


def main() -> None:
    config_path = "courses.xlsx"

    course_rows = course_config_loader.read_course_config_xlsx(config_path)

    if not course_rows:
        print("No valid course rows found.")
        return

    for course_name, course_id, box_folder_id in course_rows:
        print(f"\nProcessing: {course_name} ({course_id})")

        canvas = CanvasDiscussions('LPS_Production', 'Student', course_id)
        canvas.course_name = course_name  # override instead of API call

        course_enrollees = canvas.get_enrollees(course_id)

        if canvas.get_enrollment_type() != 'StudentEnrollment':
            if canvas.get_enrollment_type() == 'TaEnrollment':
                canvas.set_enrollment_type('Teacher')
            else:
                canvas.set_enrollment_type('TA')
            course_enrollees += canvas.get_enrollees(course_id)

        if not course_enrollees:
            print(f"No enrollees for {course_name}")
            continue

        data, _ = canvas.get_course_discussion_data(course_id, course_enrollees)

        if not data:
            print(f"No discussion data for {course_name}")
            continue

        # write file
        xlsx_path = canvas.write_module_breakdown_xlsx(data)

        # upload using row-specific folder
        box_upload.upload_file_to_box(str(xlsx_path), box_folder_id)

if __name__ == '__main__':
    main()

