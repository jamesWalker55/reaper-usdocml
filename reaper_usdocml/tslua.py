import textwrap
from typing import Literal, NamedTuple, Optional, get_args

PREAMBLE = """\
// https://stackoverflow.com/questions/56737033/how-to-define-an-opaque-type-in-typescript
declare const opaqueTypeTag: unique symbol;"""


class TranspileError(Exception):
    def __init__(self, source_text: str, msg: str) -> None:
        super().__init__(f"{msg}: {source_text!r}")


NativeTSLuaType = Literal["string", "number", "boolean", "object", "Function"]
NATIVE_TS_LUA_TYPES = frozenset(get_args(NativeTSLuaType))


class Param(NamedTuple):
    type: str
    name: str
    optional: bool


class FunctionDeclaration(NamedTuple):
    name: str
    description: Optional[str]
    params: list[Param]
    return_types: list[str]
    varargs: bool

    def function_declaration(self):
        params = ", ".join([f"{p.name}: {p.type}" for p in self.params])
        if self.varargs:
            params += ", ...args: any[]"

        if len(self.return_types) == 1:
            return_type = self.return_types[0]
        elif len(self.return_types) > 1:
            return_type = ", ".join([str(rt) for rt in self.return_types])
            return_type = f"LuaMultiReturn<[{return_type}]>"
        else:  # len(self.return_types) == 0:
            return_type = "void"

        functioncall = f"function {self.name}({params}): {return_type}"

        if self.description:
            docstring = "/**\n{}\n */".format(textwrap.indent(self.description, " * "))
            return f"{docstring}\n{functioncall}"
        else:
            return functioncall

    def method_declaration(self):
        params = ", ".join([f"{p.name}: {p.type}" for p in self.params])
        if self.varargs:
            params += ", ...args: any[]"

        if len(self.return_types) == 1:
            return_type = self.return_types[0]
        elif len(self.return_types) > 1:
            return_type = ", ".join([str(rt) for rt in self.return_types])
            return_type = f"LuaMultiReturn<[{return_type}]>"
        else:  # len(self.return_types) == 0:
            return_type = "void"

        functioncall = f"{self.name}({params}): {return_type};"

        if self.description:
            docstring = "/**\n{}\n */".format(textwrap.indent(self.description, " * "))
            return f"{docstring}\n{functioncall}"
        else:
            return functioncall


class CustomType(NamedTuple):
    name: str
    methods: list[FunctionDeclaration]

    def __str__(self) -> str:
        return self.name

    def declaration(self):
        if len(self.methods) == 0:
            return f"declare type {self.name} = {{ readonly [opaqueTypeTag]: '{self.name}' }};"
        else:
            methods = "\n\n".join([m.method_declaration() for m in self.methods])
            methods = textwrap.indent(methods, "  ")
            return (
                f"declare class {self.name} {{\n"
                "  private constructor();\n"
                "\n"
                f"{methods}\n"
                "}"
            )


class Namespace(NamedTuple):
    name: str
    functions: list[FunctionDeclaration]


def to_typescriptlua(custom_types: list[CustomType], namespaces: list[Namespace]):
    parts = [PREAMBLE]

    # generate type declarations
    type_declarations = "\n".join([x.declaration() for x in sorted(custom_types)])
    parts.append(type_declarations)

    custom_types_names: dict[str, CustomType] = {}
    for ct in custom_types:
        custom_types_names[ct.name] = ct

    def validate_type(f: FunctionDeclaration, typ: str):
        if typ in NATIVE_TS_LUA_TYPES:
            return
        if typ in custom_types_names:
            return

        raise TranspileError(f.function_declaration(), f"unknown custom type {typ!r}")

    # generate namespaces
    for namespace in namespaces:
        # convert functions to ts
        namespace_functions = "\n\n".join(
            [f.function_declaration() for f in namespace.functions]
        )
        namespace_functions = textwrap.indent(namespace_functions, "  ")

        # validate that param/retval types are valid
        for f in namespace.functions:
            for p in f.params:
                validate_type(f, p.type)
            for rt in f.return_types:
                validate_type(f, rt)

        namespace_ts = (
            "/** @noSelf */\n"
            f"declare namespace {namespace.name} {{\n"
            f"{namespace_functions}\n"
            "}"
        )
        parts.append(namespace_ts)

    return "\n\n".join(parts)
