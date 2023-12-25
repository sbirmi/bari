"""Dynamically load all word sets from Taboo/wordsets"""

from collections import defaultdict
import os
import random
import yaml

from fwk.Common import Map
from fwk.Trace import (
        Level,
        trace,
)


# .../Taboo/WordSets.py -> .../Taboo/wordsets
WORDSETS_PATH = os.path.join(os.path.split(__file__)[0], "wordsets")

# List of all supported word sets
#   filename --> WordSet
SupportedWordSets = {}

def randomWord(wordPool):
    return random.sample(list(wordPool), 1)[ 0 ]

class WordSet:
    """
    WordList YAML file format

        enabled: true
        words:
           a:
              - a1
              - a2
    """
    def __init__(self, name, path):
        self.name = name
        self.path = path

        self.data = {}
        self.allWords = {}
        self.loadData()

        self._usedWordsByRequestor = defaultdict( set )

    def loadData(self):
        self.data = yaml.safe_load(open(self.path))
        self.allWords = set(self.data.get('words', {}))
        trace(Level.info, "Loaded", len(self.allWords), "words")

    def __str__(self):
        return "WordSet:{}".format(self.name)

    def count(self):
        if 'words' not in self.data:
            trace(Level.error, "'words' not found in", self.path)
            return 0
        return len(self.allWords)

    def enabled(self):
        if "enabled" not in self.data:
            trace(Level.error, "'enabled' not found in", self.path)
            return False
        return self.data['enabled']

    def areWordsAvailable(self, requestor):
        return len(self._usedWordsByRequestor[requestor]) < self.count()

    def nextWord(self, requestor):
        """
        Arguments
        ---------
        requestor : unique hashable key

        Returns : Map or None
        ----------------------
        If no words are remaining, return None. Else, return
            Map(word : str, disallowed : list[str],
                usedWordIdxs : set(int))
        """
        if not self.areWordsAvailable(requestor):
            # No more words
            return None

        candidateWords = self.allWords - self._usedWordsByRequestor[requestor]
        word = randomWord(candidateWords)
        disallowed = self.data['words'][word]

        self._usedWordsByRequestor[requestor].add(word)

        return Map(word=word, disallowed=disallowed)

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
