import csv
import requests
import json
from json import JSONDecodeError
from pathlib import Path
import sys


class Canvas:
    def __init__(self, instance):
        self.instance = instance

    def get_token(self=None):
        try:
            # In later updates, may need to provide alternatives for user to
            # type in path another credentials file if error occurs
            with (open(r'\Users\Levester\Desktop\cred.json') as f):
                cred = json.load(f)
        except FileNotFoundError:
            print(f"The credentials file cred.json was not found.")
            sys.exit(1)
        except JSONDecodeError:
            print(f"The credentials file cred.json contains invalid JSON.")
            sys.exit(1)
        return cred

    server_url = {'LPS_Production': 'https://canvas.upenn.edu/', 'LPS_Test':
        'https://upenn.test.instructure.com/'}

    def headers(self):
        token = self.get_token()
        headers = {'Content-Type': 'application/json',
                   'Authorization': 'Bearer {}'.format(
                       token[f'{self.instance}'])}
        return headers

    # Retrieve students and test to see if the correct JSON object has been retrieved
    def get_students(self, course_id):
        # Fetch students enrolled in the course
        students_url = f'{self.server_url["LPS_Test"]}api/v1/courses/{course_id}/users?enrollemnt_type=student'
        response = requests.get(students_url, headers=self.headers())

        # Error catching and handling for JSON
        if response.status_code != 200:
            raise Exception(f'{response.status_code},{response.text}')

        try:
            students = response.json()
        except json.JSONDecodeError:
            print("Failed to decode data from response")


        # Debugging statements
        print("Course ID:", course_id)
        print("Response status:", response.status_code)
        print("Response text:", response.text[:500])
        print("Processed students data:", students)
        print(type(students))
        for student in students:
            print(type(student))
            print(student['name'])

        if isinstance(students, list) and all(
                isinstance(students, dict) for student in students):
            return {student['id']: student['name'] for student in students}
        else:
            print("Error: Unexpected API response format")
            print("In get_student()")
            return {}

    def get_course_discussion_data(self, course_id):
        student_discussion_data = {}
        page_url = f'{self.server_url[self.instance]}api/v1/courses/{course_id}/discussion_topics?per_page=100'

        # Debug page_url
        print("Page URL:", page_url)

        while page_url:
            response = requests.get(page_url, headers=self.headers())
            print("Response status:", response.status_code)

            # Check if the response status code is OK
            if response.status_code != 200:
                raise Exception(f'{response.status_code},{response.text}')

            try:
                discussion_topics = response.json()
            except json.JSONDecodeError:
                print("Failed to decode JSON from response")
                break

            print("Discussion topics:", discussion_topics)

            for topic in discussion_topics:
                topic_title = topic.get('title', 'Unknown Title')
                self.process_discussion_topic(topic, course_id,
                                              student_discussion_data)

            page_url = self.get_next_page_url(response.headers.get('Link'))

        return student_discussion_data

    def process_discussion_topic(self, topic, course_id,
                                 student_discussion_data):
        discussion_posts_url = f'{self.server_url[self.instance]}api/v1/courses/{course_id}/discussion_topics/{topic["id"]}/posts'
        response = requests.get(discussion_posts_url, headers=self.headers())

        if response.status_code != 200:
            print(f"Error fetching discussion posts: {response.status_code}")
            return

        try:
            discussion_posts = response.json()
        except json.JSONDecodeError:
            print("Failed to decode JSON from discussion posts response")
            return

        for discussion_post in discussion_posts:
            student_id = discussion_post.get('author_id')
            if student_id:
                if student_id not in student_discussion_data:
                    student_discussion_data[student_id] = {}
                if discussion_post.get('parent_id') is None:  # Original post
                    student_discussion_data[student_id][
                        f'{topic["title"]} - Original Post'] = True
                else:  # Reply
                    student_discussion_data[student_id][
                        f'{topic["title"]} - Replies'] = True

    def get_next_page_url(self, link_header):
        if link_header:
            links = link_header.split(',')
            for link in links:
                if 'rel="next"' in link:
                    next_link = link.split(';')[0].strip('<> ')
                    return next_link
        return None

    def write_discussion_data_to_csv(self, student_discussion_data):
        # Return without outputting a csv file if no students are found in course
        if not student_discussion_data:
            print("No student discussion data")
            return
        # Determine the path to the user's download folder
        download_folder = Path.home() / 'Downloads'
        print(download_folder)
        if not download_folder.exists():
            download_folder.mkdir()
            print(f"Created folder: {download_folder}")

        output_file_path = download_folder / 'discusssion_data.csv'

        with open(output_file_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)

            headers = ['Student\'s Name'] + [f"{topic} - Original Post" for
                                             topic in next(iter(
                    student_discussion_data.values()), {}).keys()] + [
                          f"{topic} - Replies" for topic in next(iter(
                    student_discussion_data.values()), {}).keys()]

            writer.writerow(headers)

            for student_name, topics in student_discussion_data.items():
                row = [student_name] + list(topics.values())
                writer.writerow(row)

        print(f"CSV file written to {output_file_path}")

    # Retrieve course name
    def get_course_name(self, course_id):
        course_url = f'{self.server_url[self.instance]}api/v1/courses/{course_id}'
        print(f"Getting course name: {course_url}")
        response = requests.get(course_url, headers=self.headers())
        course = response.json()
        return course.get('name', 'Unknown Course')


def main(course_num):
    #Debugging statements
    course_name = canvas.get_course_name(course_num)
    print(f"Course Name: {course_name}")
    canvas.get_students(course_num)

    # Get the discussion data for the course
    student_discussion_data = canvas.get_course_discussion_data(course_num)

    # Write the discussion data to a CSV file
    canvas.write_discussion_data_to_csv(student_discussion_data)


if __name__ == '__main__':
    canvas = Canvas('LPS_Test')
    course_number = '1748632'
    main(course_number)