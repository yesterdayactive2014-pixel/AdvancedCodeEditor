def expr(block):
    """Convert a single expression block to a JS value string."""
    if not isinstance(block, dict):
        return str(block) if block is not None else "0"

    t = block["type"]

    if t == "operator_add":
        return f"(Number({expr(block['a'])}) + Number({expr(block['b'])}))"
    elif t == "operator_subtract":
        return f"(Number({expr(block['a'])}) - Number({expr(block['b'])}))"
    elif t == "operator_multiply":
        return f"(Number({expr(block['a'])}) * Number({expr(block['b'])}))"
    elif t == "operator_divide":
        return f"(Number({expr(block['a'])}) / Number({expr(block['b'])}))"
    elif t == "operator_gt":
        return f"(Number({expr(block['a'])}) > Number({expr(block['b'])}))"
    elif t == "operator_lt":
        return f"(Number({expr(block['a'])}) < Number({expr(block['b'])}))"
    elif t == "operator_equals":
        return f"({expr(block['a'])} == {expr(block['b'])})"
    elif t == "operator_and":
        return f"({expr(block['a'])} && {expr(block['b'])})"
    elif t == "operator_or":
        return f"({expr(block['a'])} || {expr(block['b'])})"
    elif t == "operator_not":
        return f"!({expr(block['operand'])})"
    elif t == "operator_random":
        return f"random({expr(block['from'])}, {expr(block['to'])})"
    elif t == "operator_mod":
        return f"({expr(block['a'])} % {expr(block['b'])})"
    elif t == "operator_round":
        return f"Math.round({expr(block['num'])})"
    elif t == "operator_join":
        return f"String({expr(block['a'])}) + String({expr(block['b'])})"
    elif t == "operator_length":
        return f"String({expr(block['string'])}).length"
    elif t == "variable_get":
        return block["name"]
    elif t == "arduino_digital_read":
        return f"await digitalRead({block['pin']})"
    elif t == "arduino_analog_read":
        return f"await analogRead({block['pin']})"
    elif t == "sensor_distance":
        return f"await getDistance({block['trigger_pin']}, {block['echo_pin']})"
    elif t == "sensor_light":
        return f"await getLightValue({block['pin']})"
    elif t == "sensing_answer":
        return "answer"
    elif t == "sensing_current_year":
        return "new Date().getFullYear()"
    else:
        return str(block.get("value", "0"))


def _stmt(block, indent=0):
    """Convert a single statement block to a JS code line."""
    pad = "  " * indent
    t = block["type"]

    # ── Control ──────────────────────────────────
    if t == "control_repeat":
        body = _stmts(block.get("children", []), indent + 1)
        return f"{pad}for (let i = 0; i < {block['times']}; i++) {{\n{body}\n{pad}}}"

    elif t == "control_repeat_until":
        cond = expr(block["condition"])
        body = _stmts(block.get("children", []), indent + 1)
        return f"{pad}while (!({cond})) {{\n{body}\n{pad}}}"

    elif t == "control_forever":
        body = _stmts(block.get("children", []), indent + 1)
        return f"{pad}while (true) {{\n{body}\n{pad}}}"

    elif t == "control_if":
        cond = expr(block["condition"])
        body = _stmts(block.get("children", []), indent + 1)
        return f"{pad}if ({cond}) {{\n{body}\n{pad}}}"

    elif t == "control_if_else":
        cond = expr(block["condition"])
        body_t = _stmts(block.get("children", []), indent + 1)
        body_f = _stmts(block.get("else_children", []), indent + 1)
        return f"{pad}if ({cond}) {{\n{body_t}\n{pad}}} else {{\n{body_f}\n{pad}}}"

    elif t == "control_wait":
        return f"{pad}await wait({block['secs']});"

    # ── Motion ────────────────────────────────────
    elif t == "motion_move":
        return f"{pad}move({block['steps']});"
    elif t == "motion_turn_right":
        return f"{pad}turn({block['degrees']});"
    elif t == "motion_turn_left":
        return f"{pad}turn(-{block['degrees']});"
    elif t == "motion_goto":
        return f"{pad}goto({block['x']}, {block['y']});"
    elif t == "motion_set_x":
        return f"{pad}setX({block['x']});"
    elif t == "motion_set_y":
        return f"{pad}setY({block['y']});"
    elif t == "motion_change_x":
        return f"{pad}changeX({block['dx']});"
    elif t == "motion_change_y":
        return f"{pad}changeY({block['dy']});"
    elif t == "motion_point_in_direction":
        return f"{pad}pointInDirection({block['direction']});"

    # ── Looks ─────────────────────────────────────
    elif t == "looks_say":
        return f"{pad}say({block['message']!r});"
    elif t == "looks_say_for_secs":
        return f"{pad}await sayForSecs({block['message']!r}, {block['secs']});"
    elif t == "looks_think":
        return f"{pad}think({block['message']!r});"
    elif t == "looks_think_for_secs":
        return f"{pad}await thinkForSecs({block['message']!r}, {block['secs']});"
    elif t == "looks_show":
        return f"{pad}show();"
    elif t == "looks_hide":
        return f"{pad}hide();"
    elif t == "looks_switch_costume":
        return f"{pad}switchCostume({block['costume']!r});"
    elif t == "looks_next_costume":
        return f"{pad}nextCostume();"

    # ── Variables ─────────────────────────────────
    elif t == "variable_set":
        return f"{pad}{block['name']} = {expr(block['value'])};"
    elif t == "variable_change":
        return f"{pad}{block['name']} += {expr(block['value'])};"

    # ── Procedures ────────────────────────────────
    elif t == "procedures_call":
        args = ", ".join(expr(a) if isinstance(a, dict) else str(a) for a in block.get("args", []))
        return f"{pad}{block['name']}({args});"
    elif t == "procedures_definition":
        params = ", ".join(block.get("params", []))
        body = _stmts(block.get("children", []), indent + 1)
        return f"{pad}async function {block['name']}({params}) {{\n{body}\n{pad}}}"

    # ── Pen ───────────────────────────────────────
    elif t == "pen_clear":
        return f"{pad}await penClear();"
    elif t == "pen_down":
        return f"{pad}await penDown();"
    elif t == "pen_up":
        return f"{pad}await penUp();"
    elif t == "pen_set_color":
        return f"{pad}await setPenColor({expr(block['color'])});"
    elif t == "pen_set_size":
        return f"{pad}await setPenSize({expr(block['size'])});"

    # ── Electronics ───────────────────────────────
    elif t == "arduino_set_pin_mode":
        return f"{pad}await setPinMode({block['pin']}, {expr(block['mode'])});"
    elif t == "arduino_digital_write":
        return f"{pad}await digitalWrite({block['pin']}, {expr(block['value'])});"
    elif t == "arduino_analog_write":
        return f"{pad}await analogWrite({block['pin']}, {expr(block['value'])});"

    # ── Broadcast ──────────────────────────────
    elif t == "broadcast":
        return f"{pad}await broadcast({block['message']!r});"
    elif t == "broadcast_and_wait":
        return f"{pad}await broadcastAndWait({block['message']!r});"

    else:
        return f"{pad}// unknown: {t}"


def _stmts(blocks, indent=0):
    """Convert an array of statement blocks to JS code string."""
    return "\n".join(_stmt(b, indent) for b in blocks)


def transpile(blocks, indent=0):
    """Backward-compatible wrapper — plain statements, no event grouping."""
    return _stmts(blocks, indent)


def transpile_project(blocks):
    """Group blocks by event type into named async functions.

    Returns (code_string, meta_dict) where meta_dict has:
        'flags': list of function names for event_when_flag_clicked
        'broadcasts': dict mapping event name to list of function names
    Returns meta_dict=None if no hat blocks are present.
    """
    has_events = any(
        b.get("type") in ("event_when_flag_clicked", "event_when_broadcast_received")
        for b in blocks
    )
    if not has_events:
        return _stmts(blocks), None

    parts = []
    idx = 0
    flag_list = []
    broadcast_map = {}

    for b in blocks:
        t = b["type"]
        if t == "event_when_flag_clicked":
            name = f"__s{idx}"
            idx += 1
            body = _stmts(b.get("children", []), 1)
            parts.append(f"async function {name}() {{\n{body}\n}}")
            flag_list.append(name)
        elif t == "event_when_broadcast_received":
            msg = b.get("broadcast", "message")
            name = f"__s{idx}"
            idx += 1
            body = _stmts(b.get("children", []), 1)
            parts.append(f"async function {name}() {{\n{body}\n}}")
            broadcast_map.setdefault(msg, []).append(name)
        else:
            parts.append(_stmt(b, 0))

    import json
    bc_entries = ", ".join(
        f"{json.dumps(msg)}: [{', '.join(fns)}]" for msg, fns in broadcast_map.items()
    )
    parts.append(f"\nreturn {{ flags: [{', '.join(flag_list)}], broadcasts: {{ {bc_entries} }} }};")

    code = "\n".join(parts)
    meta = {"flags": flag_list, "broadcasts": broadcast_map}
    return code, meta


# ================================================================
# SCRATCH 3.0 .sb3 PARSER — Flat blocks (dict) → Our tree format
# ================================================================

OPCODE_MAP = {
    # motion
    "motion_movesteps": "motion_move",
    "motion_turnright": "motion_turn_right",
    "motion_turnleft": "motion_turn_left",
    "motion_gotoxy": "motion_goto",
    "motion_setx": "motion_set_x",
    "motion_sety": "motion_set_y",
    "motion_changexby": "motion_change_x",
    "motion_changeyby": "motion_change_y",
    "motion_pointindirection": "motion_point_in_direction",
    # looks
    "looks_say": "looks_say",
    "looks_sayforsecs": "looks_say_for_secs",
    "looks_think": "looks_think",
    "looks_thinkforsecs": "looks_think_for_secs",
    "looks_show": "looks_show",
    "looks_hide": "looks_hide",
    "looks_switchcostumeto": "looks_switch_costume",
    "looks_nextcostume": "looks_next_costume",
    # control
    "control_repeat": "control_repeat",
    "control_repeat_until": "control_repeat_until",
    "control_forever": "control_forever",
    "control_if": "control_if",
    "control_if_else": "control_if_else",
    "control_wait": "control_wait",
    # events
    "event_whenflagclicked": "event_when_flag_clicked",
    "event_whenbroadcastreceived": "event_when_broadcast_received",
    "event_broadcast": "broadcast",
    "event_broadcastandwait": "broadcast_and_wait",
    # operators
    "operator_add": "operator_add",
    "operator_subtract": "operator_subtract",
    "operator_multiply": "operator_multiply",
    "operator_divide": "operator_divide",
    "operator_gt": "operator_gt",
    "operator_lt": "operator_lt",
    "operator_equals": "operator_equals",
    "operator_and": "operator_and",
    "operator_or": "operator_or",
    "operator_not": "operator_not",
    "operator_random": "operator_random",
    "operator_mod": "operator_mod",
    "operator_round": "operator_round",
    "operator_join": "operator_join",
    "operator_length": "operator_length",
    # data
    "data_setvariableto": "variable_set",
    "data_changevariableby": "variable_change",
    "data_variable": "variable_get",
    # procedures
    "procedures_call": "procedures_call",
    "procedures_definition": "procedures_definition",
    # pen extensions
    "pen_clear": "pen_clear",
    "pen_down": "pen_down",
    "pen_up": "pen_up",
    "pen_setColor": "pen_set_color",
    "pen_setSize": "pen_set_size",
    # arduino / custom extensions
    "arduino_digitalWrite": "arduino_digital_write",
    "arduino_analogWrite": "arduino_analog_write",
    "arduino_digitalRead": "arduino_digital_read",
    "arduino_analogRead": "arduino_analog_read",
    "arduino_setPinMode": "arduino_set_pin_mode",
    "sensor_distance": "sensor_distance",
    "sensor_light": "sensor_light",
}

INPUT_NAME = {
    "motion_move": {"STEPS": "steps"},
    "motion_turn_right": {"DEGREES": "degrees"},
    "motion_turn_left": {"DEGREES": "degrees"},
    "motion_goto": {"X": "x", "Y": "y"},
    "motion_set_x": {"X": "x"},
    "motion_set_y": {"Y": "y"},
    "motion_change_x": {"X": "dx"},
    "motion_change_y": {"Y": "dy"},
    "motion_point_in_direction": {"DIRECTION": "direction"},
    "control_repeat": {"TIMES": "times"},
    "control_repeat_until": {"CONDITION": "condition"},
    "control_if": {"CONDITION": "condition"},
    "control_if_else": {"CONDITION": "condition"},
    "control_wait": {"DURATION": "secs"},
    "looks_say": {"MESSAGE": "message"},
    "looks_think": {"MESSAGE": "message"},
    "looks_say_for_secs": {"MESSAGE": "message", "SECS": "secs"},
    "looks_think_for_secs": {"MESSAGE": "message", "SECS": "secs"},
    "looks_switch_costume": {"COSTUME": "costume"},
    "variable_set": {"VALUE": "value"},
    "variable_change": {"VALUE": "value"},
    "broadcast": {"BROADCAST_OPTION": "message"},
    "broadcast_and_wait": {"BROADCAST_OPTION": "message"},
    "operator_add": {"NUM1": "a", "NUM2": "b"},
    "operator_subtract": {"NUM1": "a", "NUM2": "b"},
    "operator_multiply": {"NUM1": "a", "NUM2": "b"},
    "operator_divide": {"NUM1": "a", "NUM2": "b"},
    "operator_gt": {"OPERAND1": "a", "OPERAND2": "b"},
    "operator_lt": {"OPERAND1": "a", "OPERAND2": "b"},
    "operator_equals": {"OPERAND1": "a", "OPERAND2": "b"},
    "operator_and": {"OPERAND1": "a", "OPERAND2": "b"},
    "operator_or": {"OPERAND1": "a", "OPERAND2": "b"},
    "operator_not": {"OPERAND": "operand"},
    "operator_random": {"FROM": "from", "TO": "to"},
    "operator_mod": {"NUM1": "a", "NUM2": "b"},
    "operator_round": {"NUM": "num"},
    "operator_join": {"STRING1": "a", "STRING2": "b"},
    "operator_length": {"STRING": "string"},
    "pen_set_color": {"COLOR": "color"},
    "pen_set_size": {"SIZE": "size"},
    "arduino_digital_write": {"PIN": "pin", "VALUE": "value"},
    "arduino_analog_write": {"PIN": "pin", "VALUE": "value"},
    "arduino_set_pin_mode": {"PIN": "pin", "MODE": "mode"},
    "sensor_distance": {"TRIG": "trigger_pin", "ECHO": "echo_pin"},
    "sensor_light": {"PIN": "pin"},
}

FIELD_PARAM = {
    "variable_get": {"VARIABLE": "name"},
    "event_when_broadcast_received": {"BROADCAST_OPTION": "broadcast"},
    "broadcast": {"BROADCAST_OPTION": "message"},
    "broadcast_and_wait": {"BROADCAST_OPTION": "message"},
}


def _parse_sb3_input(input, blocks):
    """Parse a Scratch 3.0 input array into a value or expression block."""
    if not isinstance(input, (list, tuple)):
        return input if input is not None else 0
    if len(input) == 2:
        t, v = input
        if t == 1 and isinstance(v, (list, tuple)):
            return v[1] if len(v) > 1 else 0
        if t == 2:
            return _convert_sb3_expr(v, blocks)
        if t == 3 and isinstance(v, (list, tuple)):
            if v[0]:
                r = _convert_sb3_expr(v[0], blocks)
                if r is not None:
                    return r
            return v[1] if len(v) > 1 else 0
        if t >= 4:
            return v if v is not None else 0
        return v if v is not None else 0
    if len(input) == 3:
        t, v1, v2 = input
        if t == 2:
            r = _convert_sb3_expr(v1, blocks)
            return r if r is not None else 0
        if t == 3:
            r = _convert_sb3_expr(v1, blocks)
            if r is not None:
                return r
            return v2[1] if isinstance(v2, (list, tuple)) and len(v2) > 1 else (v2 or 0)
        if t == 1 and isinstance(v1, (list, tuple)):
            return v1[1] if len(v1) > 1 else 0
        return v1 if v1 is not None else (v2[1] if isinstance(v2, (list, tuple)) and len(v2) > 1 else (v2 or 0))
    return 0


def _convert_sb3_expr(block_id, blocks):
    """Convert a single expression/reporter block."""
    b = blocks.get(block_id)
    if not b:
        return None
    itype = OPCODE_MAP.get(b["opcode"])
    if not itype:
        if b["opcode"] == "data_variable" and "VARIABLE" in b.get("fields", {}):
            f = b["fields"]["VARIABLE"]
            return {"type": "variable_get", "name": f[0] if isinstance(f, (list, tuple)) else f}
        return None
    out = {"type": itype}
    imap = INPUT_NAME.get(itype, {})
    for sk, ok in imap.items():
        inp = b.get("inputs", {}).get(sk)
        if inp:
            out[ok] = _parse_sb3_input(inp, blocks)
    if itype == "variable_get" and "VARIABLE" in b.get("fields", {}):
        f = b["fields"]["VARIABLE"]
        out["name"] = f[0] if isinstance(f, (list, tuple)) else f
    return out


def _convert_sb3_block(block_id, blocks):
    """Convert a single Scratch block to our internal format (no body/chain)."""
    b = blocks.get(block_id)
    if not b:
        return None
    itype = OPCODE_MAP.get(b["opcode"])
    if not itype:
        return None
    out = {"type": itype}

    # Sub-stack children
    if "SUBSTACK" in b.get("inputs", {}):
        _, body_id = b["inputs"]["SUBSTACK"]
        if body_id:
            out["children"] = _convert_sb3_chain(body_id, blocks)
    if "SUBSTACK2" in b.get("inputs", {}):
        _, body_id = b["inputs"]["SUBSTACK2"]
        if body_id:
            out["else_children"] = _convert_sb3_chain(body_id, blocks)

    # Mapped inputs
    imap = INPUT_NAME.get(itype, {})
    for sk, ok in imap.items():
        inp = b.get("inputs", {}).get(sk)
        if inp:
            out[ok] = _parse_sb3_input(inp, blocks)

    # Mapped fields
    fmap = FIELD_PARAM.get(itype, {})
    for sk, ok in fmap.items():
        f = b.get("fields", {}).get(sk)
        if f:
            out[ok] = f[0] if isinstance(f, (list, tuple)) else f

    # Variable name from fields for set/change
    if itype in ("variable_set", "variable_change") and "VARIABLE" in b.get("fields", {}):
        f = b["fields"]["VARIABLE"]
        out["name"] = f[0] if isinstance(f, (list, tuple)) else f

    # Procedures call
    if itype == "procedures_call" and "mutation" in b:
        m = b["mutation"]
        if "proccode" in m:
            import re
            out["name"] = re.sub(r"\s+%[snb]", "", m["proccode"]).strip()
            import json as _json
            try:
                arg_ids = _json.loads(m.get("argumentids", "[]"))
            except Exception:
                arg_ids = []
            out["args"] = []
            for i in range(len(arg_ids)):
                inp = b.get("inputs", {}).get(f"arg{i + 1}")
                out["args"].append(_parse_sb3_input(inp, blocks) if inp else "")

    # Procedures definition
    if itype == "procedures_definition":
        p_id = b.get("inputs", {}).get("custom_block", [None, None])[1]
        if p_id and p_id in blocks:
            proto = blocks[p_id]
            if "PROCEDURE" in proto.get("fields", {}):
                pf = proto["fields"]["PROCEDURE"]
                proc_str = pf[0] if isinstance(pf, (list, tuple)) else pf
                import re
                out["name"] = re.sub(r"\s+%[snb]", "", proc_str).strip()
                n_params = len(re.findall(r"%[snb]", proc_str))
                out["params"] = []
                for i in range(1, n_params + 1):
                    an = proto.get("fields", {}).get(f"arg{i}", [None])[0]
                    if an:
                        out["params"].append(an)

    return out


def _convert_sb3_chain(start_id, blocks):
    """Follow next pointers and convert a chain of blocks."""
    result = []
    bid = start_id
    while bid and bid in blocks:
        conv = _convert_sb3_block(bid, blocks)
        if conv:
            result.append(conv)
        bid = blocks[bid].get("next")
    return result


def convert_sb3_blocks(sb3_blocks):
    """Convert a Scratch 3.0 flat block dict into our internal tree format.

    sb3_blocks: dict mapping block ID -> block object (from project.json)
    Returns a list of blocks in our internal format (with children, types mapped).
    """
    top_ids = [
        bid for bid, b in sb3_blocks.items()
        if b.get("topLevel") and not b.get("parent")
    ]

    result = []
    for bid in top_ids:
        b = sb3_blocks[bid]
        itype = OPCODE_MAP.get(b["opcode"])

        if itype in ("event_when_flag_clicked", "event_when_broadcast_received"):
            conv = _convert_sb3_block(bid, sb3_blocks)
            if conv:
                conv["children"] = _convert_sb3_chain(b.get("next"), sb3_blocks)
                result.append(conv)
        elif itype == "procedures_definition":
            conv = _convert_sb3_block(bid, sb3_blocks)
            if conv:
                result.append(conv)
        else:
            result.extend(_convert_sb3_chain(bid, sb3_blocks))

    return result


def cpp_expr(block):
    """Convert a single expression block to a C++ value string."""
    if not isinstance(block, dict):
        return str(block) if block is not None else "0"
    t = block["type"]
    if t == "operator_add":
        return f"({cpp_expr(block['a'])} + {cpp_expr(block['b'])})"
    elif t == "operator_subtract":
        return f"({cpp_expr(block['a'])} - {cpp_expr(block['b'])})"
    elif t == "operator_multiply":
        return f"({cpp_expr(block['a'])} * {cpp_expr(block['b'])})"
    elif t == "operator_divide":
        return f"({cpp_expr(block['a'])} / {cpp_expr(block['b'])})"
    elif t == "operator_gt":
        return f"({cpp_expr(block['a'])} > {cpp_expr(block['b'])})"
    elif t == "operator_lt":
        return f"({cpp_expr(block['a'])} < {cpp_expr(block['b'])})"
    elif t == "operator_equals":
        return f"({cpp_expr(block['a'])} == {cpp_expr(block['b'])})"
    elif t == "operator_and":
        return f"({cpp_expr(block['a'])} && {cpp_expr(block['b'])})"
    elif t == "operator_or":
        return f"({cpp_expr(block['a'])} || {cpp_expr(block['b'])})"
    elif t == "operator_not":
        return f"!({cpp_expr(block['operand'])})"
    elif t == "operator_random":
        return f"random({cpp_expr(block['from'])}, {cpp_expr(block['to'])})"
    elif t == "operator_mod":
        return f"({cpp_expr(block['a'])} % {cpp_expr(block['b'])})"
    elif t == "operator_round":
        return f"round({cpp_expr(block['num'])})"
    elif t == "operator_join":
        return f"String({cpp_expr(block['a'])}) + String({cpp_expr(block['b'])})"
    elif t == "operator_length":
        return f"String({cpp_expr(block['string'])}).length()"
    elif t == "variable_get":
        return block["name"]
    elif t == "arduino_digital_read":
        return f"digitalRead({block['pin']})"
    elif t == "arduino_analog_read":
        return f"analogRead({block['pin']})"
    elif t == "sensor_distance":
        return f"getDistance({block['trigger_pin']}, {block['echo_pin']})"
    elif t == "sensor_light":
        return f"getLightValue({block['pin']})"
    else:
        return str(block.get("value", "0"))


def cpp_stmt(block, indent=0):
    """Convert a single statement block to a C++ code line."""
    pad = "  " * indent
    t = block["type"]
    if t == "control_repeat":
        body = cpp_stmts(block.get("children", []), indent + 1)
        return f"{pad}for (int i = 0; i < {block['times']}; i++) {{\n{body}\n{pad}}}"
    elif t == "control_repeat_until":
        cond = cpp_expr(block["condition"])
        body = cpp_stmts(block.get("children", []), indent + 1)
        return f"{pad}while (!({cond})) {{\n{body}\n{pad}}}"
    elif t == "control_forever":
        body = cpp_stmts(block.get("children", []), indent + 1)
        return f"{pad}while (true) {{\n{body}\n{pad}}}"
    elif t == "control_if":
        cond = cpp_expr(block["condition"])
        body = cpp_stmts(block.get("children", []), indent + 1)
        return f"{pad}if ({cond}) {{\n{body}\n{pad}}}"
    elif t == "control_if_else":
        cond = cpp_expr(block["condition"])
        body_t = cpp_stmts(block.get("children", []), indent + 1)
        body_f = cpp_stmts(block.get("else_children", []), indent + 1)
        return f"{pad}if ({cond}) {{\n{body_t}\n{pad}}} else {{\n{body_f}\n{pad}}}"
    elif t == "control_wait":
        secs = block['secs']
        if isinstance(secs, (int, float)):
            ms = int(float(secs) * 1000)
        else:
            ms = f"((int)({cpp_expr(secs)} * 1000))"
        return f"{pad}delay({ms});"
    elif t == "arduino_set_pin_mode":
        mode = cpp_expr(block['mode']) if isinstance(block.get('mode'), dict) else repr(block.get('mode', 'OUTPUT')).strip("'")
        return f"{pad}pinMode({block['pin']}, {mode});"
    elif t == "arduino_digital_write":
        val = cpp_expr(block['value']) if isinstance(block.get('value'), dict) else repr(block.get('value', 'HIGH')).strip("'")
        return f"{pad}digitalWrite({block['pin']}, {val});"
    elif t == "arduino_analog_write":
        return f"{pad}analogWrite({block['pin']}, {cpp_expr(block['value'])});"
    elif t == "variable_set":
        return f"{pad}{block['name']} = {cpp_expr(block['value'])};"
    elif t == "variable_change":
        return f"{pad}{block['name']} += {cpp_expr(block['value'])};"
    elif t == "looks_say":
        return f"{pad}Serial.println({block['message']!r});"
    elif t == "looks_think":
        return f"{pad}Serial.println({block['message']!r});"
    else:
        return f"{pad}// unknown: {t}"


def cpp_stmts(blocks, indent=0):
    """Convert an array of statement blocks to C++ code string."""
    return "\n".join(cpp_stmt(b, indent) for b in blocks)


def transpile_to_ino(blocks):
    """Convert Scratch blocks to Arduino .ino sketch.

    Rules:
      - arduino_set_pin_mode → void setup() { pinMode(...); }
      - control_forever children → void loop() { ... }
      - Other top-level blocks → setup() after pinMode
      - control_wait → delay(secs * 1000)
    """
    setup_lines = []
    loop_lines = []
    # Collect top-level blocks that are NOT inside control_forever
    for b in blocks:
        t = b.get("type")
        if t == "arduino_set_pin_mode":
            setup_lines.append(cpp_stmt(b, 1))
        elif t == "control_forever":
            loop_lines.extend(cpp_stmt(b, 1) for _ in [b])
            # ^ we just add the raw control_forever block as-is for loop()
        else:
            # Everything else goes to setup
            setup_lines.append(cpp_stmt(b, 1))

    setup_body = "\n".join(setup_lines) if setup_lines else "  // инициализация"
    loop_body = "\n".join(loop_lines) if loop_lines else "  // основной цикл"

    ino = f"""// Автоматически сгенерировано из Scratch JSON
// Скомпилировано в скетч Arduino

void setup() {{
{setup_body}
}}

void loop() {{
{loop_body}
}}
"""
    return ino


# Keep transpile_to_ino also under alias for backward compat
def transpile_to_arduino(blocks):
    return transpile_to_ino(blocks)


if __name__ == "__main__":
    # Demo: convert a real Scratch 3.0 flat block structure
    import json
    sample_sb3 = {
        "hat1": {
            "opcode": "event_whenflagclicked",
            "next": "move1",
            "parent": None,
            "topLevel": True,
            "inputs": {},
            "fields": {},
            "x": 0, "y": 0
        },
        "move1": {
            "opcode": "motion_movesteps",
            "next": "repeat1",
            "parent": "hat1",
            "topLevel": False,
            "inputs": {"STEPS": [1, [4, 10]]},
            "fields": {}
        },
        "repeat1": {
            "opcode": "control_repeat",
            "next": None,
            "parent": "move1",
            "topLevel": False,
            "inputs": {
                "TIMES": [1, [4, 4]],
                "SUBSTACK": [2, "if1"]
            },
            "fields": {}
        },
        "if1": {
            "opcode": "control_if",
            "next": "wait1",
            "parent": "repeat1",
            "topLevel": False,
            "inputs": {
                "CONDITION": [2, "gt1"],
                "SUBSTACK": [2, "turn1"]
            },
            "fields": {}
        },
        "gt1": {
            "opcode": "operator_gt",
            "parent": "if1",
            "topLevel": False,
            "inputs": {
                "OPERAND1": [2, "varX"],
                "OPERAND2": [1, [4, 200]]
            },
            "fields": {}
        },
        "varX": {
            "opcode": "data_variable",
            "parent": "gt1",
            "topLevel": False,
            "inputs": {},
            "fields": {"VARIABLE": ["x", "varId"]}
        },
        "turn1": {
            "opcode": "motion_turnright",
            "next": None,
            "parent": "if1",
            "topLevel": False,
            "inputs": {"DEGREES": [1, [4, 90]]},
            "fields": {}
        },
        "wait1": {
            "opcode": "control_wait",
            "next": None,
            "parent": "if1",
            "topLevel": False,
            "inputs": {"DURATION": [1, [4, 0.1]]},
            "fields": {}
        }
    }

    converted = convert_sb3_blocks(sample_sb3)
    print("# Converted blocks from Scratch 3.0 flat structure:")
    print(json.dumps(converted, indent=2, ensure_ascii=False))
    print()

    code, meta = transpile_project(converted)
    print(code)
