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
import time
from json import JSONDecodeError
from pathlib import Path
from json_freader import JSONfreader
from collections import OrderedDict


class Canvas:
    """This class reads data from a course's Canvas discussion engagements and
    prints the data in a CSV format.

    Attributes:
    -----------
    server_url : dict
        A dictionary that contains information about the server url.

    Methods:
    --------
    get_server_url():
        Retrieves the server url.

    get_token():
        Retrieves the API token.

    get_cred_json():
        Retrieves an API token from a json file.

    get_cred_env_var():
        Retrieves an API token from an environment variable.

    headers():
        Generates HTTP headers.

    get_enrollees():
        Gets enrollees enrolled in the course.

    set_enrollment_type():
        Sets the Enrollment type

    get_next_page_url():
        Gets the next page URI for the discussion page.

    get_course_discussion_data():
        Gets the discussion data for the given course.

    get_full_topic_view():
        Gets the full topic for each discussion topic.

    process_full_topic_view():
        Stores what discussion topic students replied to.

    write_discussion_data_to_csv():
        Writes student participation of each discussion to a CSV file.

    get_course_name():
        Returns the name of the course.
    """
    server_url = {'LPS_Production': 'https://canvas.upenn.edu/', 'LPS_Test':
        'https://upenn.test.instructure.com/'}

    enrollment_type = {'Student': 'StudentEnrollment', 'TA': 'TaEnrollment',
                       'Teacher': 'TeacherEnrollment'}

    def __init__(self, server_type: str, enrollment: str) -> None:
        """Initializes the class with the server type."""
        self.server_type = server_type
        self.enrollment = enrollment

    def get_server_url(self=None) -> str:
        """Returns the server url.

        Returns
        -------
        str : A string representing the server url.
        """
        return self.server_url[self.server_type]

    def get_enrollment_type(self=None) -> str:
        """Returns the Enrollment type.

        Returns
        -------
        str : A string representing the Enrollment type.
        """
        return self.enrollment_type[self.enrollment]

    def set_enrollment_type(self, enrollment_type: str) -> str:
        """Sets the Enrollment type

        Returns
        -------
        str : A string representing the Enrollment type.
        """
        self.enrollment = enrollment_type
        return self.enrollment_type[self.enrollment]

    def get_token(self=None) -> dict:
        """Gets the API token from either an environment variable or a json
        file.

        Parameters:
        -----------
        self : none

        Returns:
        --------
        dict : An API token.

        Note: Environment variable is automatically turned on. Need more
        clarification on the running environment of this script.
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

        Raises:
        -------
        FileNotFoundError
            If the file does not exist.
        RuntimeError
            If credentials are invalid.
        Exception
            If an error occurs.
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

        Raises:
        -------
        KeyError
            If the key-value pair does not exist.
        json.JSONDecodeError
            If JSON is invalid.
        TypeError
            If type is not a JSON string
        Exception
            If an error occurs.
        """
        try:
            cred = json.loads(os.getenv('CANVAS_API_CRED'))
        except KeyError:
            print(f"Environment variable CANVAS_API_CRED does not exist.")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"Contains invalid JSON.")
            sys.exit(1)
        except TypeError:
            print("Invalid type: expected a JSON string.")
            sys.exit(1)
        except Exception as e:
            print(f"Unexpected error: {e}")
            sys.exit(1)
        return cred

    def headers(self) -> dict:
        """Generates and returns HTTP headers to send JSON data and
        authentication for API calls.

        Parameters:
        -----------
        self : none

        Returns:
        --------
        dict : HTTP headers.
        """
        token = self.get_token()
        headers = {'Content-Type': 'application/json',
                   'Authorization': 'Bearer {}'.format(
                       token[self.server_type])}
        return headers

    def get_enrollees(self, course_id: str) -> list[dict]:
        """Gets only student enrollments in the course using the Enrollments API.

        Parameters:
        -----------
        course_id (str) : ID of the course.

        Returns:
        --------
        list : List of dicts containing only sortable names of students
        enrolled in the
        course, or an empty list if no students are found or an error occurs.
        """
        enrollments_url = (
            f'{self.get_server_url()}api/v1/courses/{course_id}/enrollments'
            f'?type[]={self.get_enrollment_type()}&per_page=100')
        print(enrollments_url)
        max_retries = 3
        retry_delay = 2

        enrollments = []
        page_url = enrollments_url

        while page_url:
            for attempt in range(max_retries):
                response = requests.get(page_url, headers=self.headers())
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if isinstance(data, list) and all(
                                isinstance(enrollment, dict) for enrollment in
                                data):
                            student_enrollments = [
                                enrollment for enrollment in data
                                if enrollment.get('type') ==
                                   self.get_enrollment_type()
                            ]
                            enrollments.extend([enrollment.get('user',
                                                               {}).get(
                                'sortable_name', 'Unknown').strip(" ") for
                                                enrollment in
                                                student_enrollments])
                            page_url = self.get_next_page_url(
                                response.headers.get('Link'))
                            break  # Exit the retry loop on success

                        else:
                            print("Error: Unexpected API response format")
                            return []

                    except JSONDecodeError:
                        print("Failed to decode JSON data from response")
                        return []

                elif response.status_code in {401, 403}:
                    print(
                        "Unauthorized: Check your API token or re-authenticate.")
                    return []

                elif response.status_code == 404:
                    print(
                        f"Not Found: The course with ID {course_id} does not exist.")
                    return []

                elif response.status_code == 500:
                    print(
                        f"Server error: Retrying request in {retry_delay} seconds...")
                    time.sleep(retry_delay)

                else:
                    print(
                        f"Unexpected error ({response.status_code}): {response.text}")
                    return []

            if response.status_code != 200:
                print(
                    "Max retries reached. Could not retrieve enrollment data.")
                return []
        print(f"Enrollments is {enrollments}")
        return enrollments

    def get_next_page_url(self, link_header: str) -> str:
        """Gets the next page URI for the discussion page.

        Parameters
        ----------
        link_header (str) : Header for the next URI for the discussion page.

        Returns
        -------
        str : URI for the next page.
        """
        if link_header:
            links = link_header.split(',')
            for link in links:
                if 'rel="next"' in link:
                    next_link = link.split(';')[0].strip('<> ')
                    return next_link
        return ""

    def get_course_discussion_data(self, course_id: str,
                                   enrollees_in_course: list[str]) -> tuple[
        dict, list]:
        """Gets the discussion data for the given course, sorted by the date they were posted.

        Parameters
        ---------
        course_id (str) : ID for the course.

        Returns
        -------
        tuple[dict, list] : Returns a tuple containing the dict of student
        names as keys and a list of their courses as values; and a list of
        discussion topics sorted by posting date.
        """
        student_discussion_data = {}
        page_url = (
            f'{self.get_server_url()}api/v1/courses/{course_id}/discussion_topics?per_page=10')
        discussions = []

        while page_url:
            response = requests.get(page_url, headers=self.headers())
            if response.status_code == 200:
                try:
                    discussion_topics = response.json()
                    for topic in discussion_topics:
                        topic_title = topic.get('title', 'Unknown Title')
                        topic_id = topic.get('id', 'Unknown')
                        topic_posted_date = topic.get('last_reply_at',
                                                      '')  # Fetch the posting date
                        discussions.append((
                            topic_posted_date if topic_posted_date else '1900-01-01T00:00:00Z',
                            topic_id, topic_title))

                    page_url = self.get_next_page_url(
                        response.headers.get('Link'))
                except json.JSONDecodeError:
                    print("Failed to decode JSON data from response")
                    return {}, []
            else:
                print(
                    f"Unexpected error ({response.status_code}): {response.text}")
                page_url = None  # Ensure loop exit on error

        # Sort discussions by the posting date
        discussions.sort(key=lambda x: x[
            0])  # Sort using the first element of each tuple (date)
        list_topic_titles = [title for _, _, title in
                             discussions]  # Unpack sorted topics

        for _, topic_id, topic_title in discussions:
            self.process_full_topic_view(course_id, topic_id,
                                         student_discussion_data, topic_title,
                                         enrollees_in_course)

        ordered_by_student_name = OrderedDict(
            sorted(student_discussion_data.items()))
        return ordered_by_student_name, list_topic_titles

    def get_full_topic_view(self, course_id: str, topic_id: str) -> dict:
        """Gets the full topic for each discussion topic, which included
           threaded responses.

        Parameters
        ---------
        course_id (str) : ID for the course.
        topic_id (str) : ID for the discussion topic.

        Returns
        -------
        dict : Data associated with the topic discussion.
        """
        full_topic_view_url = (f'{self.get_server_url()}/api/v1/'
                               f'courses/{course_id}/discussion_topics/'
                               f'{topic_id}/view')
        response = requests.get(full_topic_view_url, headers=self.headers())
        if response.status_code == 200:
            try:
                full_topic_view = response.json()
                return full_topic_view
            except JSONDecodeError:
                print("Failed to decode JSON from response")
                return {}
        elif response.status_code == 403:
            # skip over as topic requires user to have posted
            return {}
        # NOTE: may need to handle 503 error if the cached structure is not yet
        # ready and prompt the caller to try again or sleep and wait and call
        # again
        else:
            print(
                f"Error fetching full topic view: {response.status_code},"
                f" {response.text}")
            return {}

    def process_full_topic_view(self, course_id: str, topic_id: str,
                                student_discussion_data: dict, topic_title: str,
                                enrolled_student_names: list[str]) -> list:
        """
        Processes the full topic view for a given course and topic, filtering participants
        based on enrolled students with StudentEnrollment.

        Parameters
        ----------
        course_id (str): ID of the course.

        topic_id (str): ID of the discussion topic.

        student_discussion_data (dict): Dictionary containing discussion data
        for students.

        topic_title (str): Title of the discussion topic.
        enrolled_student_names (list): List of sortable names of students with
        StudentEnrollment.

        Returns
        -------
        list : List of topic titles for the processed students.
        """
        topic_view = self.get_full_topic_view(course_id, topic_id)
        if not topic_view:
            return []

        list_topic_titles = []

        # Iterate through all participants in the topic view
        for entry in topic_view.get('participants', []):
            participant_name = entry.get('display_name', '')

            # Convert 'First Last' format to 'Last, First' to match sortable names
            name_parts = participant_name.split()
            if len(name_parts) > 1:
                transformed_name = f"{' '.join(name_parts[1:])}, {name_parts[0]}"
            else:
                transformed_name = participant_name

            # Filter out users who are not in the list of enrolled student names
            if transformed_name in enrolled_student_names:
                if transformed_name not in student_discussion_data:
                    student_discussion_data[transformed_name] = [topic_title]
                else:
                    student_discussion_data[transformed_name].append(
                        topic_title)

                list_topic_titles.append(topic_title)
        return list_topic_titles

    def write_discussion_data_to_csv(self, student_discussion_data: dict,
                                     discussion_titles: list) -> None:
        """Writes student participation of each discussion topic to a CSV
        file.

        Parameters
        ----------
        student_discussion_data (dict) : Student participation of discussion
        topics.

        discussion_titles (list): List of discussion topics.

        Returns
        -------
        None

        Notes:
        Outputs a CSV file containing the student participation of each
        discussion topic.
        """
        if not student_discussion_data:
            print("No student discussion data")
            return
        download_folder = Path.home() / 'Downloads'
        print(download_folder)
        if not download_folder.exists():
            download_folder.mkdir()
            print(f"Created folder: {download_folder}")
        output_file_path = download_folder / 'discusssion_data.csv'
        headers = ['Name'] + discussion_titles

        with (open(output_file_path, 'w', newline='') as csvfile):
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            # Write each student's participation data
            for student_name, topics in student_discussion_data.items():
                row = [student_name]
                for topic in discussion_titles:
                    row.append(topic in topics)
                writer.writerow(row)

        print(f"CSV file written to {output_file_path}")

    # Retrieve course name
    def get_course_name(self, course_id: str) -> str:
        """Returns the name of the course.

        Parameters:
        -----------
        course_id (str) : The id of the course.

        Returns:
        --------
        str : The name of the course.
        """
        course_url = f'{self.get_server_url()}api/v1/courses/{course_id}'
        response = requests.get(course_url, headers=self.headers())
        course = response.json()
        return course.get('name', 'Unknown Course')


def main(course_num: str) -> None:

    course_name = canvas.get_course_name(course_num)
    print(f"Course Name: {course_name}")
    course_enrollees = canvas.get_enrollees(course_num)
    if canvas.get_enrollment_type() != 'StudentEnrollment':
        if canvas.get_enrollment_type() == 'TaEnrollment':
            canvas.set_enrollment_type('Teacher')
        else:
            canvas.set_enrollment_type('TA')
        course_enrollees_addt = canvas.get_enrollees(course_num)
        course_enrollees = course_enrollees + course_enrollees_addt
    print(f"Enrollees_in_course: {course_enrollees}")
    if len(course_enrollees) > 0:
        student_discussion_tuple = canvas.get_course_discussion_data(
            course_num, course_enrollees)
        if student_discussion_tuple[0] and student_discussion_tuple[1]:
            canvas.write_discussion_data_to_csv(student_discussion_tuple[0],
                                                student_discussion_tuple[1])
            return None
    print(f"No CSV written for {course_name}")


if __name__ == '__main__':
    # need clarity if command-line request for enrollment_type
    canvas = Canvas('LPS_Test', 'TA')
    # course_number = '1748632'
    course_number = "1645103"
    main(course_number)
