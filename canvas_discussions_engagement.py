#
# Levester Williams
# 31 August 2023
#
# Platform info:
# - python 3.11.0
#

import csv
import requests
import json
import sys
import os
from json import JSONDecodeError
from pathlib import Path
from json_freader import JSONfreader


class Canvas:
    """This class reads data from a Canvas discussion engagements and prints
    the data in a CSV format.

    Attributes:
    -----------
    server_url : dict
        A dictionary that contains information about the server url.

    Methods:
    --------
    get_token():
        Retrieves the API token.


    """
    server_url = {'LPS_Production': 'https://canvas.upenn.edu/', 'LPS_Test':
        'https://upenn.test.instructure.com/'}

    def __init__(self, instance):
        """Initializes the class with the server URL."""
        self.instance = instance

    def get_token(self=None) -> dict:
        """Gets the API token from either an environment variable or a json
        file.

        Parameters:
        -----------
            self : none

        Returns:
        --------
            dict : An API token.
        """
        environ_var = True
        if environ_var:
            return self.get_cred_env_var()
        return self.get_cred_json()

    def get_cred_json(self=None) -> dict:
        """
        Retrieves an API token from a json file.

        Parameters:
        -----------
        self : none

        Returns:
        --------
        dict : An API token from either an environment variable or a json file.
        """
        reader = JSONfreader()
        # have to inquire how the cred should be stored and if team has
        # access to a secret manager
        json_file_path = ""
        try:
            cred = reader.load_json_file(json_file_path)
        except FileNotFoundError as e:
            print(f"The credentials file cred.json was not found")
            # Must consult with others about whether the client should have
            # the ability to manually input the filepath to credential
            sys.exit(1)
        except RuntimeError:
            print(f"The credentials file cred.json contains invalid JSON.")
            sys.exit(1)
        except Exception as e:
            print(f"Unexpected error: {e}")
            sys.exit(1)
        return cred

    def get_cred_env_var(self=None) -> dict:
        """Gets the API token from an environment variable.

        Parameters:
        -----------
        self : none

        Returns:
        --------
        dict : An API token.
        """
        try:
            cred = json.loads(os.getenv('CANVAS_API_CRED'))
        except AttributeError:
            print(f"Environment variable CANVAS_API_CRED does not exist")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"The credentials file cred.json contains invalid JSON.")
            sys.exit(1)
        except TypeError:
            print("Invalid type: expected a JSON string.")
            sys.exit(1)
        except Exception as e:
            print(f"Unexpected error: {e}")
            sys.exit(1)
        return cred

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
        except JSONDecodeError:
            print("Failed to decode data from response")
            sys.exit(1)

        # Debugging statements
        print("Course ID:", course_id)
        print("Processed students data:", students)
        print(type(students))
        for student in students:
            print(type(student))
            print(student['name'])

        if isinstance(students, list) and all(
                isinstance(student, dict) for student in students):
            # need to return a list of dicts with name
            return {student['name'] for student in students}
        else:
            print("Error: Unexpected API response format")
            sys.exit(1)

    def get_course_discussion_data(self, course_id):
        student_discussion_data = {}
        page_url = f'{self.server_url[self.instance]}api/v1/courses/{course_id}/discussion_topics?per_page=100'

        # Debug page_url
        print("Page URL:", page_url)

        while page_url:
            response = requests.get(page_url, headers=self.headers())
            if response.status_code != 200:
                raise Exception(f'{response.status_code},{response.text}')

            try:
                discussion_topics = response.json()
            except JSONDecodeError:
                print("Failed to decode JSON from response")
                sys.exit(1)

            print("Discussion topics:", discussion_topics)
            list_topic_titles = []
            for topic in discussion_topics:
                topic_title = topic.get('title', 'Unknown Title')
                topic_id = topic.get('id', 'Unknown')
                print(f"Topic title is: {topic_title}")
                original_topic_title = self.process_discussion_topic(topic,
                                                                     course_id,
                                                                     student_discussion_data)
                replies_topic_titles = self.process_full_topic_view(course_id,
                                                                    topic_id,
                                                                    student_discussion_data,
                                                                    topic_title)
                # Appends titles to list
                if original_topic_title:
                    list_topic_titles.append(original_topic_title[0])
                if replies_topic_titles:
                    list_topic_titles.extend(replies_topic_titles)
            page_url = self.get_next_page_url(response.headers.get('Link'))

        print(f"Student discussion is {student_discussion_data}")
        print(f"Topic titles are {list_topic_titles}")
        return student_discussion_data, list_topic_titles

    def get_full_topic_view(self, course_id, topic_id):
        full_topic_view_url = f'{self.server_url[self.instance]}/api/v1/courses/{course_id}/discussion_topics/{topic_id}/view'
        response = requests.get(full_topic_view_url, headers=self.headers())
        if response.status_code == 200:
            try:
                full_topic_view = response.json()
                return full_topic_view
            except JSONDecodeError:
                print("Failed to decode JSON from response")
                sys.exit(1)
        elif response.status_code == 403:
            # skip over as topic requires user to have posted
            return None
        # NOTE: may need to handle 503 error if the cached structure is not yet
        # ready and prompt the caller to try again or sleep and wait and call
        # again
        else:
            print(
                f"Error fetching full topic view: {response.status_code}, {response.text}")
            return None

    def process_full_topic_view(self, course_id, topic_id,
                                student_discussion_data, topic_title):
        topic_view = self.get_full_topic_view(course_id, topic_id)
        if not topic_view:
            return []
        list_topic_titles = []
        # student_discussion_data' is structured as
        # {student_id: {topic_title: True/False for replies}}
        for entry in topic_view.get('participants', []):  # Iterate through all
            # entries
            student_name = entry.get('display_name')
            print(f"{student_name} - {topic_title}")
            if student_name not in student_discussion_data:
                student_discussion_data[student_name] = {}
            else:
                # Mark student as having replied to the topic
                topic_replies_title = f"{topic_title} - Replies"
                if topic_title not in list_topic_titles:
                    list_topic_titles.append(topic_replies_title)
                student_discussion_data[student_name][
                    topic_replies_title] = True
        print(f'Topic replies in full_view is{list_topic_titles}')
        return list_topic_titles

    def process_discussion_topic(self, topic, course_id,
                                 student_discussion_data):
        discussion_post_url = f'{self.server_url[self.instance]}api/v1/courses/{course_id}/discussion_topics/{topic["id"]}'
        response = requests.get(discussion_post_url, headers=self.headers())
        if response.status_code != 200:
            print(f"Error fetching discussion posts: {response.status_code}")
            return []

        try:
            discussion_post = response.json()
        except json.JSONDecodeError:
            print("Failed to decode JSON from discussion posts response")
            sys.exit(1)

        list_topic_titles = []

        print(f"Discussion post is: {discussion_post}")
        student_name = discussion_post.get('user_name')
        print(f"Author Name: {student_name}")
        print(f"student discussion data is: {type(student_discussion_data)}")
        if student_name:
            if student_name not in student_discussion_data:
                student_discussion_data[student_name] = {}
            if discussion_post.get('parent_id') is None:  # Original post
                topic_title = f'{topic["title"]} - Original Post'
                student_discussion_data[student_name][
                    topic_title] = True
                list_topic_titles.append(topic_title)
                print(f'New topic title is {topic_title}')
        return list_topic_titles

    def get_next_page_url(self, link_header):
        if link_header:
            links = link_header.split(',')
            for link in links:
                if 'rel="next"' in link:
                    next_link = link.split(';')[0].strip('<> ')
                    return next_link
        return None

    def write_discussion_data_to_csv(self, student_discussion_data,
                                     discussion_topics):
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

        discussion_titles = list(set(discussion_topics))

        headers = ['Student Name']
        for topic_title in discussion_titles:
            headers.append(topic_title)
            # debugging statement
        print(f'Header titles: {headers}')

        with (open(output_file_path, 'w', newline='') as csvfile):
            writer = csv.writer(csvfile)
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
    # Debugging statements
    course_name = canvas.get_course_name(course_num)
    print(f"Course Name: {course_name}")

    # Return a set of student names
    students_in_course = canvas.get_students(course_num)
    if len(students_in_course) == 0:
        print("No students are listed in the course for Canvas.")
        sys.exit(1)

    # Get the discussion data for the course
    student_discussion_tuple = canvas.get_course_discussion_data(course_num)

    # Write the discussion data to a CSV file
    canvas.write_discussion_data_to_csv(student_discussion_tuple[0],
                                        student_discussion_tuple[1])


if __name__ == '__main__':
    canvas = Canvas('LPS_Test')
    course_number = '1748632'
    main(course_number)
