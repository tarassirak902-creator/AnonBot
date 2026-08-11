from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDLERS = ROOT / "app" / "handlers"

# Duplicates in this set are deliberate compatibility/canonical adapters. Import
# order in app.handlers.__init__ deliberately registers the canonical route first;
# the later implementation remains for legacy direct imports and compatibility.
ALLOWED_EXACT_DUPLICATES = {
    "nav_main_menu",
    "admin_back_to_panel",
    "buy_vip_sub",
    "profile_withdraw",
    "profile_refresh",
    "user_activity_center",
    "community_dialog_history",
    "community_connections",
    "engagement_missions",
    "admin_warned_list",
    "admin_restricted_list",
    "check_required_subscriptions",
    "ads_buy_post",
    "ads_back_post",
    "ads_community_channel",
    "ads_community_group",
}


def _attr_chain(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _exact_values(expr: ast.AST) -> set[str]:
    values: set[str] = set()
    if isinstance(expr, ast.BoolOp):
        for item in expr.values:
            values.update(_exact_values(item))
    elif isinstance(expr, ast.BinOp) and isinstance(expr.op, (ast.BitAnd, ast.BitOr)):
        values.update(_exact_values(expr.left))
        values.update(_exact_values(expr.right))
    elif isinstance(expr, ast.Compare) and len(expr.ops) == 1 and isinstance(expr.ops[0], ast.Eq):
        if _attr_chain(expr.left) == "F.data":
            right = expr.comparators[0]
            if isinstance(right, ast.Constant) and isinstance(right.value, str):
                values.add(right.value)
    elif isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute):
        if _attr_chain(expr.func.value) == "F.data" and expr.func.attr == "in_" and expr.args:
            arg = expr.args[0]
            if isinstance(arg, (ast.Set, ast.List, ast.Tuple)):
                for item in arg.elts:
                    if isinstance(item, ast.Constant) and isinstance(item.value, str):
                        values.add(item.value)
    return values


def test_exact_callback_routes_do_not_conflict_unexpectedly() -> None:
    locations: dict[str, list[str]] = defaultdict(list)
    for path in sorted(HANDLERS.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                if not _attr_chain(decorator.func).endswith("router.callback_query"):
                    continue
                values: set[str] = set()
                for arg in decorator.args:
                    values.update(_exact_values(arg))
                for value in values:
                    locations[value].append(f"{path.name}:{node.name}")

    conflicts = {
        value: funcs
        for value, funcs in locations.items()
        if len(funcs) > 1 and value not in ALLOWED_EXACT_DUPLICATES
    }
    assert not conflicts, f"Unexpected duplicate exact callback routes: {conflicts}"
