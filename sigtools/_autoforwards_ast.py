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


class Closure(object):
    def __init__(self, clv):
        self.clv = clv
        self.names = clv.names.copy()
        self.nonlocals = set()

    def restore(self):
        save = {k: self.clv.names[k] for k in self.nonlocals}
        self.clv.names = self.names
        self.clv.names.update(save)
        return self.nonlocals


class CallListerVisitor(ast.NodeVisitor):
    def __init__(self, func):
        self.func = func
        self.closures = []
        self.calls = []
        self.names = {}
        self.in_subdef = False
        self.tainted_names = set()
        self.varargs = None
        self.varkwargs = None

        self.process_parameters(func.args)
        for stmt in func.body:
            self.visit(stmt)

    def process_parameters(self, args, starargs=True):
        for arg in args.args:
            self.names[arg.arg] = Unknown(arg)
        for arg in args.kwonlyargs:
            self.names[arg.arg] = Unknown(arg)
        if args.vararg:
            varargs = self.names[args.vararg.arg] = Varargs()
            if starargs:
                self.varargs = varargs
        if args.kwarg:
            varkwargs = self.names[args.kwarg.arg] = Varkwargs()
            if starargs:
                self.varkwargs = varkwargs

    def resolve_name(self, name):
        if isinstance(name, ast.Name):
            id = name.id
            return self.names.get(id, Name(id))
        return Unknown(name)

    def new_closure(self):
        self.closures.append(Closure(self))

    def pop_closure(self):
        self.tainted_names.update(self.closures.pop().restore())

    def visit_FunctionDef(self, node):
        self.in_subdef = True
        self.new_closure()
        self.process_parameters(node.args, starargs=False)
        body = node.body
        try:
            iter(body)
        except TypeError: # handle lambdas as well
            body = [node.body]
        for stmt in body:
            self.visit(stmt)
        self.pop_closure()
        self.in_subdef = False

    visit_Lambda = visit_FunctionDef

    def visit_Nonlocal(self, node):
        try:
            clos = self.closures[-1]
        except IndexError:
            return
        for name in node.names:
            clos.nonlocals.add(name)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Store):
            self.names[node.id] = Unknown(node)

    def visit_Call(self, node):
        self.calls.append((
            self.in_subdef,
            self.resolve_name(node.func),
            len(node.args), [kw.arg for kw in node.keywords],
            self.resolve_name(node.starargs) if node.starargs else None,
            node.starargs.id if node.starargs else None,
            self.resolve_name(node.kwargs) if node.kwargs else None,
            node.kwargs.id if node.kwargs else None
            ))

    def __iter__(self):
        for (
                in_subdef, wrapped, num_args, keywords,
                varargs, varargs_name, varkwargs, varkwargs_name
                ) in self.calls:
            use_varargs = (
                varargs == self.varargs
                and not (in_subdef and varargs_name in self.tainted_names))
            use_varkwargs = (
                varkwargs == self.varkwargs
                and not (in_subdef and varkwargs_name in self.tainted_names))
            yield wrapped, num_args, keywords, use_varargs, use_varkwargs


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
