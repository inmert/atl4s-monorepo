"""Online voxel-hash defect dedup, integrated into mesh-worker's bag-playback loop.

Public surface:
    from defects.state import DefectTracker
    from defects.grid  import VOXEL_M, build_T_cw, project_to_world

Per docs/DEFECT_DEDUP_ONLINE.md.
"""
from .grid import VOXEL_M, Voxel, build_T_cw, project_to_world, voxel_keys, group_by_voxel  # noqa: F401
from .state import DefectTracker, MIN_HITS, mint_defect_id  # noqa: F401
