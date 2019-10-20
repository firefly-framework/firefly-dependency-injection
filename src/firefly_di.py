from __future__ import annotations

import inspect
import os
import typing
from abc import ABC
from typing import Tuple, List
from unittest.mock import MagicMock


class Container(ABC):
    def __init__(self):
        self._cache = {}
        self._annotations = None
        self._unannotated = None
        self._child_containers = []

    def __getattribute__(self, item: str):
        if item.startswith('_'):
            return object.__getattribute__(self, item)

        if item in self._cache:
            return self._cache[item]()

        if not hasattr(self.__class__, item):
            return self._search_child_containers(item)

        obj = object.__getattribute__(self, item)

        if inspect.ismethod(obj) and obj.__name__ != '<lambda>':
            return obj

        if not callable(obj):
            raise AttributeError(f'Attribute {item} is not callable.')

        if inspect.isclass(obj):
            obj = self.build(obj)
            self._cache[item] = lambda: obj
        elif inspect.isfunction(obj) or inspect.ismethod(obj):
            obj = obj()
            if inspect.isfunction(obj):
                self._cache[item] = obj
            else:
                self._cache[item] = lambda: obj
        else:
            self._cache[item] = lambda: obj

        return self._cache[item]()

    def _search_child_containers(self, item: str):
        for container in self._child_containers:
            if item in dir(container):
                return getattr(container, item)

        raise AttributeError(item)

    def build(self, class_: object, **kwargs):
        a = self.autowire(class_, kwargs)
        return a()

    def mock(self, class_, **kwargs):
        a = self.autowire(class_, kwargs, with_mocks=True)
        return a()

    def autowire(self, class_, params: dict = None, with_mocks: bool = False):
        if hasattr(class_, '__original_init'):
            return class_

        if inspect.isclass(class_) and hasattr(class_, '__init__'):
            class_ = self._wrap_constructor(class_, params, with_mocks)

        return self._inject_properties(class_, with_mocks)

    def register_container(self, container):
        self._child_containers.append(container)
        return self

    def match(self, name: str, type_, searched: List[Container] = None):
        searched = searched or []
        # Prevent circular references
        if self in searched:
            return
        searched.append(self)

        t = self._find_by_type(self._get_annotations(), type_)
        if len(t) == 1:
            t = str(t[0])
        elif len(t) == 0:
            t = None
        else:
            for item in t:
                if name == item or name.lstrip('_') == item:
                    return getattr(self, item)
            t = None

        # Found type in the container
        if t is not None:
            return getattr(self, t)

        # Found object with same name in container
        elif t is None and name in self._get_unannotated():
            return getattr(self, name)

        for container in self._child_containers:
            m = container.match(name, type_, searched)
            if m is not None:
                return m

    def get_registered_services(self):
        ret = {}
        annotations = typing.get_type_hints(type(self))
        for k, v in self.__class__.__dict__.items():
            if not str(k).startswith('_'):
                ret[k] = annotations[k] if k in annotations else ''

        return ret

    def clear_annotation_cache(self):
        self._annotations = None

    def _wrap_constructor(self, class_, params, with_mocks):
        init = class_.__init__

        def init_wrapper(*args, **kwargs):
            constructor_args = self._get_constructor_args(class_)

            for name, type_ in constructor_args.items():
                if type_ == Container:
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
            if str(k).startswith('__') or v is not None:
                continue

            try:
                if k in annotations and isinstance(self, annotations[k]):
                    setattr(class_, k, self)
                    continue
            except TypeError:
                pass

            if with_mocks:
                setattr(class_, k, MagicMock(spec=annotations[k] if k in annotations else None))
            elif k in annotations:
                t = self.match(k, annotations[k])
                if t is not None:
                    setattr(class_, k, t)
            elif k in unannotated:
                setattr(class_, k, getattr(self, k))

        return class_

    def _get_class_tree_properties(self, class_: typing.Any, properties: dict = None, annotations: dict = None)\
            -> Tuple[dict, dict]:
        if properties is None and annotations is None:
            properties = {}
            annotations = {}

        properties.update(class_.__dict__)
        try:
            annotations.update(typing.get_type_hints(class_))
        except AttributeError:
            pass

        if hasattr(class_, '__bases__'):
            for base in class_.__bases__:
                properties, annotations = self._get_class_tree_properties(base, properties, annotations)

        return properties, annotations

    def _get_annotations(self):
        if self._annotations is None:
            container_object = type(self)
            self._annotations = typing.get_type_hints(container_object)

        return self._annotations

    def _get_unannotated(self):
        annotations_ = self._get_annotations()
        if self._unannotated is None:
            unannotated = inspect.getmembers(type(self), lambda a: not (inspect.isroutine(a)))
            self._unannotated = []
            for entry in unannotated:
                if entry[0] not in annotations_:
                    self._unannotated.append(entry[0])

        return self._unannotated

    @staticmethod
    def _get_constructor_args(class_):
        init = class_.__init__
        if hasattr(class_, '__original_init'):
            init = getattr(class_, '__original_init')
        try:
            constructor_args = typing.get_type_hints(init)
        except NameError:
            return {}
        items = {}
        items.update(constructor_args)
        for arg in constructor_args.keys():
            if arg != 'self' and arg not in items:
                items[arg] = 'nil'

        return items

    @staticmethod
    def _find_by_type(available: dict, t):
        ret = []

        for key, value in available.items():
            try:
                if issubclass(value, t):
                    ret.append(key)
            except TypeError:
                try:
                    if str(value) == str(t):
                        ret.append(key)
                except RecursionError:
                    pass

        return ret

    @staticmethod
    def _find_parameter(name: str):
        if name in os.environ:
            return os.environ.get(name)
        elif name.upper() in os.environ:
            return os.environ.get(name.upper())


class MockContainer(Container):
    pass


mock_container = MockContainer()


def inject_mocks(class_, **kwargs):
    return mock_container.mock(class_, **kwargs)
