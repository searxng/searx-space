# pylint: disable=unused-argument, redefined-outer-name
import asyncio
import pytest

import searxstats.common.utils as utils


def test_dict_update():
    values = dict()
    utils.dict_update(values, ['A'], 12)
    assert values['A'] == 12

    utils.dict_update(values, ['B', 'C'], 13)
    assert values['B']['C'] == 13

    utils.dict_update(values, ['D'], {
        'U': 14,
        'V': 15
    })
    assert values['D']['U'] == 14
    assert values['D']['V'] == 15


def dummy_function(first, second=None):
    return (first, second)


async def dummy_coroutine(first, second=None):
    await asyncio.sleep(0.01)
    return (first, second)


def dummy_raise_exception():
    raise ValueError('excepted exception')


@pytest.fixture
def task_list_with_exception(event_loop):
    tasks = []
    tasks.append(utils.create_task(event_loop, None, dummy_coroutine, 12, second=42))
    tasks.append(utils.create_task(event_loop, None, dummy_raise_exception))
    return tasks


@pytest.fixture
def simple_task_list(event_loop):
    tasks = []
    tasks.append(utils.create_task(event_loop, None, dummy_coroutine, 12, second=42))
    return tasks


@pytest.mark.asyncio
@pytest.mark.parametrize("dummy", [dummy_function, dummy_coroutine])
async def test_create_task(event_loop, dummy):
    first, second = await utils.create_task(event_loop, None, dummy, 12)
    assert first == 12
    assert second is None

    first, second = await utils.create_task(event_loop, None, dummy, 12, second=42)
    assert first == 12
    assert second == 42


@pytest.mark.asyncio
async def test_wait_tasks_empty():
    tasks = []

    results = await utils.wait_get_results(*tasks)

    assert len(results) == 0


@pytest.mark.asyncio
async def test_wait_tasks_ok(event_loop, simple_task_list):
    results = await utils.wait_get_results(*simple_task_list)

    assert len(results) == 1
    assert results.pop() == (12, 42)


@pytest.mark.asyncio
async def test_wait_tasks_exception(event_loop, task_list_with_exception):
    with pytest.raises(ValueError):
        await utils.wait_get_results(*task_list_with_exception)


def test_exception_to_str():
    assert utils.exception_to_str(ValueError('test')) == 'test'
    assert utils.exception_to_str(ValueError(utils.ERROR_REMOVE_PREFIX + 'test')) == 'test'
    assert utils.exception_to_str(ValueError('')) == 'ValueError'
