import json
import xml.etree.ElementTree as ET
from argparse import ArgumentParser
from pathlib import Path
from typing import Optional

from . import parse_lua as lua
from . import tslua as ts
from .parse_doc import parse_usdocml


def parse_args():
    parser = ArgumentParser()
    parser.add_argument("input", type=Path, help="path to the .usdocml file")
    parser.add_argument("output", type=Path, help="path to the output .d.ts file")
    parser.add_argument(
        "-r",
        "--replacements",
        type=Path,
        help="path to an optional JSON file containing string replacements for the input file",
    )
    parser.add_argument(
        "-f",
        "--write-fixed",
        type=Path,
        help="path to an optional output XML file with the string replacements applied",
    )
    return parser.parse_args()


def usdocml_to_ts_declaration(root: ET.Element):
    assert root.tag == "USDocBloc", "expected document root tag to be 'USDocBloc'"

    # in each subsection, find and parse the lua functioncall
    functioncalls: list[lua.FunctionCall] = []
    for docbloc in root:
        assert docbloc.tag == "US_DocBloc"

        lua_functioncall = docbloc.find('functioncall[@prog_lang="lua"]')
        if lua_functioncall is None:
            continue

        try:
            parsed = lua.FunctionCall.from_element(lua_functioncall)
            functioncalls.append(parsed)
        except lua.ParseError as e:
            print(f"[ERROR] {e}")

    custom_types: dict[str, ts.CustomType] = {}

    def sanitise_type_name(name: str) -> str:
        return name.replace(".", "_")

    def sanitise_param_name(name: str) -> str:
        if name in {"in", "function"}:
            return f"_{name}"

        return name.replace(".", "_")

    def get_type(x: str) -> str:
        # handle standard types
        if x in {"int", "integer", "number"}:
            return "number"
        elif x == "string":
            return "string"
        elif x == "boolean":
            return "boolean"
        elif x == "table":
            return "object"
        elif x == "function":
            return "Function"

        # handle custom opaque type
        x = sanitise_type_name(x)
        if x in custom_types:
            return x
        else:
            ct = ts.CustomType(x, [])
            custom_types[x] = ct
            return x

    namespaces: dict[str, ts.Namespace] = {}
    for fc in functioncalls:
        if fc.namespace.startswith("{") and fc.namespace.endswith("}"):
            # class method
            class_name = sanitise_type_name(fc.namespace[1:-1])
            if class_name not in custom_types:
                custom_types[class_name] = ts.CustomType(class_name, [])

            target = custom_types[class_name].methods

        else:
            if fc.namespace not in namespaces:
                namespaces[fc.namespace] = ts.Namespace(fc.namespace, [])

            namespace = namespaces[fc.namespace]
            target = namespace.functions

        params = [
            ts.Param(get_type(p.type), sanitise_param_name(p.name), p.optional)
            for p in fc.params
        ]
        retvals: list[str] = [get_type(rt.type) for rt in fc.retvals]
        # TODO: Fix description
        desc = None

        declaration = ts.FunctionDeclaration(fc.name, desc, params, retvals, fc.varargs)
        target.append(declaration)

    return ts.to_typescriptlua(
        list(custom_types.values()),
        list(namespaces.values()),
    )


def main():
    args = parse_args()

    input_path: Path = args.input
    output_path: Path = args.output
    replacements_path: Optional[Path] = args.replacements
    fixed_path: Optional[Path] = args.write_fixed

    # read the shitty xml
    with open(input_path, "r", encoding="utf8") as f:
        input_text = f.read()

    # apply fixes if provided
    if replacements_path is not None:
        with open(replacements_path, "r", encoding="utf8") as f:
            replacements_json = json.load(f)

        assert isinstance(replacements_json, dict), "replacements must be a dictionary"
        for src, dst in replacements_json.items():
            assert isinstance(src, str), "dictionary key must be a string"
            assert isinstance(dst, str), "dictionary value must be a string"

            input_text = input_text.replace(src, dst)

    # parse the fixed xml
    root = parse_usdocml(input_text)

    # write optional fixed XML
    if fixed_path is not None:
        fixed_text = ET.tostring(root, encoding="unicode")
        with open(fixed_path, "w", encoding="utf8") as f:
            f.write(fixed_text)

    # convert to typescript declarations
    ts_declaration = usdocml_to_ts_declaration(root)
    with open(output_path, "w", encoding="utf8") as f:
        f.write(ts_declaration)
