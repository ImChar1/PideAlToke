import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_defaults_y_lista_de_brokers():
    s = Settings(AZURE_TENANT_ID="t", AZURE_CLIENT_ID="c", KAFKA_BOOTSTRAP_SERVERS="a:1,b:2,c:3")
    assert s.KAFKA_BOOTSTRAP_SERVERS.split(",") == ["a:1", "b:2", "c:3"]
    assert s.KAFKA_REQUEST_TIMEOUT_SECONDS == 10.0


def test_timeout_debe_ser_positivo():
    with pytest.raises(ValidationError):
        Settings(AZURE_TENANT_ID="t", AZURE_CLIENT_ID="c", KAFKA_REQUEST_TIMEOUT_SECONDS=0)
