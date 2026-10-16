import multiprocessing

import pytest


@pytest.fixture(params=["fork", "spawn"])
def start_method(request):
    """Run the test under each start method this platform allows."""
    if request.param not in multiprocessing.get_all_start_methods():
        pytest.skip(f"{request.param} not available here")
    previous = multiprocessing.get_start_method(allow_none=True)  # None: not chosen yet
    multiprocessing.set_start_method(request.param, force=True)
    yield request.param
    multiprocessing.set_start_method(previous, force=True)
