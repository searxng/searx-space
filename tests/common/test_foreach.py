import asyncio
import time
import pytest

from searxstats.common.foreach import for_each


@pytest.mark.asyncio
@pytest.mark.parametrize('limit', [None, 4, 3, 2, 1])
async def test_for_each(limit):
    input_list = ['A', 'B', 'C', 'D']
    expected_output = set(input_list)
    output_set = set()
    parallel = [0, 0]

    def f_generic(i):
        parallel[0] += 1
        parallel[1] = max(parallel)
        yield
        if i in output_set:
            raise ValueError(f'{i} already seen')
        output_set.add(i)
        parallel[0] -= 1

    async def f_func(i):
        generic_routine = f_generic(i)
        next(generic_routine)
        time.sleep(0.5)
        next(generic_routine, None)

    async def f_async(i):
        generic_routine = f_generic(i)
        next(generic_routine)
        await asyncio.sleep(0.5)
        next(generic_routine, None)

    await for_each(input_list, f_func, limit=limit)
    assert output_set == expected_output
    assert parallel[0] == 0
    assert parallel[1] == limit or 1

    output_set = set()
    parallel = [0, 0]
    await for_each(input_list, f_async, limit=limit)
    assert output_set == expected_output


@pytest.mark.asyncio
async def test_for_each_exception():
    input_list = ['A', 'B', 'C', 'D']

    output_set = set()

    def f_func(i):
        if i == 'C':
            raise ValueError()
        output_set.add(i)

    async def f_async(i):
        f_func(i)

    with pytest.raises(ValueError):
        await for_each(input_list, f_async)
    assert output_set == {'A', 'B'}

    output_set = set()
    with pytest.raises(ValueError):
        await for_each(input_list, f_func)
    assert output_set == {'A', 'B'}

    output_set = set()
    with pytest.raises(ValueError):
        await for_each(input_list, f_async, limit=2)
    assert output_set == {'A', 'B', 'D'}

    output_set = set()
    with pytest.raises(ValueError):
        await for_each(input_list, f_func, limit=2)
    assert output_set == {'A', 'B', 'D'}


@pytest.mark.asyncio
async def test_for_each_huge_simple():
    input_list = list(range(1, 500))
    output_set = set()

    def f_func(i):
        output_set.add(i)

    await for_each(input_list, f_func, limit=70)

    for i in range(1, 500):
        if i not in output_set:
            raise ValueError(f'{i} not found')
    for i in [0, 501]:
        if i in output_set:
            raise ValueError(f'{i} found')


@pytest.mark.asyncio
async def test_for_each_huge_tuple():
    input_list = list(range(1, 500))

    output_value_set = set()
    output_i_set = set()

    def f_func(i, value):
        output_value_set.add(value)
        output_i_set.add(i)

    await for_each(enumerate(input_list), f_func, limit=70)

    for i in input_list:
        if i not in output_value_set:
            raise ValueError(f'{i} not found')
    for i in [0, 501]:
        if i in output_value_set:
            raise ValueError(f'{i} found')
