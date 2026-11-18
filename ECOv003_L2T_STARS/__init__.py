try:
    from . import _stars_rust
except ImportError as exc:
    raise ImportError(
        "ECOv003-L2T-STARS requires the compiled '_stars_rust' extension. "
        "Run 'make install' or 'maturin develop --release' in a source checkout."
    ) from exc

from .version import __version__
from .main import *
from .ECOv003_DL import *
from .smoke_test import test, test_python, test_rust, test_julia
from .install_julia import install_julia
