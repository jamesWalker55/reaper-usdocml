from . import parse_lua as lua
from . import tslua as ts
from .hard_fix import hard_fix
from .parse_doc import parse_usdocml


def main():
    # read the USDocML into an XML tree
    with open("Reaper_Api_Documentation.USDocML", "r", encoding="utf8") as f:
        xml_text = hard_fix(f.read())

    with open("fixed.xml", "w", encoding="utf8") as f:
        f.write(xml_text)

    root = parse_usdocml(xml_text)

    assert root.tag == "USDocBloc"

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

    with open("src/reaper.d.ts", "w", encoding="utf8") as f:
        text = ts.to_typescriptlua(
            list(custom_types.values()),
            list(namespaces.values()),
        )
        f.write(text)
