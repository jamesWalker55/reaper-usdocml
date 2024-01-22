REPLACEMENTS = {
    "<b>unsupported</b>": "",
    "draw_listImGui_Image": "draw_list, ImGui_Image",
    "string namereaper_array values": "string name, reaper_array values",
    "ImGui_Context ctxImGui_Image img": "ImGui_Context ctx, ImGui_Image img",
    "draw_listImGui_Image": "draw_list, ImGui_Image",
    "optional integer flagsInImGui_Function callbackIn": "optional integer flagsIn, ImGui_Function callbackIn",
    "labelreaper_array": "label, reaper_array",
    "draw_listreaper_array": "draw_list, reaper_array",
    "size_max_hImGui_Function": "size_max_h, ImGui_Function",
    "ImGui_ImageSet  = reaper.ImGui_CreateImageSet()": "ImGui_ImageSet imageset = reaper.ImGui_CreateImageSet()",
    "ImGui_Context ctxImGui_Resource obj": "ImGui_Context ctx, ImGui_Resource obj",
    "optional string msgIn msgIn": "optional string msgIn",
    "number retval = gfx.printf(string format[, various ...])": "number retval = gfx.printf(string format, optional string various ...)",
    "gfx.triangle(integer x1, integer y1, integer x2, integer y2, integer x3, integer y3, [optional integer x4, optional integer y4, ...)": "gfx.triangle(integer x1, integer y1, integer x2, integer y2, integer x3, integer y3, optional integer x4, optional integer y4, ...)",
    "integer retval = {reaper.array}.convolve([reaper.array src, integer srcoffs, integer size, integer destoffs])": "integer retval = {reaper.array}.convolve(reaper.array src, integer srcoffs, integer size, integer destoffs)",
}


def hard_fix(text: str):
    """Hard-coded fixes for the xml, since they're terribly formatted and are written by an insane person"""

    for old, new in REPLACEMENTS.items():
        text = text.replace(old, new)

    return text
