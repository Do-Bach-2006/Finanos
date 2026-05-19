"""
This file use to create a cache for the API.

The purpose of it is to store the value fetched by the API in a small time ! to avoid API usage and also faster respond !

"""

import json
from functools import wraps


# cs2 market is always on
# crypto market is always on !
# forex market is not always on!
# comodity market is not always on !
# stock market is not always on !

# valid TTL for each type

TTL_reference = {
    "cs2": 5 * 60,
    "crypto": 20,
    "forex": {"active": 20, "closed": 60 * 60 * 12},
    "commodity": {"active": 20, "closed": 60 * 60 * 12},
    "stock": {"active": 20, "closed": 60 * 60 * 12},
}


class API_value:
    """This class is use to store the value fetched by the api.

    Attributes:
        name (str): The name of the API.
        value (float/any): The value of the API.
        last_fetched (int): The last time the API was fetched.
        time_to_live (int): The time to live of the API.
    """

    def __init__(self, name: str, value: float, time: int = 3600):
        self.name = name
        self.value = value
        self.last_fetched = time
        self.time_to_live = time


class Caching:
    """Manages local storage of API responses to minimize redundant requests.

    Attributes:
        max_size (int): The maximum number of items the cache can hold.
        cache (dict): The internal dictionary storing cached data.
    """

    def __init__(
        self, max_size: int = 1000, save_path: str = "./data/api/cache_values.json"
    ):
        """Initializes the cache with a maximum size limit."""
        self.max_size = max_size
        self.cache = {}
        self.save_path = save_path

    def get_by_key(self, key: str) -> API_value:
        """Retrieves a specific value from the cache by its key.

        Args:
            key (str): The identifier for the cached data.

        Returns:
            API_value: The cached API_value object if found, else None.
        """
        return self.cache[key] if key in self.cache else None

    def get_all(self) -> dict:
        """Retrieves all currently cached key-value pairs.

        Returns:
            dict: The entire cache dictionary.
        """
        return self.cache

    def get_by_time_period(self, timestamp_start: int, timestamp_end: int) -> list:
        """Retrieves cached items stored within a specific time period.

        Args:
            timestamp_start (int): The start time.
            timestamp_end (int): The end time.

        Returns:
            list: A list of API_value objects matching the timeframe.
        """

        matched_object = []

        for key, items in self.cache.items():
            if timestamp_start <= items.last_fetched <= timestamp_end:
                matched_object.append((key, items))

        return matched_object

    def set_value(self, key: str, value: API_value):
        """Stores a new value in the cache.

        Args:
            key (str): The identifier for the data.
            value (API_value): The data object to store.
        """
        self.cache[key] = value

    def is_in_cache(self, key: str) -> bool:
        """Checks if a given key currently exists in the cache.

        Args:
            key (str): The key to check.

        Returns:
            bool: True if the key exists, False otherwise.
        """
        return key in self.cache

    def remove_value(self, key: str):
        """Removes a specific value from the cache.

        Args:
            key (str): The key of the item to remove.
        """

        del self.cache[key]

    def update_value(self, key: str, new_value: API_value):
        """Updates an existing value in the cache.

        Args:
            key (str): The key of the item to update.
            new_value (API_value): The updated data object.
        """
        self.cache[key] = new_value

    def save_to_json(self, path: str) -> bool:
        """Saves the current cache to a JSON file.

        Args:
            path (str): The path to the JSON file.

        Returns:
            bool: True if the cache was saved successfully, False otherwise.
        """
        with open(self.save_path, "w") as f:
            json.dump(self.cache, f, indent=4)
        return True

    def load_from_json(self, path: str) -> bool:
        """Loads the cache from a JSON file.

        Args:
            path (str): The path to the JSON file.

        Returns:
            bool: True if the cache was loaded successfully, False otherwise.
        """
        with open(self.save_path, "r") as f:
            self.cache = json.load(f)
        return True


class OnlineInformations:
    """Handles data fetching from external APIs and integrates with Caching.

    This class ensures that external requests are only made when data is not
    available in the cache, thereby saving API tokens.

    Attributes:
        cache_manager (Caching): The cache instance used to store and retrieve data.
    """

    def __init__(self, cache_manager: Caching):
        """Initializes the information fetcher with a caching manager.

        Args:
            cache_manager (Caching): An instance of the Caching class.
        """
        self.cache_manager = cache_manager

    def fetch_data_logger(self, func):
        """ wrapper to display the informations of the query
        Args:
            func (function): The function to wrap.
        Returns:
            API_value: The resulting data, either from cache or freshly fetched.
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper


class GeminiDistributor:
    """Distributes requests across multiple Gemini API instances or keys.

    Utilizes a Round Robin load balancing algorithm to ensure uniform distribution
    of API requests and prevent rate-limiting on a single key.

    Attributes:
        api_endpoints (list[str]): A list of available API keys or endpoint URLs.
        _current_index (int): Tracks the index of the next endpoint to use.
    """

    def __init__(self, api_endpoints: list[str]):
        """Initializes the distributor with a list of endpoints.

        Args:
            api_endpoints (list[str]): List of Gemini API keys/endpoints.
        """
        self.api_endpoints = api_endpoints
        self._current_index = 0

    def get_next_endpoint(self) -> str:
        """Retrieves the next available API endpoint using Round Robin logic.

        Returns:
            str: The selected API endpoint or key.
        """
        if not self.api_endpoints:
            raise ValueError("No API endpoints available.")

        endpoint = self.api_endpoints[self._current_index]
        self._current_index = (self._current_index + 1) % len(
            self.api_endpoints
        )  # we % to make sures it always in the range of the list index
        return endpoint


# the logic is enough ! we then use it for better and faster learning
