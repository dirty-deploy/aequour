"""Aequour HTTP API around the existing photo pipeline and the deterministic engine.
The API adds no pricing logic: every rupee comes from autosettle_engine. Customer routes never return the ceiling,
the pivots or internal assumptions."""
