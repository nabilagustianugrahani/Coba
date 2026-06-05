"""Integrations package — adapters for social media + e-commerce.

Architecture:
  VPS side (this package is imported there):
    - base.py: PlatformAdapter abstract class
    - registry.py: auto-discovery
    - dispatcher.py: routes heavy work to codespace
  
  Codespace side (executed via runner.py):
    - social_dispatch.py: real social media implementations
    - ecom_dispatch.py: real e-commerce implementations
  
  Heavy work NEVER runs on VPS. The dispatcher serializes requests, sends
  them to codespace via gh codespace ssh, and returns JSON results.
"""
