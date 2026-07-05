"""CAM model identity — storage metadata only (IVS-1.1).

Deliberately outside predictive.py: the model is under MODEL FREEZE (D-005)
and must not be modified for metadata concerns. This constant is stamped on
predictive_setups and setup_outcomes at creation time so every outcome can
be attributed to the model that produced it.

Bump this value when (and only when) the model itself changes.
NULL in the database means the row predates version tracking.
"""

CAM_MODEL_VERSION = "CAM_V2.7_FREEZE"
