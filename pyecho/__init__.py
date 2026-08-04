"""pyecho - Python interface for ECHO2D electromagnetic wakefield solver."""

from pyecho._version import __version__

# Core API - lazy imports to avoid circular dependencies
__all__ = [
    "__version__",
    # config
    "ECHO2DParams",
    "load_params",
    "save_params",
    # geometry
    "RoundGeometry",
    "FlatGeometry",
    "load_geometry",
    # runner
    "ECHO2DRunner",
    "BatchRunner",
    # parser
    "OutputLoader",
    # postprocess
    "PostProcessor",
    "WakeResult",
    "FlatWakeResult",
    # preprocess
    "InitialFieldGenerator",
    "ASTRAConverter",
    "create_beam_profile",
    "parse_beam_profile",
    # visualize
    "plot_wake_round",
    "plot_flat_wake",
    "plot_field",
    "plot_geometry",
    "plot_comparison",
    "plot_wake_modes",
    # export
    "export_hdf5",
    # project (Phase 1)
    "ProjectManifest",
    "RunManifest",
    "SubRunInfo",
    "ProcessedSummary",
    "init_project",
    "load_project",
    "save_project",
    "scan_workspace",
    "migrate_project",
    "list_runs",
    "is_echo2d_project",
    "is_legacy_project",
    "find_project_root",
    "create_new_run",
    "update_run_status",
    "MANIFEST_FILE",
    "RUN_META_FILE",
    "DEFAULT_WORKSPACE",
    # shortcuts
    "quick_simulate",
    "quick_postprocess",
    "compare_runs",
]


def __getattr__(name):
    """Lazy imports for public API."""
    _imports = {
        "ECHO2DParams": "pyecho.config",
        "load_params": "pyecho.config",
        "save_params": "pyecho.config",
        "RoundGeometry": "pyecho.geometry",
        "FlatGeometry": "pyecho.geometry",
        "load_geometry": "pyecho.geometry",
        "ECHO2DRunner": "pyecho.runner",
        "BatchRunner": "pyecho.runner",
        "OutputLoader": "pyecho.parser",
        "PostProcessor": "pyecho.postprocess.core",
        "WakeResult": "pyecho.datamodel",
        "FlatWakeResult": "pyecho.datamodel",
        "InitialFieldGenerator": "pyecho.preprocess.field",
        "ASTRAConverter": "pyecho.preprocess.particles",
        "create_beam_profile": "pyecho.preprocess.particles",
        "parse_beam_profile": "pyecho.preprocess.particles",
        "plot_wake_round": "pyecho.visualize",
        "plot_flat_wake": "pyecho.visualize",
        "plot_field": "pyecho.visualize",
        "plot_geometry": "pyecho.visualize",
        "plot_comparison": "pyecho.visualize",
        "plot_wake_modes": "pyecho.visualize",
        "export_hdf5": "pyecho.io.hdf5",
        "quick_simulate": "pyecho.api",
        "quick_postprocess": "pyecho.api",
        "compare_runs": "pyecho.api",
        # project (Phase 1)
        "ProjectManifest": "pyecho.project",
        "RunManifest": "pyecho.project",
        "SubRunInfo": "pyecho.project",
        "ProcessedSummary": "pyecho.project",
        "init_project": "pyecho.project",
        "load_project": "pyecho.project",
        "save_project": "pyecho.project",
        "scan_workspace": "pyecho.project",
        "migrate_project": "pyecho.project",
        "list_runs": "pyecho.project",
        "is_echo2d_project": "pyecho.project",
        "is_legacy_project": "pyecho.project",
        "find_project_root": "pyecho.project",
        "create_new_run": "pyecho.project",
        "update_run_status": "pyecho.project",
        "MANIFEST_FILE": "pyecho.project",
        "RUN_META_FILE": "pyecho.project",
        "DEFAULT_WORKSPACE": "pyecho.project",
    }
    if name in _imports:
        import importlib
        mod = importlib.import_module(_imports[name])
        attr = getattr(mod, name)
        globals()[name] = attr
        return attr
    raise AttributeError(f"module 'pyecho' has no attribute '{name}'")
