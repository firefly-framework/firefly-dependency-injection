import inspect
import os
from abc import ABC
from unittest.mock import MagicMock


class DIC(ABC):
    def __init__(self):
        self.cache = {}
        self.callables = {}
        self.static = {}
        self.singleton_names = []
        self.singletons = {}

        class_ = type(self)
        if not hasattr(class_, '__dic_processed'):
            for k, v in self.__class__.__dict__.items():
                if str(k).startswith('_'):
                    continue

                if hasattr(v, '__prototype'):
                    setattr(class_, k, self._prototype(k, v))
                else:
                    setattr(class_, k, self._singleton(k, v))

            setattr(class_, '__callables', self.callables)
            setattr(class_, '__static', self.static)
            setattr(class_, '__singleton_names', self.singleton_names)
            setattr(class_, '__dic_processed', True)
        else:
            self.callables = getattr(class_, '__callables')
            self.static = getattr(class_, '__static')
            self.singleton_names = getattr(class_, '__singleton_names')

    def build(self, class_: object, params: dict = None):
        a = self.autowire(class_, params)
        return a()

    def mock(self, class_, params: dict = None):
        a = self.autowire(class_, params, with_mocks=True)
        return a()

    def autowire(self, class_, params: dict = None, with_mocks: bool = False):
        if str(class_) in self.cache:
            return self.cache[str(class_)]

        if inspect.isclass(class_) and hasattr(class_, '__init__'):
            init = class_.__init__
            class_.__original_init = init
            constructor_args = inspect.getfullargspec(init)

            def init_wrapper(*args, **kwargs):
                container_object = type(self)
                available = {}
                if hasattr(container_object, '__annotations__'):
                    available = type(self).__annotations__

                unannotated = inspect.getmembers(type(self), lambda a: not (inspect.isroutine(a)))
                names = []
                for entry in unannotated:
                    names.append(entry[0])

                items = {}
                items.update(constructor_args.annotations.items())
                for arg in constructor_args.args:
                    if arg != 'self' and arg not in items:
                        items[arg] = 'nil'

                for name, type_ in items.items():
                    if type_ == DIC:
                        kwargs[name] = self
                        continue

                    t = self._find_by_type(available, type_)

                    if type_ is not str and with_mocks is True:
                        kwargs[name] = MagicMock(spec=type_ if type_ != 'nil' else None)
                        continue

                    # Found type in the container
                    if t is not None and name not in kwargs:
                        kwargs[name] = getattr(self, t)

                    # Found object with same name in container
                    elif t is None and name not in kwargs and name in names:
                        kwargs[name] = getattr(self, name)

                    # This is a string parameter. Look for params/environment variables to inject.
                    elif type_ is str:
                        t = self._find_parameter(name)
                        if t is not None:
                            kwargs[name] = t

                if params is not None:
                    for key, value in params.items():
                        kwargs[key] = value

                return init(*args, **kwargs)

            class_.__init__ = init_wrapper
            self.cache[str(class_)] = class_

        return class_

    def _singleton(self, name: str, o):
        self._add(name, o)
        self.singleton_names.append(name)

        return property(
            fget=lambda c, n=name: self._get_singleton(n), fset=lambda c, val, n=name: self._set_singleton(n, val)
        )

    def _prototype(self, name: str, o):
        self._add(name, o)

        return property(fget=lambda c, n=name: self._get(n), fset=lambda c, val, n=name: self._set(n, val))

    def _set_singleton(self, name, value):
        self.singletons[name] = value

    def _get_singleton(self, name: str):
        if name in self.singletons:
            return self.singletons[name]

        o = self._get(name)

        self.singletons[name] = o

        return o

    def _set(self, name: str, val):
        if name in self.callables:
            self.callables[name] = val
        else:
            self.static[name] = val

    def _get(self, name: str):
        if name in self.callables:
            c = self.callables[name]
            if c.__name__ == '<lambda>':
                return c(self)
            return c()
        else:
            return self.static[name]

    def _add(self, name: str, o):
        if callable(o):
            self.callables[name] = o
        else:
            self.static[name] = o

    @staticmethod
    def _find_by_type(available: dict, t):
        for key, value in available.items():
            try:
                if issubclass(value, t):
                    return key
            except TypeError:
                if str(value) == str(t):
                    return key

    @staticmethod
    def _find_parameter(name: str):
        if name in os.environ:
            return os.environ.get(name)
        elif name.upper() in os.environ:
            return os.environ.get(name.upper())


def prototype(cb):
    cb.__prototype = True
    return cb
