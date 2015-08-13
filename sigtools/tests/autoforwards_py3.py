from sigtools import support, specifiers
from sigtools.tests.util import sigtester, tup


_wrapped = support.f('x, y, *, z')


@sigtester
def autosigequal(self, func, expected):
    self.assertSigsEqual(
        specifiers.signature(func),
        support.s(expected))


@autosigequal
class Py3AutoforwardsTests(object):
    @tup('a, b, *args, **kwargs')
    def rebind_subdef_nonlocal(a, b, *args, **kwargs):
        def func():
            nonlocal args, kwargs
            args = ()
            kwargs = {}
            _wrapped(42, *args, **kwargs)
        _wrapped(*args, **kwargs)

    @tup('a, b, *args, **kwargs')
    def nonlocal_backchange(a, b, *args, **kwargs):
        def ret1():
            _wrapped(*args, **kwargs)
        def ret2():
            nonlocal args, kwargs
            args = ()
            kwargs = {}

    @tup('a, *args, **kwargs')
    def nonlocal_deep(a, *args, **kwargs):
        def l1():
            def l2():
                nonlocal args, kwargs
                args = ()
                kwargs = {}
        _wrapped(*args, **kwargs)
