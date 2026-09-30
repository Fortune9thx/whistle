"""
Static regression guard for gl.chain.Event declarations.

Two independent rules govern gl.chain.Event subclasses, and BOTH are
invisible to genvm-lint (warns, doesn't raise) and to gltest direct-mode
(doesn't validate event emission at all -- see conftest.py):

1. At most three indexed (positional-only) fields. ABI.EVENT_MAX_TOPICS is
   4, but the event's own signature occupies one topic. A fourth
   positional field passes every local check and then fails on chain with
   `SystemError: 2: inval` inside gl_call_generic.
2. Indexed fields bind by SORTED PARAM NAME against POSITIONAL VALUE
   ORDER (Event._do_init does `for name, val in zip(sorted(names), args)`).
   A declaration whose params are not already alphabetical silently
   records every value under the wrong field name, forever, on chain.

This is parsed with `ast` against the actual bundled deploy artifact (the
file that ships), needs no genlayer import, and runs as a plain pure-logic
test. See docs/architecture.md and the WHISTLE event fix for the concrete
history: 5 of 10 events (EventFixtureCreated, EventBetPlaced,
EventResolved, EventAppealed, Claimed) originally violated rule 2 and were
reordered to alphabetical before the second Studio Next deploy.
"""
import ast

from conftest import CONTRACT_PATH


def _event_classes(tree: ast.Module):
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        is_event = any(
            (isinstance(base, ast.Attribute) and base.attr == "Event")
            or (isinstance(base, ast.Name) and base.id == "Event")
            for base in node.bases
        )
        if is_event:
            yield node


def _init_posonlyargs(class_node: ast.ClassDef):
    for item in class_node.body:
        if isinstance(item, ast.FunctionDef) and item.name == "__init__":
            names = [a.arg for a in item.args.posonlyargs if a.arg != "self"]
            return names
    return None


def test_all_events_have_at_most_three_indexed_fields():
    tree = ast.parse(open(CONTRACT_PATH, encoding="utf-8").read(), filename=CONTRACT_PATH)
    offenders = []
    for cls in _event_classes(tree):
        names = _init_posonlyargs(cls)
        if names is not None and len(names) > 3:
            offenders.append((cls.name, names))
    assert offenders == [], (
        f"gl.chain.Event subclasses with 4+ positional fields (ABI.EVENT_MAX_TOPICS "
        f"is 4, minus 1 for the signature -- a 4th field passes local checks and "
        f"fails on chain with SystemError: 2: inval): {offenders}"
    )


def test_all_events_declare_fields_in_alphabetical_order():
    tree = ast.parse(open(CONTRACT_PATH, encoding="utf-8").read(), filename=CONTRACT_PATH)
    offenders = []
    for cls in _event_classes(tree):
        names = _init_posonlyargs(cls)
        if names is not None and names != sorted(names):
            offenders.append((cls.name, names, sorted(names)))
    assert offenders == [], (
        f"gl.chain.Event subclasses whose positional params are not alphabetical "
        f"(indexed fields bind by SORTED NAME against POSITIONAL VALUE, so this "
        f"silently records every value under the wrong field name on chain): "
        f"{[(n, 'declared=' + str(d), 'must_be=' + str(s)) for n, d, s in offenders]}"
    )


def test_at_least_one_event_class_was_found():
    # Guards against the two tests above silently passing on zero classes
    # if CONTRACT_PATH or the Event base-class match ever breaks.
    tree = ast.parse(open(CONTRACT_PATH, encoding="utf-8").read(), filename=CONTRACT_PATH)
    assert len(list(_event_classes(tree))) == 10
