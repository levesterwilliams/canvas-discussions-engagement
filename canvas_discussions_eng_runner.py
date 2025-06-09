#
# Levester Williams
# 9 June 2025
#
# Platform info:
# - python 3.12.0

from canvas_discussions_engagement import CanvasDiscussions

def main() -> None:
    course_num_list = ["1849493"]
    for course_num in course_num_list:
        canvas = CanvasDiscussions('LPS_Production', 'Student', course_num)
        canvas.set_course_name(course_num)
        print(f"Course Name: {canvas.course_name}")
        course_enrollees = canvas.get_enrollees(course_num)
        if canvas.get_enrollment_type() != 'StudentEnrollment':
            if canvas.get_enrollment_type() == 'TaEnrollment':
                canvas.set_enrollment_type('Teacher')
            else:
                canvas.set_enrollment_type('TA')
            course_enrollees_addt = canvas.get_enrollees(course_num)
            course_enrollees = course_enrollees + course_enrollees_addt
        if len(course_enrollees) > 0:
            enrollee_discussion_tuple = canvas.get_course_discussion_data(
                course_num, course_enrollees)
            if enrollee_discussion_tuple[0] and enrollee_discussion_tuple[1]:
                canvas.write_discussion_data_to_csv(
                    enrollee_discussion_tuple[0],
                    enrollee_discussion_tuple[1])
                return None
        print(f"No CSV written for {canvas.course_name}")
        return None

if __name__ == '__main__':
    main()

