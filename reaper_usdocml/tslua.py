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

    def declaration(self):
        return f"{self.name}{'?' if self.optional else ''}: {self.type}"

    @staticmethod
    def validate_order(params: list["Param"]):
        prev_optional = False
        for p in params:
            if prev_optional and not p.optional:
                raise TranspileError(
                    p.declaration(),
                    "positional parameter cannot follow optional parameter",
                )
            prev_optional = p.optional


class FunctionDeclaration(NamedTuple):
    name: str
    description: Optional[str]
    deprecated: Optional[str]
    params: list[Param]
    return_types: list[str]
    varargs: bool

    def _params_declaration(self):
        try:
            Param.validate_order(self.params)
        except TranspileError as e:
            print(f"[ERROR] invalid param order for: {self}")
            raise e

        params = ", ".join([p.declaration() for p in self.params])
        if self.varargs:
            params += ", ...args: any[]"
        return params

    def _retvals_declaration(self):
        if len(self.return_types) == 1:
            return self.return_types[0]
        elif len(self.return_types) > 1:
            return_type = ", ".join([str(rt) for rt in self.return_types])
            return f"LuaMultiReturn<[{return_type}]>"
        else:  # len(self.return_types) == 0:
            return "void"
        
    def _docstring(self):
        docstring_parts = []

        if self.description:
            docstring_parts.append(self.description)

        if self.deprecated:
            docstring_parts.append(f"@deprecated {self.deprecated}")

        if len(docstring_parts) == 0:
            return None

        docstring = "\n\n".join(docstring_parts)
        docstring = "/**\n{}\n */".format(
            textwrap.indent(
                docstring,
                " * ",
                lambda _: True,
            )
        )
        return docstring


    def function_declaration(self):
        params = self._params_declaration()
        return_type = self._retvals_declaration()

        functioncall = f"function {self.name}({params}): {return_type}"

        docstring = self._docstring()
        if docstring is not None:
            return f"{docstring}\n{functioncall}"
        else:
            return functioncall

    def method_declaration(self):
        params = self._params_declaration()
        return_type = self._retvals_declaration()

        functioncall = f"{self.name}({params}): {return_type};"

        docstring = self._docstring()
        if docstring is not None:
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
        namespace_functions = []
        for f in namespace.functions:
            try:
                namespace_functions.append(f.function_declaration())
            except TranspileError as e:
                print(f"[ERROR] {e}")
                continue
        namespace_functions = "\n\n".join(namespace_functions)
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
