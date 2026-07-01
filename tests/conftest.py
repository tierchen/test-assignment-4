import pytest

from tests.fixtures.fakes import FakeRepo


@pytest.fixture
def repo() -> FakeRepo:
    return FakeRepo()
