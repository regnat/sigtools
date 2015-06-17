import dis

from sigtools.specifiers import forger_function, forwards
from sigtools import signatures


def iter_bytes(bytestring):
    for op in bytestring:
        if isinstance(op, str):
            op = ord(op)
        yield op

def iter_bytecode(code):
    ito = iter_bytes(code)
    for op in ito:
        if op >= dis.HAVE_ARGUMENT:
            arg = next(ito) + next(ito) * 0x100
        else:
            arg = None
        yield dis.opname[op], arg


class Unknown(object):
    def __repr__(self):
        return '<unknown>'

    def __eq__(self, other):
        return False

UNKNOWN = Unknown()


class Value(object):
    def __init__(self, val):
        self.val = val

    def __repr__(self):
        return '<value: {0!r}>'.format(self.val)

    def __eq__(self, other):
        return isinstance(other, Value) and self.val is other.val


class Param(object):
    def __init__(self, func, name):
        self.func = func
        self.name = name

    def __repr__(self):
        return '<param {0!r} from {1.__name__}>'.format(self.name, self.func)

    def __eq__(self, other):
        return (
            isinstance(other, Param)
            and self.name == other.name
            and self.func == other.func
            )


class BytecodeWalker(object):
    def __init__(self, func):
        self.func = func
        self.code = co = func.__code__
        self.ito = iter_bytecode(co.co_code)

        has_varargs = bool(co.co_flags & 0x04)
        has_varkwargs = bool(co.co_flags & 0x08)
        numparams = (
            co.co_argcount + co.co_kwonlyargcount
            + has_varargs + has_varkwargs)

        self.params = p = [
            Param(func, co.co_varnames[i])
            for i in range(numparams)
                ]
        self.varargs = p[co.co_argcount] if has_varargs else None
        self.varkwargs = p[-1] if has_varkwargs else None
        self.locals = self.params + [UNKNOWN
                                     for _ in range(co.co_nlocals - numparams)]
        self.stack = []

    def __iter__(self):
        for opname, arg in self.ito:
            if opname == 'POP_TOP':
                self.stack.pop()
            elif opname == 'POP_BLOCK':
                pass # self.stack[self.blocks.pop():] = []
            elif opname == 'RETURN_VALUE':
                return self.stack.pop()
            elif opname == 'SETUP_WITH':
                self.stack[-1] = UNKNOWN
            elif opname == 'WITH_CLEANUP':
                self.stack.pop()
            elif opname.startswith('CALL_'):
                fkw = fva = None
                if opname == 'CALL_FUNCTION_VAR_KW':
                    fkw = self.stack.pop()
                    fva = self.stack.pop()
                elif opname == 'CALL_FUNCTION_VAR':
                    fva = self.stack.pop()
                elif opname == 'CALL_FUNCTION_KW':
                    fkw = self.stack.pop()
                kwdc = arg >> 8
                posc = arg & 0xFF
                kwdn = []
                for i in range(kwdc):
                    self.stack.pop()
                    kwdn.append(self.stack.pop())
                if posc:
                    self.stack[-posc:] = []
                use_varargs = fva and fva == self.varargs
                use_varkwargs =  fkw and fkw == self.varkwargs
                wrapped = self.stack.pop()
                if use_varargs or use_varkwargs:
                    if not isinstance(wrapped, Value):
                        raise ValueError(wrapped)
                    print(fva, fkw, self.stack)
                    yield forwards(self.func, wrapped.val,
                                   posc, *(x.val for x in kwdn),
                                   use_varargs=use_varargs,
                                   use_varkwargs=use_varkwargs)
                self.stack.append(UNKNOWN)
            elif opname == 'LOAD_GLOBAL':
                self.stack.append(
                    Value(self.func.__globals__[self.code.co_names[arg]]))
            elif opname == 'LOAD_FAST':
                self.stack.append(self.locals[arg])
            elif opname == 'LOAD_DEREF':
                self.stack.append(
                    Value(self.func.__closure__[arg].cell_contents))
            elif opname == 'LOAD_CONST':
                self.stack.append(Value(self.code.co_consts[arg]))
            elif opname == 'STORE_FAST':
                self.locals[arg] = self.stack.pop()
            elif opname.startswith('LOAD_'):
                self.stack.append(opname)
                print('unknown', opname)
            elif opname.startswith('BUILD_'):
                self.stack.append(UNKNOWN)
            else:
                print('unknown', opname)
            print(opname, self.stack)

    def __repr__(self):
        return '<walker for {0.__name__}  stack={1}'.format(
            self.func, self.stack)


@forger_function
def autoforwards(obj):
    #fixme obj not a function
    func = obj
    sigs = list(BytecodeWalker(func))
    return signatures.merge(*sigs) if sigs else None

def old_autoforwards(func):
    code = func.__code__
    stack = []
    sig = signatures.signature(func)
    _, _, pva, _, pkw = signatures.sort_params(sig)
    varargs = pva and pva.name
    varkwargs = pkw and pkw.name
    for opname, arg in iter_bytecode(code.co_code):
        if opname.startswith('CALL_'):
            fkw = fva = None
            if opname == 'CALL_FUNCTION_VAR_KW':
                fkw = stack.pop()
                fva = stack.pop()
            elif opname == 'CALL_FUNCTION_VAR':
                fva = stack.pop()
            elif opname == 'CALL_FUNCTION_KW':
                fkw = stack.pop()
            kwdc = arg >> 8
            posc = arg & 0xFF
            kwdn = []
            for i in range(kwdc):
                stack.pop()
                kwdn.append(stack.pop())
            if posc:
                stack[-posc:] = []
            return forwards(
                func,
                stack.pop(),
                posc, *kwdn,
                use_varargs = fva and fva==varargs,
                use_varkwargs = fkw and fkw==varkwargs
                )
