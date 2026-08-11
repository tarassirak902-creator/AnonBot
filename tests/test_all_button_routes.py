from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"


def _python_sources() -> list[Path]:
    return sorted(APP.rglob("*.py"))


def _literal_strings(node: ast.AST) -> set[str]:
    values: set[str] = set()
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        values.add(node.value)
    elif isinstance(node, (ast.Set, ast.List, ast.Tuple)):
        for item in node.elts:
            values.update(_literal_strings(item))
    return values


def _fstring_prefix(node: ast.AST) -> str | None:
    if not isinstance(node, ast.JoinedStr) or not node.values:
        return None
    first = node.values[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str) and first.value:
        return first.value
    return None


def _keyword(call: ast.Call, name: str) -> ast.AST | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _attr_chain(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _collect_button_contracts() -> tuple[set[str], set[str], set[str], set[str]]:
    callback_exact: set[str] = set()
    callback_prefixes: set[str] = set()
    text_exact: set[str] = set()
    text_prefixes: set[str] = set()

    for path in _python_sources():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            callee = _attr_chain(node.func)
            if callee.endswith("InlineKeyboardButton"):
                value = _keyword(node, "callback_data")
                if value is None:
                    continue
                callback_exact.update(_literal_strings(value))
                prefix = _fstring_prefix(value)
                if prefix:
                    callback_prefixes.add(prefix)
            elif callee.endswith("KeyboardButton"):
                value = _keyword(node, "text")
                if value is None:
                    continue
                text_exact.update(_literal_strings(value))
                prefix = _fstring_prefix(value)
                if prefix:
                    text_prefixes.add(prefix)

    return callback_exact, callback_prefixes, text_exact, text_prefixes


def _collect_filter_contracts() -> tuple[set[str], set[str], set[str], set[str]]:
    callback_exact: set[str] = set()
    callback_prefixes: set[str] = set()
    text_exact: set[str] = set()
    text_prefixes: set[str] = set()

    def collect_expr(expr: ast.AST) -> None:
        if isinstance(expr, ast.BoolOp):
            for value in expr.values:
                collect_expr(value)
            return
        if isinstance(expr, ast.Compare) and len(expr.ops) == 1 and isinstance(expr.ops[0], ast.Eq):
            left = _attr_chain(expr.left)
            right = expr.comparators[0]
            values = _literal_strings(right)
            if left == "F.data":
                callback_exact.update(values)
            elif left == "F.text":
                text_exact.update(values)
            return
        if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute):
            base = _attr_chain(expr.func.value)
            method = expr.func.attr
            if not expr.args:
                return
            if method == "in_":
                values = _literal_strings(expr.args[0])
                if base == "F.data":
                    callback_exact.update(values)
                elif base == "F.text":
                    text_exact.update(values)
            elif method == "startswith":
                values = _literal_strings(expr.args[0])
                if base == "F.data":
                    callback_prefixes.update(values)
                elif base == "F.text":
                    text_prefixes.update(values)

    for path in _python_sources():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                name = _attr_chain(decorator.func)
                if not (name.endswith("router.callback_query") or name.endswith("router.message")):
                    continue
                for arg in decorator.args:
                    collect_expr(arg)

    return callback_exact, callback_prefixes, text_exact, text_prefixes


def _covered(value: str, exact: set[str], prefixes: set[str]) -> bool:
    return value in exact or any(value.startswith(prefix) for prefix in prefixes)


def _prefix_covered(prefix: str, exact: set[str], prefixes: set[str]) -> bool:
    return any(prefix.startswith(handler) or handler.startswith(prefix) for handler in prefixes) or any(
        value.startswith(prefix) for value in exact
    )


def test_every_static_inline_button_has_a_registered_route() -> None:
    button_exact, button_prefixes, _, _ = _collect_button_contracts()
    handler_exact, handler_prefixes, _, _ = _collect_filter_contracts()

    missing_exact = sorted(
        value for value in button_exact if not _covered(value, handler_exact, handler_prefixes)
    )
    missing_prefixes = sorted(
        prefix for prefix in button_prefixes if not _prefix_covered(prefix, handler_exact, handler_prefixes)
    )
    assert not missing_exact and not missing_prefixes, (
        "Inline buttons without a registered callback route:\n"
        f"exact={missing_exact}\n"
        f"prefixes={missing_prefixes}"
    )


def test_every_static_reply_button_has_a_registered_route() -> None:
    _, _, button_exact, button_prefixes = _collect_button_contracts()
    _, _, handler_exact, handler_prefixes = _collect_filter_contracts()

    missing_exact = sorted(
        value for value in button_exact if not _covered(value, handler_exact, handler_prefixes)
    )
    missing_prefixes = sorted(
        prefix for prefix in button_prefixes if not _prefix_covered(prefix, handler_exact, handler_prefixes)
    )
    assert not missing_exact and not missing_prefixes, (
        "Reply buttons without a registered message route:\n"
        f"exact={missing_exact}\n"
        f"prefixes={missing_prefixes}"
    )
