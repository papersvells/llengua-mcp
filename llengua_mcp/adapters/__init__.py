"""Adaptadors de les fonts lingüístiques."""

from llengua_mcp.adapters.bdlex import BdlexAdapter
from llengua_mcp.adapters.ctilc import CtilcAdapter
from llengua_mcp.adapters.diec import DiecAdapter
from llengua_mcp.adapters.esadir import EsadirAdapter
from llengua_mcp.adapters.optimot import OptimotAdapter
from llengua_mcp.adapters.softcatala import SoftcatalaAdapter

__all__ = [
    "BdlexAdapter",
    "CtilcAdapter",
    "DiecAdapter",
    "EsadirAdapter",
    "OptimotAdapter",
    "SoftcatalaAdapter",
]
