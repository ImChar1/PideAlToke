# Validacion con Pydantic: nombres vacios o raros y configuraciones imposibles se rechazan (422)
# antes de tocar el broker.

from pydantic import ValidationError
import pytest

from app.schemas.schema_rabbitmq import BindingCrearSchema, ColaCrearSchema, ExchangeCrearSchema


def _invalido(clase, **datos):
    with pytest.raises(ValidationError):
        clase(**datos)


# ------------------------------------------------------------------ nombres

def test_nombres_validos_se_aceptan():
    for nombre in ["q", "inventario.pedidos", "inventario.pedidos.dlq", "mi-cola_1:a", "A" * 255]:
        assert ColaCrearSchema(name=nombre).name == nombre


def test_nombre_vacio_o_solo_espacios_se_rechaza():
    for nombre in ["", " ", "   ", "\t"]:
        _invalido(ColaCrearSchema, name=nombre)
        _invalido(ExchangeCrearSchema, name=nombre, type="direct")


def test_nombre_con_caracteres_no_permitidos_se_rechaza():
    for nombre in ["con espacio", "a/b", "a\\b", "a'b", 'a"b', "a\nb", "ñandu", " lead", "trail "]:
        _invalido(ColaCrearSchema, name=nombre)


def test_nombre_demasiado_largo_se_rechaza():
    _invalido(ColaCrearSchema, name="a" * 256)


def test_prefijo_amq_esta_reservado_al_declarar():
    _invalido(ColaCrearSchema, name="amq.mi-cola")
    _invalido(ExchangeCrearSchema, name="AMQ.mi-exchange", type="topic")


def test_amq_si_se_puede_referenciar_en_bindings_y_dlx():
    b = BindingCrearSchema(queue="q", exchange="amq.topic", routing_key="a.*")
    assert b.exchange == "amq.topic"
    assert ColaCrearSchema(name="q", dead_letter_exchange="amq.direct").dead_letter_exchange == "amq.direct"


# ------------------------------------------------------------------ colas

def test_cola_con_defaults_es_durable_y_classic():
    c = ColaCrearSchema(name="q")
    assert (c.durable, c.auto_delete, c.queue_type) == (True, False, "classic")


def test_cola_con_dlq_completa_es_valida():
    c = ColaCrearSchema(
        name="q", message_ttl_ms=60000, max_length=1000,
        dead_letter_exchange="dlx", dead_letter_routing_key="q.dlq",
    )
    assert c.dead_letter_routing_key == "q.dlq"


def test_dead_letter_routing_key_sin_dead_letter_exchange_se_rechaza():
    _invalido(ColaCrearSchema, name="q", dead_letter_routing_key="q.dlq")


def test_valores_numericos_fuera_de_rango_se_rechazan():
    _invalido(ColaCrearSchema, name="q", message_ttl_ms=-1)
    _invalido(ColaCrearSchema, name="q", message_ttl_ms=4294967296)
    _invalido(ColaCrearSchema, name="q", max_length=0)


def test_cola_quorum_debe_ser_durable_y_sin_auto_delete():
    assert ColaCrearSchema(name="q", queue_type="quorum").queue_type == "quorum"
    _invalido(ColaCrearSchema, name="q", queue_type="quorum", durable=False)
    _invalido(ColaCrearSchema, name="q", queue_type="quorum", auto_delete=True)


def test_tipo_de_cola_desconocido_se_rechaza():
    _invalido(ColaCrearSchema, name="q", queue_type="lazy")


def test_campos_desconocidos_se_rechazan():
    _invalido(ColaCrearSchema, name="q", durabel=False)  # typo
    _invalido(BindingCrearSchema, queue="q", exchange="e", extra="x")


# ------------------------------------------------------------------ exchanges y bindings

def test_tipos_de_exchange_validos():
    for tipo in ["direct", "topic", "fanout", "headers"]:
        assert ExchangeCrearSchema(name="e", type=tipo).type == tipo


def test_tipo_de_exchange_invalido_o_ausente_se_rechaza():
    _invalido(ExchangeCrearSchema, name="e", type="broadcast")
    _invalido(ExchangeCrearSchema, name="e")


def test_binding_requiere_cola_y_exchange_no_vacios():
    _invalido(BindingCrearSchema, queue="", exchange="e")
    _invalido(BindingCrearSchema, queue="q", exchange="")


def test_binding_acepta_patrones_de_topic_y_routing_key_vacia():
    assert BindingCrearSchema(queue="q", exchange="e", routing_key="pedido.*").routing_key == "pedido.*"
    assert BindingCrearSchema(queue="q", exchange="e", routing_key="#").routing_key == "#"
    assert BindingCrearSchema(queue="q", exchange="e").routing_key == ""  # fanout


def test_routing_key_con_caracteres_invalidos_o_demasiado_larga_se_rechaza():
    _invalido(BindingCrearSchema, queue="q", exchange="e", routing_key="con espacio")
    _invalido(BindingCrearSchema, queue="q", exchange="e", routing_key="a" * 256)
