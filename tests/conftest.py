"""Yhteiset pytest-fixturet."""
import pytest
from django.test import RequestFactory as DjangoRequestFactory


@pytest.fixture
def rf():
    return DjangoRequestFactory()
