"""Dynamically load all word sets from Taboo/wordsets"""

import os
import yaml

from fwk.Trace import (
        Level,
        trace,
)


# .../Taboo/WordSets.py -> .../Taboo/wordsets
WORDSETS_PATH = os.path.join(os.path.split(__file__)[0], "wordsets")

# List of all supported word sets
#   filename --> WordSet
SupportedWordSets = {}

class WordSet:
    """
    WordList YAML file format

        enabled: true
        words:
           - a:
              - a1
              - a2

    Note that the words are a list (of dictionaries) to
    allow the same word to appear twice
    """
    def __init__(self, name, path):
        self.name = name
        self.path = path

        self.data = yaml.safe_load(open(self.path))

    def __str__(self):
        return "WordSet:{}".format(self.name)

    def count(self):
        if 'words' not in self.data:
            trace(Level.error, "'words' not found in", self.path)
            return 0
        return len(self.data['words'])

    def enabled(self):
        if "enabled" not in self.data:
            trace(Level.error, "'enabled' not found in", self.path)
            return False
        return self.data['enabled']

if __name__ != "__main__": # When importing
    files = os.listdir(WORDSETS_PATH)

    for f in files:
        try:
            ws = WordSet(f, os.path.join(WORDSETS_PATH, f))
        except: # pylint: disable=bare-except
            trace(Level.warn, "Not a YAML file", f)
            continue

        enabled = ws.enabled()
        count = ws.count()
        if enabled and count > 0:
            trace(Level.info, "Loaded", ws, "word count", count)
            SupportedWordSets[f] = ws
        else:
            trace(Level.info, "Not loading", ws, "enabled", enabled, "word count", count)
