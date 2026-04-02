import re

class PatternMatcher:
    def __init__(self, words=None, multi_endings=None):
        """
        Initialize with a list of words and a dictionary of words with optional endings.


        * list of words is stored in a set data structure
        * ending are stored as is.  This will still have the set like support
        * for non-duplicates

        Args:
            words (list): List of words/phrases to match (e.g., ["hello", "world"])
            multi_endings (dict): Dict of words with optional endings (e.g., {"run": ["ning", "s"]})
        """
        self.words = set(words) if words else set()
        self.multi_endings = multi_endings if multi_endings else {}
        self.pattern = self._compile_pattern()

    def _compile_pattern(self):
        """Compile the regex pattern from the current words and multi-endings."""
        # Escape and join simple words
        escaped_words = [re.escape(word) for word in self.words]

        # Handle multi-endings (e.g., "run(ning|s)?")
        multi_patterns = []
        for word, endings in self.multi_endings.items():
            escaped_word = re.escape(word)
            endings_pattern = "|".join(endings)
            multi_patterns.append(f"{escaped_word}({endings_pattern})?")

        # Combine all patterns
        all_patterns = escaped_words + multi_patterns
        pattern_str = r"\b(" + "|".join(all_patterns) + r")\b"
        ########################################## 
        # print("pattern_str: ", pattern_str )
        # debug print if needed 
        ##########################################
        return re.compile(pattern_str, re.IGNORECASE)

    def add_word(self, word):
        """Add a single word and recompile the pattern."""
        self.words.add(word)
        self.pattern = self._compile_pattern()

    def add_words(self, words):
        """Add multiple words and recompile the pattern."""
        self.words.update(words)
        self.pattern = self._compile_pattern()

    def add_multi_ending_word(self, word, endings):
        """Add a word with optional endings and recompile the pattern."""
        self.multi_endings[word] = endings
        self.pattern = self._compile_pattern()

    def matches(self, input_string):
        """Check if the input string matches any pattern."""
        return bool(self.pattern.search(input_string))
