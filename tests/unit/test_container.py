import os

import pytest

from firefly_di import Container


class Bar:
    pass


class Baz:
    def __init__(self, bar: Bar):
        self.bar = bar


class BarBaz:
    def __init__(self, bar: Bar, baz: Baz):
        self.bar = bar
        self.baz = baz


class PropInject:
    bar: Bar = None


class BaseClass:
    bar: Bar = None


class ChildPropInject(BaseClass):
    baz: Baz = None


class Container1(Container):
    bar: Bar = Bar


class Container2(Container):
    pass


class Container3(Container):
    bar: Bar = lambda self: Bar()
    baz: Baz = lambda self: Baz(self.bar)


class Container4(Container):
    bar_singleton_static: Bar = Bar
    bar_singleton_lambda: Bar = lambda c: Bar()
    bar_prototype: Bar = lambda self: lambda: Bar()


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
    foo = c.build(foo_type, bar=bar)

    assert isinstance(foo, foo_type)
    assert isinstance(foo.bar, Bar)
    assert foo.bar is bar
    assert foo.env_var == 'baz'


def test_sub_container():
    dic = Container1()
    dic.register_container(Container3())

    bar_baz = dic.build(BarBaz)
    assert isinstance(bar_baz.bar, Bar)
    assert isinstance(bar_baz.baz, Baz)


def test_property_injection():
    dic = Container3()

    prop_inject = dic.build(PropInject)
    assert isinstance(prop_inject.bar, Bar)

    child_prop_inject = dic.build(ChildPropInject)
    assert isinstance(child_prop_inject.bar, Bar)
    assert isinstance(child_prop_inject.baz, Baz)


def test_child_containers():
    dic = Container1()
    dic.register_container(Container3())
    assert isinstance(dic.baz, Baz)


def test_circular_reference():
    dic = Container1()
    dic3 = Container3()
    dic.register_container(dic3)
    dic3.register_container(dic)

    with pytest.raises(AttributeError):
        print(dic.foobar)
