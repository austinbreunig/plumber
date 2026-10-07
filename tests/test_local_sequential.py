from plumber.local import LocalSequential
from plumber.protocols import Step


def step(name, fn, **params):
    return Step(name=name, fn=fn, params=params, partitionable=True, checkpoint=False)


def test_runs_input_then_phases_in_order_then_output():
    calls = []

    def load(n):
        calls.append("input")
        return list(range(n))

    def add(data, amount):
        calls.append("add")
        return [x + amount for x in data]

    def double(data):
        calls.append("double")
        return [x * 2 for x in data]

    def write(data, tag):
        calls.append(("output", tag, data))

    result = LocalSequential().execute(
        (load, {"n": 3}),
        [step("add", add, amount=1), step("double", double)],
        (write, {"tag": "t"}),
        {},
    )

    assert calls == ["input", "add", "double", ("output", "t", [2, 4, 6])]
    assert result.collect() == [2, 4, 6]


def test_output_is_optional():
    result = LocalSequential().execute((lambda: [1], {}), [], None, {})
    assert result.collect() == [1]
