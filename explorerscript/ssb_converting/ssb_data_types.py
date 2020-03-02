"""Data types used to describe ssb components"""
#  MIT License
#
#  Copyright (c) 2020 Parakoopa
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all
#  copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#  SOFTWARE.
#
from enum import Enum
from typing import Dict, TypeVar, Union, List, OrderedDict as OrderedDictType


def escape_quotes(string):
    return string.replace('"', '\\"').replace("'", "\\'")


def escape_newlines(string):
    return string.replace('\n', '\\n')


class SsbRoutineType(Enum):
    GENERIC = 1
    ACTOR = 3
    OBJECT = 4
    PERFORMER = 5
    COROUTINE = 9


class SsbNamedId:
    def __init__(self, id: int, name: str):
        self.id = id
        self.name = name

    def __repr__(self):
        return str(self)

    def __str__(self):
        return f"{self.__class__.__name__}<{self.name}({self.id})>"

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return int(self) == int(other)

    def __int__(self):
        return self.id


class SsbOpCode(SsbNamedId):
    pass


class SsbCoroutine(SsbNamedId):
    pass


class SsbWarning(UserWarning):
    pass


class SsbRoutineInfo:
    def __init__(self, type: SsbRoutineType, linked_to: int):
        self.type = type
        self.linked_to = linked_to

    def __repr__(self):
        return str(self)

    def __str__(self):
        return f"{self.__class__.__name__}<{self.type}({self.linked_to})>"


class SsbOpParamConstant:
    """An actual constant representing an int"""
    def __init__(self, name: str):
        self.name = name

    def __str__(self):
        return self.name


class SsbOpParamConstString:
    """A string constant from the table of string constants in an Ssb"""
    def __init__(self, name: str):
        self.name = name

    def __str__(self):
        return f"'{self.name}'"


class SsbOpParamLanguageString:
    """A string from the table of strings in an Ssb"""
    def __init__(self, strings: Dict[str, str]):  # {language_name: string}
        self.strings = strings
        # Because this will print a multiline output, this may specify the original indent of the current
        # line in the converter, may be set by the converter before converting to string
        self.indent = 0

    def __str__(self):
        string = '{\n'
        for language, lang_string in self.strings.items():
            string += ' ' * ((self.indent + 1) * NUMBER_OF_SPACES_PER_INDENT)
            string += f'{language}="{escape_newlines(escape_quotes(lang_string))}",\n'
        string += ' ' * (self.indent * NUMBER_OF_SPACES_PER_INDENT)
        string += '}'
        return string


SsbOpParam = TypeVar('SsbOpParam', int, SsbOpParamConstant, SsbOpParamConstString, SsbOpParamLanguageString)
ListOfSsbOpParam = Union[List[SsbOpParam], OrderedDictType[str, SsbOpParam]]


class SsbOperation:
    def __init__(self, offset: int, op_code: SsbOpCode, params: ListOfSsbOpParam):
        self.offset = offset
        self.op_code = op_code
        self.params = params

    def __repr__(self):
        return str(self)

    def __str__(self):
        return f"{self.__class__.__name__}<{str({k:v for k,v in self.__dict__.items()})}>"


NUMBER_OF_SPACES_PER_INDENT = 4