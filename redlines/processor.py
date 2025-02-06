import enum
import re
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Tuple, List, Optional, Union
import spacy

from redlines.document import Document

class TokenizerType(enum.StrEnum):
    REGEX = enum.auto()
    SPACY = enum.auto()

tokenizer = re.compile(r"((?:[^()\s]+|[().?!-])\s*)")
"""
This regular expression matches a group of characters that can include any character except for parentheses
and whitespace characters (which include spaces, tabs, and line breaks) or any character
that is a parenthesis or punctuation mark (.?!-).
The group can also include any whitespace characters that follow these characters.

Breaking it down further:

* `(` and `)` indicate a capturing group
* `(?: )` is a non-capturing group, meaning it matches the pattern but doesn't capture the matched text
* `[^()\s]+` matches one or more characters that are not parentheses or whitespace characters
* `|` indicates an alternative pattern
* `[().?!-]` matches any character that is a parenthesis or punctuation mark `(.?!-)`
* `\s*` matches zero or more whitespace characters (spaces, tabs, or line breaks) that follow the previous pattern.
"""
# This pattern matches one or more newline characters `\n`, and any spaces between them.

paragraph_pattern = re.compile(r"((?:\n *)+)")
"""
It is used to split the text into paragraphs.

* `(?:\\n *)` is a non-capturing group that must start with a `\\n`   and be followed by zero or more spaces.
* `((?:\\n *)+)` is the previous non-capturing group repeated one or more times.
"""

space_pattern = re.compile(r"(\s+)")
"""It is used to detect space."""

from spacy.lang.en import English
nlp = English()
"""
Tokenizer with the default settings for English including punctuation rules and exceptions.
"""

def _spacy_tokenize(text: str) -> Iterator[str]:
    for token in nlp(text):
        yield token.text
        if token.whitespace_:
            yield token.whitespace_

def tokenize_text(text: str, choice: TokenizerType) -> list[str]:
    if choice == TokenizerType.REGEX:
        return re.findall(tokenizer, text)
    elif choice == TokenizerType.SPACY:
        return list(_spacy_tokenize(text))

    raise ValueError(f"Invalid choice: {choice}")


def split_paragraphs(text: str) -> List[str]:
    """
    Splits a string into a list of paragraphs. One or more `\n` splits the paragraphs.
    For example, if the text is "Hello\nWorld\nThis is a test", the result will be:
    ['Hello', 'World', 'This is a test']

    :param text: The text to split.
    :return: a list of paragraphs.
    """

    split_text = re.split(paragraph_pattern, text)
    result = []
    for s in split_text:
        if s and not re.fullmatch(space_pattern, s):
            result.append(s.strip())

    return result


def concatenate_paragraphs_and_add_chr_182(text: str) -> str:
    """
    Split paragraphs and concatenate them. Then add a character '¶' between paragraphs.
    For example, if the text is "Hello\nWorld\nThis is a test", the result will be:
    "Hello¶World¶This is a test"

    :param text: The text to split.
    :return: a list of paragraphs.
    """
    paragraphs = split_paragraphs(text)

    result = []
    for p in paragraphs:
        result.append(p)
        result.append(" ¶ ")
        # Add a string ' ¶ ' between paragraphs.
    if len(paragraphs) > 0:
        result.pop()

    return "".join(result)


@dataclass
class Chunk:
    """A chunk of text that is being compared. In some cases, it may be the whole document"""

    text: List[str]
    """The tokens of the chunk"""
    chunk_location: Optional[str]
    """An optional string describing the location of the chunk in the document. For example, a PDF page number"""


@dataclass
class Redline:
    """A redline that is generated by the redlines library"""

    source_chunk: Chunk
    test_chunk: Chunk
    """The chunk of text that is being redlined"""
    opcodes: Tuple[str, int, int, int, int]
    """The opcodes that describe the redline in the chunk. See the difflib documentation for more information"""


class RedlinesProcessor(ABC):
    """
    An abstract class that defines the interface for a redlines processor.
    A redlines processor is a class that takes two documents and generates redlines from them.
    Use this class as a base class if you want to create a custom redlines processor.
    See `WholeDocumentProcessor` for an example of a redlines processor.
    """

    @abstractmethod
    def process(
        self, source: Union[Document, str], test: Union[Document, str]
    ) -> List[Redline]:
        pass


class WholeDocumentProcessor(RedlinesProcessor):
    """
    A redlines processor that compares two documents. It compares the entire documents as a single chunk.
    """

    source: str
    test: str

    tokenizer_type: TokenizerType = TokenizerType.REGEX

    def process(
        self, source: Union[Document, str], test: Union[Document, str]
    ) -> List[Redline]:
        """
        Compare two documents as a single chunk.
        :param source: The source document to compare.
        :param test: The test document to compare.
        :return: A list of `Redline` that describe the differences between the two documents.
        """
        self.source = source.text if isinstance(source, Document) else source
        self.test = test.text if isinstance(test, Document) else test

        seq_source = tokenize_text(concatenate_paragraphs_and_add_chr_182(self.source), self.tokenizer_type)
        seq_test = tokenize_text(concatenate_paragraphs_and_add_chr_182(self.test), self.tokenizer_type)

        from difflib import SequenceMatcher

        matcher = SequenceMatcher(None, seq_source, seq_test)

        return [
            Redline(
                source_chunk=Chunk(text=seq_source, chunk_location=None),
                test_chunk=Chunk(text=seq_test, chunk_location=None),
                opcodes=opcode,
            )
            for opcode in matcher.get_opcodes()
        ]
