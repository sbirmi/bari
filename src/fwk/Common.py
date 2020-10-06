"""
Commonly used utility methods and types
"""

class Map(dict):
    """A dictionary that allows access to attributes with
    the dot notation"""
    def __getattr__(self, key):
        return self[key]
