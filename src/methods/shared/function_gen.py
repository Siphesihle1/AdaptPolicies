"""AST call-site discovery and bounded, depth-first helper synthesis."""

import ast
import inspect
import symtable
from uuid import uuid4

from .lmp_runtime import BUILTINS, validate


def unresolved_calls(source, available):
    """Resolve direct calls in their Python lexical scopes, including bindings.

    Attribute calls are validated by the runtime rather than synthesized. Python's
    symbol table handles parameters, comprehension targets and nested definitions.
    """
    tree = ast.parse(source)
    table = symtable.symtable(source, "<generated>", "exec")
    module_bound = {s.get_name() for s in table.get_symbols() if s.is_assigned() or s.is_namespace()}
    calls = []

    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.scope = table

        def scoped(self, node, name):
            previous = self.scope
            self.scope = next((t for t in previous.get_children()
                               if t.get_lineno() == node.lineno and t.get_name() == name), previous)
            self.generic_visit(node)
            self.scope = previous

        def visit_FunctionDef(self, node):
            self.scoped(node, node.name)

        def visit_Lambda(self, node):
            self.scoped(node, "lambda")

        def visit_ListComp(self, node):
            self.scoped(node, "listcomp")

        def visit_SetComp(self, node):
            self.scoped(node, "setcomp")

        def visit_DictComp(self, node):
            self.scoped(node, "dictcomp")

        def visit_GeneratorExp(self, node):
            self.scoped(node, "genexpr")

        def visit_Call(self, node):
            if isinstance(node.func, ast.Name):
                name = node.func.id
                try:
                    symbol = self.scope.lookup(name)
                except KeyError:
                    symbol = None
                local = symbol is not None and (symbol.is_parameter() or symbol.is_free() or
                        (symbol.is_local() and self.scope is not table))
                if name not in available and name not in module_bound and not local:
                    calls.append((name, node, ast.get_source_segment(source, node)))
            self.generic_visit(node)
    Visitor().visit(tree)
    return calls


def validate_signature(definition, call):
    params = []
    args = definition.args
    positional = args.posonlyargs + args.args
    required = len(positional) - len(args.defaults)
    for i, arg in enumerate(positional):
        params.append(inspect.Parameter(arg.arg,
            inspect.Parameter.POSITIONAL_ONLY if i < len(args.posonlyargs) else inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=inspect.Parameter.empty if i < required else None))
    if args.vararg:
        params.append(inspect.Parameter(args.vararg.arg, inspect.Parameter.VAR_POSITIONAL))
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        params.append(inspect.Parameter(arg.arg, inspect.Parameter.KEYWORD_ONLY,
                                       default=inspect.Parameter.empty if default is None else None))
    if args.kwarg:
        params.append(inspect.Parameter(args.kwarg.arg, inspect.Parameter.VAR_KEYWORD))
    if not any(isinstance(a, ast.Starred) for a in call.args) and not any(k.arg is None for k in call.keywords):
        inspect.Signature(params).bind(*[None for _ in call.args], **{k.arg: None for k in call.keywords})


class FunctionGenerator:
    def __init__(self, session):
        self.session = session
        self.sources = {}
        self.dependencies = {}
        self.active = []

    def resolve(self, source, depth=0):
        session = self.session
        session.budget.check()
        validate(source, session.reserved, session.limits.max_source_bytes)
        # Active helpers are deliberately excluded from lexical module bindings
        # below so self-recursion in synthesized dependencies is rejected.
        calls = unresolved_calls(source, session.reserved | set(self.sources))
        for name, call, site in calls:
            if name in self.active:
                raise ValueError("helper_dependency_cycle: " + " -> ".join(self.active + [name]))
            if name in self.sources:
                continue
            if depth >= session.limits.max_depth:
                raise RuntimeError("helper_depth_limit")
            if len(self.sources) + len(self.active) >= session.limits.max_helpers:
                raise RuntimeError("helper_count_limit")
            if self.active:
                self.dependencies.setdefault(self.active[-1], []).append(name)
                session.emit("dependency_edge", {"caller": self.active[-1], "dependency": name,
                                                  "parent_call_id": session.current_call})
            session.emit("helper_requested", {"name": name, "call_site": site, "depth": depth,
                                               "parent_call_id": session.current_call})
            self.active.append(name)
            call_id = str(uuid4())
            generated = session.generate(session.purposes["function"], f"Implement helper {name} for call: {site}\nOriginating program:\n{source}", call_id=call_id)
            session.emit("helper_source", {"name": name, "source": generated, "call_id": call_id,
                                           "call_site": site, "parent_call_id": session.current_call})
            tree = validate(generated, session.reserved, session.limits.max_source_bytes)
            if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef) or tree.body[0].name != name:
                raise ValueError("Helper must contain exactly its requested function definition")
            validate_signature(tree.body[0], call)
            # Check generated self calls separately: module-bound names are otherwise
            # valid in ordinary policy code.
            if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == name
                   for n in ast.walk(tree.body[0])):
                raise ValueError("helper_dependency_cycle: " + name)
            previous_call = session.current_call
            session.current_call = call_id
            try:
                self.resolve(generated, depth + 1)
            finally:
                session.current_call = previous_call
            self.sources[name] = generated
            self.dependencies.setdefault(name, [])
            session.emit("helper", {"name": name, "source": generated,
                         "dependencies": self.dependencies[name], "call_site": site,
                         "parent_call_id": session.current_call})
            self.active.pop()
        return self.sources
