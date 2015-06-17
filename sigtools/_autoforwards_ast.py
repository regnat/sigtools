import inspect
import ast

from sigtools import signatures
from sigtools.specifiers import forger_function, forwards


class Name(object):
    def __init__(self, name):
        self.name = name

class Unknown(object):
    def __init__(self, source):
        self.source = source

    def __repr__(self):
        return "<unknown until runtime: {0}>".format(ast.dump(self.source))

class Varargs(object): pass
class Varkwargs(object): pass


class CallListerVisitor(ast.NodeVisitor):
    def __init__(self, func):
        self.func = func
        self.calls = []
        self.names = {}
        self.varargs = None
        self.varkwargs = None

        self.process_parameters(func.args)
        for stmt in func.body:
            self.visit(stmt)

    def __iter__(self):
        return iter(self.calls)

    def process_parameters(self, args):
        for arg in args.args:
            self.names[arg.arg] = Unknown(arg)
        for arg in args.kwonlyargs:
            self.names[arg.arg] = Unknown(arg)
        if args.vararg:
            self.varargs = self.names[args.vararg.arg] = Varargs()
        if args.kwarg:
            self.varkwargs = self.names[args.kwarg.arg] = Varkwargs()

    def resolve_name(self, name):
        if isinstance(name, ast.Name):
            id = name.id
            return self.names.get(id, Name(id))
        return Unknown(name)

    def visit_Call(self, node):
        self.calls.append((
            self.resolve_name(node.func),
            len(node.args), [kw.arg for kw in node.keywords],
            self.resolve_name(node.starargs) == self.varargs,
            self.resolve_name(node.kwargs) == self.varkwargs
            ))

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Store):
            self.names[node.id] = Unknown(node)


class UnresolvableCall(ValueError):
    pass


def forward_signatures(func, calls):
    for wrapped, num_args, keywords, use_varargs, use_varkwargs in calls:
        if not (use_varargs or use_varkwargs):
            continue
        if isinstance(wrapped, Name):
            try:
                index = func.__code__.co_freevars.index(wrapped.name)
            except ValueError:
                wrapped_func = func.__globals__[wrapped.name]
            else:
                wrapped_func = func.__closure__[index].cell_contents
        else:
            raise UnresolvableCall(wrapped)
        yield forwards(func, wrapped_func, num_args, *keywords,
                       use_varargs=use_varargs, use_varkwargs=use_varkwargs)


@forger_function
def autoforwards(obj):
    func = obj
    source = inspect.cleandoc('\n' + inspect.getsource(func.__code__))
    module = ast.parse(source)
    func_ast = module.body[0]
    try:
        sigs = list(forward_signatures(func, CallListerVisitor(func_ast)))
    except UnresolvableCall as exc:
        print(exc)
        return
    if sigs:
        return signatures.merge(*sigs)
