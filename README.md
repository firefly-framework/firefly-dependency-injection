# Firefly Dependency Injection

This is a fairly simple and straightforward implementation of a dependency injection container
for Python.

## Installation

`pip install firefly-dependency-inject`
 
## Examples

To create a dependency injection container, extend the `DIC` class.

```python
from firefly.dependency_injection import DIC


class Container(DIC):
    pass
```

Properties are assumed to be singletons. They are also not constructed until they are requested
from the container.

```python
from firefly.dependency_injection import DIC


class Foo(object):
    def __init__(self, bar: str = 'baz'):
        self.bar = bar

class Container(DIC):
    foo1: Foo = Foo                     # This is fine if the class constructor has no parameters
    foo2: Foo = lambda c: Foo('asdf')   # Same as foo1, but you can define parameters to the constructor
    foo3: Foo = Foo()                   # This constructs the object during the declaration of Container(). You probably want to avoid this

c = Container()
assert c.foo1 is c.foo1 # foo1 is a singleton
```

You can also define a prototype (factory) with the `prototype()` decorator.

```python
from firefly.dependency_injection import DIC, prototype


class Container(DIC):
    foo Foo = prototype(lambda c: Foo())

dic = Container()
assert dic.foo is not dic.foo # You get a new instance of Foo on each property reference
```

It's a cinch to compose classes with other dependencies from the container.

```python
from firefly.dependency_injection import DIC


class Bar(object):
    def __init__(self, value: str):
        self.value = value


class Foo(object):
    def __init__(self, bar: Bar):
        self.bar = bar


class Container(DIC):
    bar: Bar = lambda c: Bar('my value')
    foo: Foo = lambda c: Foo(c.bar)


dic = Container()
assert dic.foo.bar.value == 'my value'
```

Once you have a dependency injection container defined, you can easily autowire your classes.

```python
from firefly.dependency_injection import DIC


class Bar(object):
    prop = 'bar'
    

class Baz(object):
    prop = 'baz'
    

class Foo(object):
    def __init__(self, bar: Bar, baz: Baz): # These will get injected based on the type-hints
        self.bar = bar
        self.baz = baz
        
        
class Container(DIC):
    bar: Bar = lambda c: Bar()
    baz: Baz = lambda c: Baz()


dic = Container()
autowired_foo = dic.autowire(Foo)
f = autowired_foo()
assert f.bar.prop == 'bar'
assert f.baz.prop == 'baz'

# Or you can use the build() method

f = dic.build(Foo)
assert f.bar.prop == 'bar'
assert f.baz.prop == 'baz'
```

Injection is typically performed by using the first property in the container that matches the
type specified in your constructor. If no type is specified, it will attempt to match the name
of your parameter to the name of a container property exactly.

```python
from firefly.dependency_injection import DIC


class Foo(object):
    pass
    
    
class Container(DIC):
    foo = lambda c: Foo()
    
    
class Bar(object):
    def __init__(self, foo):
        self.foo = foo
        
        
dic = Container()
b = dic.build(Bar)
assert isinstance(b.foo, Foo) 
```

Parameters type-hinted with `str` will be injected from environment variables. The container
looks for an all upper-case, and an all lower-case variant of your parameter.

```python
import os

os.environ['PARAM_1'] = 'param1'
os.environ['param_2'] = 'param2'


class Foo(object):
    def __init__(self, param_1: str, param_2: str):
        self.param_1 = param_1
        self.param_2 = param_2
        
        
dic = Container()
f = dic.build(Foo)
assert f.param_1 == 'param1'
assert f.param_2 == 'param2'
```

As a convenience during unit testing, you can use the `mock()` method to autowire and construct
a class, substituing instances of MagickMock for all dependencies.

```python
class Foo(object):
    def __init__(self, some_service: SomeService):
        self.some_service = some_service
        
    def do_something(self):
        return self.some_service.run()
        

def test_foo(sut):
    sut.some_service.run.return_value = 'foo'
    assert sut.do_something() == 'foo'
    
    
@pytest.fixture()
def sut():
    return Container().mock(Foo)
```