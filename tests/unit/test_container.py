import os

import pytest

from firefly.dependency_injection import DIC, prototype


class Bar:
    pass


class Baz:
    def __init__(self, bar: Bar):
        self.bar = bar


class Container1(DIC):
    bar: Bar = Bar


class Container2(DIC):
    pass


class Container3(DIC):
    bar: Bar = lambda c: Bar()
    baz: Baz = prototype(lambda c: Baz(c.bar))


class Container4(DIC):
    bar_singleton_static: Bar = Bar
    bar_singleton_lambda: Bar = lambda c: Bar()
    bar_prototype: Bar = prototype(lambda c: Bar())


def get_foo():
    class Foo:
        def __init__(self, bar: Bar, env_var: str):
            self.bar = bar
            self.env_var = env_var

    return Foo


def test_dependency_from_container():
    c = Container3()
    print(c.bar)
    bar = c.bar
    assert isinstance(bar, Bar)
    baz = c.baz
    assert isinstance(baz, Baz)
    assert baz.bar is bar


def test_static_singleton():
    c = Container4()
    assert isinstance(c.bar_singleton_static, Bar)
    assert c.bar_singleton_static is c.bar_singleton_static


def test_lambda_singleton():
    c = Container4()
    assert isinstance(c.bar_singleton_lambda, Bar)
    assert c.bar_singleton_lambda is c.bar_singleton_lambda


def test_prototype():
    c = Container4()
    assert isinstance(c.bar_prototype, Bar)
    assert c.bar_prototype is not c.bar_prototype


def test_factory_missing_dependency():
    c = Container2()
    with pytest.raises(TypeError):
        c.build(get_foo())


def test_factory_missing_environment_variable():
    c = Container1()
    with pytest.raises(TypeError):
        c.build(get_foo())


def test_factory_success():
    os.environ['ENV_VAR'] = 'baz'
    c = Container1()
    foo_type = get_foo()
    foo = c.build(foo_type)

    assert isinstance(foo, foo_type)
    assert isinstance(foo.bar, Bar)
    assert foo.env_var == 'baz'


def test_factory_with_supplied_parameters():
    os.environ['ENV_VAR'] = 'baz'
    c = Container2()
    foo_type = get_foo()
    bar = Bar()
    foo = c.build(foo_type, {'bar': bar})

    assert isinstance(foo, foo_type)
    assert isinstance(foo.bar, Bar)
    assert foo.bar is bar
    assert foo.env_var == 'baz'
