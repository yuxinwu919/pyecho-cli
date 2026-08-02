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
    }
    if name in _imports:
        import importlib
        mod = importlib.import_module(_imports[name])
        attr = getattr(mod, name)
        globals()[name] = attr
        return attr
    raise AttributeError(f"module 'pyecho' has no attribute '{name}'")
