from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import ConnectionMode
from app.domain.models import InstrumentEndpoint, InstrumentSetup
from app.infrastructure.instruments.awg_adapter import EquipsAwgAdapter
from app.infrastructure.instruments.osc_adapter import EquipsOscAdapter
from app.infrastructure.instruments.ports import AwgPort, OscPort


@dataclass(slots=True)
class InstrumentPorts:
    awg: AwgPort
    osc: OscPort
    awg_address: str
    osc_address: str



def resolve_visa_address(endpoint: InstrumentEndpoint) -> str:
    if endpoint.connect_mode == ConnectionMode.LAN and endpoint.ip_address.strip():
        return f"TCPIP0::{endpoint.ip_address.strip()}::INSTR"
    return endpoint.visa_address.strip()



def create_instrument_ports(setup: InstrumentSetup) -> InstrumentPorts:
    awg_address = resolve_visa_address(setup.awg)
    osc_address = resolve_visa_address(setup.osc)

    awg = EquipsAwgAdapter(model=setup.awg.model, visa_address=awg_address)
    osc = EquipsOscAdapter(model=setup.osc.model, visa_address=osc_address)
    return InstrumentPorts(awg=awg, osc=osc, awg_address=awg_address, osc_address=osc_address)
