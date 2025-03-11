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


class CanvasDiscussions:
    """This class reads data from a course's Canvas discussion engagements and
    prints the data in a CSV format.

    Attributes:
    -----------
    server_url : dict
        A dictionary that contains information about the server url.

    enrollment_type : dist
        A dictionary that contains the Enrollment type to be queried.

    course_name : str
        A string that represents the course name.

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
    course_name = "Unknown"

    def __init__(self, server_type: str, enrollment: str,
                 course_number: str) -> None:
        """Initializes the class with the server type."""
        self.server_type = server_type
        self.enrollment = enrollment
        self.course_num = course_number

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

    def get_enrollees(self, course_id: str) -> list[tuple]:
        """Gets only student enrollments in the course using the Enrollments API.

        Parameters:
        -----------
        course_id (str) : ID of the course.

        Returns:
        --------
        list : List of tuples containing only sortable names and ids of students
        enrolled in the course, or an empty list if no students are found or
        an error occurs.
        """
        enrollments_url = (
            f'{self.get_server_url()}api/v1/courses/{course_id}/enrollments'
            f'?type[]={self.get_enrollment_type()}&per_page=100')
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
                            filtered_enrollments = [
                                enrollment for enrollment in data
                                if enrollment.get('type') ==
                                   self.get_enrollment_type()
                            ]
                            enrollments.extend([(enrollment.get('user',
                                                                {}).get(
                                'id', 'Unknown'), enrollment.get('user',
                                                                 {}).get(
                                'sortable_name', 'Unknown').strip()) for
                                enrollment in
                                filtered_enrollments])
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
                                   enrollees_in_course: list[tuple]) -> tuple[
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
        page_url = f'{self.get_server_url()}api/v1/courses/{course_id}/discussion_topics?per_page=10'
        discussions = []
        while page_url:
            response = requests.get(page_url, headers=self.headers())
            if response.status_code == 200:
                try:
                    discussion_topics = response.json()
                    for topic in discussion_topics:
                        if topic.get('published', False):
                            topic_title = topic.get('title', 'Unknown Title')
                            topic_id = topic.get('id', 'Unknown')
                            topic_posted_date = topic.get('last_reply_at',
                                                          '1900-01-01T00:00:00Z')
                            discussions.append(
                                (topic_posted_date, topic_id, topic_title))
                    page_url = self.get_next_page_url(
                        response.headers.get('Link'))
                except json.JSONDecodeError:
                    print("Failed to decode JSON data from response")
                    return {}, []
                except KeyError:
                    print("Key error in processing discussion topics")
                    return {}, []
            else:
                print(
                    f"Unexpected error ({response.status_code}): {response.text}")
                page_url = None
        discussions.sort(
            key=lambda x: x[0] if x[0] is not None else '1900-01-01T00:00:00Z')
        # Initialize participation data after discussions list is populated
        list_topic_titles = [title for _, _, title in discussions]
        enrollee_discussion_data = {
            enrollee[1]: [False] * len(list_topic_titles) for enrollee in
            enrollees_in_course}

        # Process each topic and update participation data
        for _, topic_id, topic_title in discussions:
            self.process_full_topic_view(course_id, topic_id,
                                         enrollee_discussion_data, topic_title,
                                         enrollees_in_course, list_topic_titles)

        ordered_by_sortable_name = OrderedDict(
            sorted(enrollee_discussion_data.items()))
        return ordered_by_sortable_name, list_topic_titles

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
                                enrollee_discussion_data: dict, topic_title:
            str, enrollees_in_course: list[tuple],
                                list_topic_titles: list) -> None:
        """
        Processes the full topic view for a given course and topic, filtering
        participants based on specified Enrollment type.


        Parameters
        ----------
        course_id (str): ID of the course.

        topic_id (str): ID of the discussion topic.

        enrollees_discussion_data (dict): Dict containing the sortable name
        of enrollees and a list of discussion topics.

        topic_title (str): Title of the discussion topic.

        enrollees_in_course (list[tuple]): List containing tuple with the id
        and sortable name for enrollment type of course.

        Returns
        -------
        list : List of topic titles for the processed students.
        """
        topic_view = self.get_full_topic_view(course_id, topic_id)
        if not topic_view:
            return

        for participant in topic_view.get('participants', []):
            participant_id = participant.get('id', 'Unknown')
            matched_enrollee = next(
                (enrollee for enrollee in enrollees_in_course if
                 enrollee[0] == participant_id), None)
            if matched_enrollee:
                enrollee_name = matched_enrollee[1]
                topic_index = list_topic_titles.index(topic_title)
                enrollee_discussion_data[enrollee_name][
                    topic_index] = True

        return None

    def write_discussion_data_to_csv(self, enrollee_discussion_data: dict,
                                     discussion_titles: list):
        """Writes enrollee participation of each discussion topic to a CSV
        file.

        Parameters
        ----------
        enrollee_name (dict) : Enrollee participation of discussion
        topics.

        discussion_titles (list): List of discussion topics.

        Returns
        -------
        None

        Notes:
        Outputs a CSV file containing the enrollee participation of each
        discussion topic.
        """
        download_folder = Path.home() / 'Downloads'
        if not download_folder.exists():
            download_folder.mkdir()
        if self.get_enrollment_type() == "StudentEnrollment":
            output_file_path = download_folder / (
                f'{self.course_name}_students_discussions.csv')
        else:
            output_file_path = download_folder / (
                f'{self.course_name}_instructors_discussions.csv')
        with open(output_file_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Name'] + discussion_titles)
            for enrollee, participations in enrollee_discussion_data.items():
                writer.writerow(
                    [enrollee] + ['Yes' if participated else 'No' for
                                  participated in participations])

        print(f"CSV file written to {output_file_path}")

    # Retrieve course name
    def set_course_name(self, course_id: str) -> None:
        """Sets the name of the course.

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
        self.course_name = course.get('name', 'Unknown Course')
        return

    def get_course_name(self) -> str:
        """Gets the name of the course.

        Returns:
        --------
        str : The name of the course
        """
        return self.course_name


def main() -> None:
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
            canvas.write_discussion_data_to_csv(enrollee_discussion_tuple[0],
                                                enrollee_discussion_tuple[1])
            return None
    print(f"No CSV written for {canvas.course_name}")
    return None


if __name__ == '__main__':
    # course_number = '1748632', Sandbox site
    # Clay's course: "1844505"
    course_num = "1645103"
    canvas = CanvasDiscussions('LPS_Production', 'TA', course_num)
    main()
