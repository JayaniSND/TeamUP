"""Service layer: Supabase data access + the HTTP Orchestrator brain.

  athlete_context      — reusable, read-only Supabase queries for one athlete.
  orchestrator_service — the orchestrator brain reachable over HTTP (loads
                         athlete context, classifies intent, routes to the
                         specialist analysis functions, composes one answer).
"""
