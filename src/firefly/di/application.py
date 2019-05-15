import inspect
import os
from abc import ABC
from typing import Tuple
from unittest.mock import MagicMock


class DIC(ABC):
    def __init__(self):
        self.callables = {}
        self.static = {}
        self.singleton_names = []
        self.singletons = {}
        self.annotations = None
        self.unannotated = None
        self.child_containers = []

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
        if hasattr(class_, '__original_init'):
            return class_

        if inspect.isclass(class_) and hasattr(class_, '__init__'):
            class_ = self._wrap_constructor(class_, params, with_mocks)

        return self._inject_properties(class_, with_mocks)

    def register_container(self, container):
        self.child_containers.append(container)
        return self

    def match(self, name: str, type_):
        t = self._find_by_type(self._get_annotations(), type_)

        # Found type in the container
        if t is not None:
            return getattr(self, t)

        # Found object with same name in container
        elif t is None and name in self._get_unannotated():
            return getattr(self, name)

        for container in self.child_containers:
            m = container.match(name, type_)
            if m is not None:
                return m

    def get_registered_services(self):
        ret = {}
        annotations = type(self).__annotations__
        for k, v in type(self).__dict__.items():
            if not str(k).startswith('_'):
                ret[k] = annotations[k] if k in annotations else ''

        return ret

    def _wrap_constructor(self, class_, params, with_mocks):
        init = class_.__init__

        def init_wrapper(*args, **kwargs):
            constructor_args = self._get_constructor_args(class_)

            for name, type_ in constructor_args.items():
                if type_ == DIC:
                    kwargs[name] = self
                    continue

                if type_ is not str and with_mocks is True:
                    kwargs[name] = MagicMock(spec=type_ if type_ != 'nil' else None)
                    continue

                # Search this container, and any child containers for a match
                t = self.match(name, type_)
                if t is not None and name not in kwargs:
                    kwargs[name] = t

                # This is a string parameter. Look for params/environment variables to inject.
                elif type_ is str:
                    t = self._find_parameter(name)
                    if t is not None:
                        kwargs[name] = t

            if params is not None:
                for key, value in params.items():
                    kwargs[key] = value

            return init(*args, **kwargs)

        setattr(class_, '__original_init', init)
        class_.__init__ = init_wrapper

        return class_

    def _inject_properties(self, class_, with_mocks: bool):
        properties, annotations = self._get_class_tree_properties(class_)
        unannotated = self._get_unannotated()

        for k, v in properties.items():
            if str(k).startswith('_') or v is not None:
                continue

            if with_mocks:
                setattr(class_, k, MagicMock(spec=annotations[k] if k in annotations else None))
            elif k in annotations:
                t = self.match(k, annotations[k])
                if t is not None:
                    setattr(class_, k, t)
            elif k in unannotated:
                setattr(class_, k, getattr(self, k))

        return class_

    def _get_class_tree_properties(self, class_: object, properties: dict = None, annotations: dict = None)\
            -> Tuple[dict, dict]:
        if properties is None and annotations is None:
            properties = {}
            annotations = {}

        properties.update(class_.__dict__)
        try:
            annotations.update(class_.__annotations__)
        except AttributeError:
            pass

        if hasattr(class_, '__bases__'):
            for base in class_.__bases__:
                properties, annotations = self._get_class_tree_properties(base, properties, annotations)

        return properties, annotations

    def _get_annotations(self):
        if self.annotations is None:
            container_object = type(self)
            self.annotations = {}
            if hasattr(container_object, '__annotations__'):
                self.annotations = type(self).__annotations__

        return self.annotations

    def _get_unannotated(self):
        if self.unannotated is None:
            unannotated = inspect.getmembers(type(self), lambda a: not (inspect.isroutine(a)))
            self.unannotated = []
            for entry in unannotated:
                self.unannotated.append(entry[0])

        return self.unannotated

    @staticmethod
    def _get_constructor_args(class_):
        init = class_.__init__
        if hasattr(class_, '__original_init'):
            init = getattr(class_, '__original_init')
        constructor_args = inspect.getfullargspec(init)
        items = {}
        items.update(constructor_args.annotations.items())
        for arg in constructor_args.args:
            if arg != 'self' and arg not in items:
                items[arg] = 'nil'

        return items

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
