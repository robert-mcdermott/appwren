"""The inventory. Importing it registers each record type's own behavior."""

import appwren.landscape  # noqa: F401  (the record types of the landscape, and theirs)
from appwren.inventory import applications, parts  # noqa: F401  (each type's hooks)
