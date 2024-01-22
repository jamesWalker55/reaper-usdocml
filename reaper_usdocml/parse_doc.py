import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional, Union


def parse_attrs(attrs: str):
    result = {}

    # find double-quoted strings
    # ignore escaped double-quotes (\") in the string
    pattern = r'''(?<==)".*?(?<!\\)"'''

    # x = re.findall(r'''(?<==)".+?(?<!\\)"''', attrs)
    # result.append([_.group(0) for _ in x])

    # [' since_when=', ' alternative=', ' removed=', '']
    non_strings: list[str] = []
    # ['"JS 0.980"', '""', '"yes"']
    strings: list[str] = []

    prev_span: tuple[int, int] = (0, 0)
    for match in re.finditer(pattern, attrs):
        span = match.span()

        # add text between last match and this match
        non_strings.append(attrs[prev_span[-1] : span[0]])

        # parse the raw string
        # '"GetSetProjectInfo_String with desc=\\"PROJECT_AUTHOR\\"(available since Reaper 6.39)"'
        bad_string = match.group(0)
        real_string = bad_string[1:-1].replace('\\"', '"')
        strings.append(real_string)

        prev_span = span

    # add text after last match
    non_strings.append(attrs[prev_span[-1] :])

    assert len(non_strings) == len(strings) + 1

    # NOTE: The last 'non_strings' is not processed in this loop
    for non_string, string in zip(non_strings, strings):
        # non_string = ' since_when='
        # string = 'SWS 2.13.0.0'

        # non_string must contain attributes that have values WITHOUT spaces
        # meaning all attributes in non_string must be space separated
        assignments = non_string.split()
        last_partial_assignment = assignments.pop()
        assert last_partial_assignment[-1] == "="

        for a in assignments:
            k, v = a.split("=")
            result[k] = v

        result[last_partial_assignment[:-1]] = string

    # NOTE: handle the last 'non_strings' here
    last_assignment = non_strings[-1].strip()
    # No idea how to implement, wait until you get an error then fix it
    assert len(last_assignment) == 0, "Not implemented"

    return result


@dataclass
class BadElement:
    tag: str
    attrs: dict[str, str]
    # if None, then this is self-closing
    content: Optional[str]

    @classmethod
    def parse_text(cls, text: str, tags: list[str]):
        # construct the patter
        pattern_start = f"<(?P<tag>{'|'.join(tags)})"

        pattern_end_tag = r"([^/>]*?)>((?:.|\n)*?)" + f"</(?P=tag)>"
        pattern_end_self_closing = r"([^/>]*?)/>"

        # match both self-closing elements, and elements with text contents
        pattern = (
            f"{pattern_start}(?:(?:{pattern_end_tag})|(?:{pattern_end_self_closing}))"
        )

        # split the text into:
        #     [text, element, text, element, ...]
        result: list[Union[str, cls]] = []
        prev_span: tuple[int, int] = (0, 0)
        for match in re.finditer(pattern, text):
            span = match.span()

            # add text between last match and this match
            result.append(text[prev_span[-1] : span[0]])

            # parse the element
            # result.append((match.group("tag"),) + match.groups()[1:])
            tag: str = match.group("tag")
            end_tag_attrs: Optional[str] = match.group(2)
            content: Optional[str] = match.group(3)
            self_closing_attrs: Optional[str] = match.group(4)

            # one of end_tag or self_closing must have attrs
            attrs: str = self_closing_attrs if end_tag_attrs is None else end_tag_attrs  # type: ignore
            assert attrs is not None

            bad_element = cls(tag, parse_attrs(attrs), content)
            result.append(bad_element)

            prev_span = span

        # add text after last match
        result.append(text[prev_span[-1] :])

        return result

    def to_xml(self):
        attrs_xml = " ".join([f'{k}="{html.escape(v)}"' for k, v in self.attrs.items()])

        if self.content is not None:
            return f"<{self.tag} {attrs_xml}>{html.escape(self.content)}</{self.tag}>"
        else:
            return f"<{self.tag} {attrs_xml} />"

    @classmethod
    def fix(cls, text: str, tags: list[str]):
        result: list[str] = []
        for x in cls.parse_text(text, tags):
            if isinstance(x, str):
                result.append(x)
            else:
                result.append(x.to_xml())
        return "".join(result)


def print_tree(element: ET.Element, indent=0, file=None):
    base_indent = " " * (indent * 2)

    parts = [base_indent, element.tag]
    if len(element.attrib) > 0:
        parts.append(f" {element.attrib!r}")

    if element.text and len(element.text.strip()) > 0:
        parts.append(f" {element.text.strip()!r}")

    print("".join(parts), file=file)

    for child in element:
        print_tree(child, indent + 1, file=file)


def parse_usdocml(text: str):
    text = BadElement.fix(
        text,
        [
            "description",
            "parameters",
            "functioncall",
            "retvals",
            "deprecated",
            "changelog",
        ],
    )

    return ET.fromstring(text)


def main():
    with open("Reaper_Api_Documentation.USDocML", "r", encoding="utf8") as f:
        root = parse_usdocml(f.read())

    assert root.tag == "USDocBloc"


if __name__ == "__main__":
    main()
