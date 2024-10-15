#
# Levester Williams
# 31 July 2024
#
# Platform info:
# - python 3.11.0
#

import json

class JSONfreader:
    def __init__(self):
        """Initializer for JSONfreader class."""
        self._credentials = None

    def load_json_file(self, json_file: str) -> dict:
        """
        Loads Reddit credentials from an external JSON file.

        Args:
            json_file (str): Path to the JSON file

        Returns:
            dict: Dictionary containing the loaded credentials, or None if an
            error occurs.

        Notes:
            If error occurs in opening the JSON file, the function raise a
            error exception for client/caller to handle.
        """

        try:
            with open(json_file, 'r') as file:
                self._credentials = json.load(file)
                return self._credentials
        except FileNotFoundError as e:
            raise FileNotFoundError(
                "Failed to load credentials due to missing file.") from e
        except json.JSONDecodeError as e:
            raise RuntimeError("The JSON file contains invalid JSON") from e
        except Exception as e:
            raise RuntimeError("Error in loading credentials") from e
