# sigtools - Python module to manipulate function signatures
# Copyright (c) 2013 Yann Kaiser
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""
`sigtools.specifiers`: Decorators to enhance a callable's signature
-------------------------------------------------------------------

"""

from functools import partial, update_wrapper

from sigtools import _util, modifiers, signatures

__all__ = [
    'forwards',
    'signature',
    'forwards_to', 'forwards_to_method',
    'forwards_to_super', 'apply_forwards_to_super',
    'forger_function', 'set_signature_forger',
    ]


_kwowr = modifiers.kwoargs('obj')


def signature(obj):
    """Retrieve the signature of ``obj``, taking into account any specifier
    from this module.

    You can use ``emulate=True`` as an argument to the specifiers from this
    module if you wish them to work with `inspect.signature` or its `functools`
    backport directly.

    ::

        >>> from sigtools import specifiers
        >>> import inspect
        >>> def inner(a, b):
        ...     return a + b
        ...
        >>> @specifiers.forwards_to(inner)
        ... def outer(c, *args, **kwargs):
        ...     return c * inner(*args, **kwargs)
        ...
        >>> print(inspect.signature(outer))
        (c, *args, **kwargs)
        >>> print(specifiers.signature(outer))
        (c, a, b)
        >>> @specifiers.forwards_to(inner, emulate=True)
        ... def outer(c, *args, **kwargs):
        ...     return c * inner(*args, **kwargs)
        #fixme

    """
    forger = getattr(obj, '_sigtools__forger', None)
    if forger is None:
        return _util.signature(obj)
    ret = forger(obj=obj)
    return ret


def set_signature_forger(obj, forger, emulate=None):
    if not emulate:
        try:
            obj._sigtools__forger = forger
            return obj
        except (AttributeError, TypeError):
            if emulate is False:
                raise
    return _ForgerWrapper(obj, forger)


def _transform(obj, meta):
    try:
        name = obj.__name__
    except AttributeError:
        return obj
    cls = meta('name', (object,), {name: obj})
    return cls.__dict__[name]


class _ForgerWrapper(object):
    def __init__(self, obj, forger):
        update_wrapper(self, obj)
        self.__wrapped__ = obj
        self._transformed = False
        self._signature_forger = forger
        self.__signature__ = forger(obj=obj)

    def __call__(self, *args, **kwargs):
        return self.__wrapped__(*args, **kwargs)

    def __get__(self, instance, owner):
        if not self._transformed:
            self.__wrapped__ = _transform(self.__wrapped__, type(owner))
            self._transformed = True
        return type(self)(
            _util.safe_get(self.__wrapped__, instance, owner),
            self._signature_forger)


def forger_function(func):
    @modifiers.kwoargs('emulate')
    def _apply_forger(emulate=None, *args, **kwargs):
        def _applier(obj):
            return set_signature_forger(
                obj, partial(func, *args, **kwargs), emulate)
        return _applier
    sig = forwards(_apply_forger, func, 0, 'obj')
    update_wrapper(_apply_forger, func, updated=())
    _apply_forger.__signature__ = sig
    return _apply_forger


@modifiers.autokwoargs
def forwards(wrapper, wrapped, *args, **kwargs):
    """Returns an effective signature of ``wrapper`` when it forwards
    its ``*args`` and ``**kwargs`` to ``wrapped``.

    :param callable wrapper: The outer callable
    :param callable wrapped: The callable ``wrapper``'s extra arguments
        are passed to.

    See `sigtools.signatures.embed` and `mask <sigtools.signatures.mask>` for
    the other parameters' documentation.
    """
    return signatures.forwards(
        _util.signature(wrapper), signature(wrapped),
        *args, **kwargs)
forwards.__signature__ = forwards(forwards, signatures.forwards, 2)


@_kwowr
def forwards_to(obj, *args, **kwargs):
    """Wraps the decorated function to give it the effective signature
    it has when it forwards its ``*args`` and ``**kwargs`` to the static
    callable wrapped.

    ::

        >>> from sigtools.specifiers import forwards_to
        >>> def wrapped(x, y):
        ...     return x * y
        ...
        >>> @forwards_to(wrapped)
        ... def wrapper(a, *args, **kwargs):
        ...     return a + wrapped(*args, **kwargs)
        ...
        >>> from inspect import signature
        >>> print(signature(wrapper))
        (a, x, y)

    """
    ret = forwards(obj, *args, **kwargs)
    return ret
forwards_to.__signature__ = forwards(forwards_to, forwards, 1)
forwards_to = forger_function(forwards_to)


@forger_function
@forwards_to(forwards, 2)
@_kwowr
def forwards_to_method(obj, wrapped_name, *args, **kwargs):
    """Wraps the decorated method to give it the effective signature
    it has when it forwards its ``*args`` and ``**kwargs`` to the method
    named by ``wrapped_name``.

    :param str wrapped_name: The name of the wrapped method.
    """
    try:
        self = obj.__self__
    except AttributeError:
        self = None
    if self is None:
        return _util.signature(obj)
    return forwards(obj, getattr(self, wrapped_name), *args, **kwargs)


forwards_to_ivar = forwards_to_method


def _get_origin_class(obj, cls):
    if cls is not None:
        return cls
    try:
        idx = obj.__code__.co_freevars.index('__class__')
    except ValueError:
        raise ValueError('Class could not be auto-determined.')
    return obj.__closure__[idx].cell_contents


@forger_function
@forwards_to(forwards, 2)
@modifiers.kwoargs('obj', 'cls')
def forwards_to_super(obj, cls=None, *args, **kwargs):
    """Wraps the decorated method to give it the effective signature it has
    when it forwards its ``*args`` and ``**kwargs`` to the same method on
    the super object for the class it belongs in.

    You can only use this decorator directly in Python versions 3.3 and up,
    and the wrapped function must make use of the arg-less form of super::

        >>> from sigtools.specifiers import forwards_to_super
        >>> class Base:
        ...     def func(self, x, y):
        ...         return x * y
        ..
        >>> class Subclass(Base):
        ...     @forwards_to_super()
        ...     def func(self, a, *args, **kwargs):
        ...         return a + super().func(*args, **kwargs)
        ...
        >>> from inspect import signature
        >>> print(signature(Subclass.func))
        (self, a, x, y)
        >>> print(signature(Subclass().func))
        (a, x, y)

    If you need to use similar functionality in older python versions, use
    `apply_forwards_to_super` instead.

    """
    try:
        self = obj.__self__
    except AttributeError:
        self = None
    if self is None:
        return _util.signature(obj)
    inner = getattr(
        super(_get_origin_class(obj, cls), self),
        obj.__name__)
    return forwards(obj, inner, *args, **kwargs)


@forwards_to(forwards_to_super, 1, 'cls', use_varargs=False)
@modifiers.autokwoargs
def apply_forwards_to_super(num_args=0, named_args=(), *member_names,
                            **kwargs):
    """Applies the `forwards_to_super` decorator on
    ``member_names`` in the decorated class, in a way which
    works in Python 2.6 and up.

        >>> from sigtools.specifiers import apply_forwards_to_super
        >>> class Base:
        ...     def func(self, x, y):
        ...         return x * y
        ...
        >>> @apply_forwards_to_super('func')
        ... class Subclass(Base):
        ...     def func(self, a, *args, **kwargs):
        ...         return a + super(Subclass, self).func(*args, **kwargs)
        ...
        >>> from inspect import signature
        >>> print(signature(Subclass.func))
        (self, a, x, y)
        >>> print(signature(Subclass().func))
        (a, x, y)

    """
    return partial(_apply_forwards_to_super, member_names,
                   ((0,) + named_args), kwargs)


def _apply_forwards_to_super(member_names, m_args, m_kwargs, cls):
    fts = forwards_to_super(*m_args, cls=cls, **m_kwargs)
    for name in member_names:
        setattr(cls, name, fts(cls.__dict__[name]))
    return cls

