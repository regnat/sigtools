import unittest

from sigtools import specifiers, _autoforwards, support
from sigtools.tests.util import sigtester


specifiers # quiet pyflakes


class WalkerTests(unittest.TestCase):
    def test_unknown(self):
        self.assertEqual(repr(_autoforwards.UNKNOWN), '<unknown>')
        self.assertNotEqual(_autoforwards.UNKNOWN, _autoforwards.UNKNOWN)

    def test_param(self):
        def func_a(x, y):
            raise NotImplementedError
        def func_b(x, z):
            raise NotImplementedError
        pa1 = _autoforwards.Param(func_a, 'x')
        pa1d = _autoforwards.Param(func_a, 'x')
        pa2 = _autoforwards.Param(func_a, 'y')
        pb1 = _autoforwards.Param(func_b, 'x')
        pb2 = _autoforwards.Param(func_b, 'z')
        self.assertEqual(pa1, pa1)
        self.assertEqual(pa1, pa1d)
        self.assertNotEqual(pa1, pa2)
        self.assertNotEqual(pa1, pb1)
        self.assertEqual(repr(pa1), '<param \'x\' from func_a>')
        self.assertEqual(repr(pa2), '<param \'y\' from func_a>')
        self.assertEqual(repr(pb1), '<param \'x\' from func_b>')
        self.assertEqual(repr(pb2), '<param \'z\' from func_b>')

    def test_parameters(self):
        def func(a, b, c, *d, **e):
            f = 1
            return f
        w = _autoforwards.BytecodeWalker(func)
        params = [
            _autoforwards.Param(func, 'a'),
            _autoforwards.Param(func, 'b'),
            _autoforwards.Param(func, 'c'),
            _autoforwards.Param(func, 'd'),
            _autoforwards.Param(func, 'e'),
        ]
        self.assertEqual(w.params, params)
        self.assertEqual(w.locals, params + [_autoforwards.UNKNOWN])

    def test_call_function(self):
        def func():
            None()
        w = _autoforwards.BytecodeWalker(func)
        list(w)
        self.assertFalse(w.stack)


def tup(*args):
    return lambda wrapped: (wrapped,) + args


_wrapped = support.f('x, y, *, z')


@sigtester
def autosigequal(self, func, expected):
    self.assertSigsEqual(
        specifiers.signature(specifiers.autoforwards()(func)),
        support.s(expected))


@autosigequal
class AutoforwardsTests(object):
    @tup('a, b, x, y, *, z')
    def global_(a, b, *args, **kwargs):
        pass
        return _wrapped(*args, **kwargs) # pragma: nocover

    def _make_closure():
        wrapped = _wrapped
        def wrapper(b, a, *args, **kwargs):
            return wrapped(*args, **kwargs)
        return wrapper
    closure = _make_closure(), 'b, a, x, y, *, z'

    @tup('a, b, y')
    def args(a, b, *args, **kwargs):
        return _wrapped(a, *args, z=b, **kwargs)

    @tup('a, b, *args, y, z') #fixme actually undetermined
    def using_other_varargs(a, b, *args, **kwargs):
        return _wrapped(a, *b, **kwargs)

    @tup('a, b, *args, **kwargs')
    def rebind_args(a, b, *args, **kwargs):
        args = ()
        kwargs = {}
        return _wrapped(*args, **kwargs)

    @tup('*args, x, y, z')
    def rebind_using_with(*args, **kwargs):
        cm = None
        with cm() as args:
            _wrapped(*args, **kwargs)

    @tup('x, y, /, *, kwop')
    def kwo(*args, kwop):
        _wrapped(*args, z=kwop)

    @tup('a, b, y, *, z')
    def subdef(a, b, *args, **kwargs):
        def func():
            _wrapped(42, *args, **kwargs)

    @tup('a, b, y, *, z')
    def subdef_lambda(a, b, *args, **kwargs):
        lambda: _wrapped(42, *args, **kwargs)

    @tup('a, b, x, y, *, z')
    def rebind_subdef(a, b, *args, **kwargs):
        def func():
            args = ()
            kwargs = {}
            _wrapped(42, *args, **kwargs)
        _wrapped(*args, **kwargs)

    @tup('a, b, *args, **kwargs')
    def rebind_subdef_nonlocal(a, b, *args, **kwargs):
        def func():
            nonlocal args, kwargs
            args = ()
            kwargs = {}
            _wrapped(42, *args, **kwargs)
        _wrapped(*args, **kwargs)

    @tup('a, b, x, y, *, z')
    def rebind_subdef_param(a, b, *args, **kwargs):
        def func(*args, **kwargs):
            _wrapped(42, *args, **kwargs)
        _wrapped(*args, **kwargs)

    @tup('a, b, *args, **kwargs')
    def rebind_subdef_lambda_param(a, b, *args, **kwargs):
        lambda *args, **kwargs: _wrapped(*args, **kwargs)

    @tup('a, b, *args, **kwargs')
    def nonlocal_backchange(a, b, *args, **kwargs):
        def ret1():
            _wrapped(*args, **kwargs)
        def ret2():
            nonlocal args, kwargs
            args = ()
            kwargs = {}
