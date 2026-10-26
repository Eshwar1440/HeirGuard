"""M1: hypothetical estate packets (specimen PDFs + truth.json) for tests and the demo."""

from hg.data_gen.packets import PACKETS, build_packet, generate_all, load_truth
from hg.data_gen.truth import PacketTruth, PlantedError

__all__ = ["PACKETS", "PacketTruth", "PlantedError", "build_packet", "generate_all", "load_truth"]
