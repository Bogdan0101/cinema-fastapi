import os
import pytest
from src.config.settings import settings


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    os.environ["TESTING"] = "True"
    settings.__init__(TESTING=True)
    print(f"\n✅ Test Session Started. Database: {settings.database_url}")
