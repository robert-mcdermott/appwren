"""The landscape around each application: interfaces and the data they carry, and (later in
the wave) where things run and what they cost. Importing it registers each record type's own
behavior."""

from appwren.landscape import costs, hosting, interfaces  # noqa: F401  (each type's hooks)
