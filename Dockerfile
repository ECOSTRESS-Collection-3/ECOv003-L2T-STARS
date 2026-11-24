# syntax=docker/dockerfile:1.6

# ==============================================================================
# STAGE 1: Conda-Forge Scientific & GDAL Toolchain + Rust Compiler
# ==============================================================================
FROM mambaorg/micromamba:ubuntu24.04 AS toolchain

USER root

ENV VIRTUAL_ENV=/opt/venv \
    MAMBA_ROOT_PREFIX=/opt/conda \
    MAMBA_EXTRACT_THREADS=2 \
    RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH="/opt/venv/bin:/usr/local/cargo/bin:$PATH"

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        fish \
        git \
        pkg-config \
        tzdata \
        wget

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal

RUN --mount=type=cache,target=/opt/conda/pkgs/cache \
    ln -sfn "$(which micromamba)" /usr/local/bin/mamba && \
    micromamba create -y -v -p /opt/venv -c conda-forge \
        python=3.12 \
        pip \
        "setuptools<81" \
        wheel \
        libgdal-netcdf \
        libgdal-hdf5 \
        "rasterio~=1.5.2" \
        pyproj \
        "shapely~=2.2.0" \
        "h5py~=3.14.0" \
        "matplotlib-base~=3.10.9" \
        "pandas~=3.1.1" \
        "scipy~=1.18.1" \
        "scikit-learn~=1.9.1" \
        "numpy~=2.5.4" && \
    micromamba clean -a -y && \
    python --version && \
    mamba --version && \
    rustc --version

# Optional legacy Julia runtime (disabled by default; pass --build-arg INCLUDE_JULIA=1 to enable)
ARG INCLUDE_JULIA=0
ENV JULIA_VERSION=1.11.6
RUN if [ "$INCLUDE_JULIA" = "1" ]; then \
        wget -q https://julialang-s3.julialang.org/bin/linux/x64/1.11/julia-$JULIA_VERSION-linux-x86_64.tar.gz \
        && tar -xzf julia-$JULIA_VERSION-linux-x86_64.tar.gz -C /opt \
        && ln -s /opt/julia-$JULIA_VERSION/bin/julia /usr/local/bin/julia \
        && rm julia-$JULIA_VERSION-linux-x86_64.tar.gz; \
    fi

# ==============================================================================
# STAGE 2: Package Build & Dependencies (Installed into /opt/venv)
# ==============================================================================
FROM toolchain AS build

WORKDIR /tmp/src

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip "maturin>=1.8,<2.0" tomli

# 1. Install third-party & dev dependencies first (cached unless pyproject.toml changes)
COPY ./pyproject.toml /tmp/src/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/pip \
    pip list --format=freeze | grep -E '^(numpy|scipy|rasterio|shapely|h5py|pandas|matplotlib|pyproj|scikit-learn)==' > /tmp/conda-constraints.txt && \
    python -c "import tomllib; d = tomllib.load(open('pyproject.toml', 'rb')); deps = d['project']['dependencies'] + d['project'].get('optional-dependencies', {}).get('dev', []); open('/tmp/reqs.txt', 'w').write('\n'.join(deps))" && \
    pip install \
      --upgrade-strategy only-if-needed \
      -c /tmp/conda-constraints.txt \
      -r /tmp/reqs.txt && \
    rm -f /tmp/reqs.txt

# 2. Build Rust extension and install ECOv003-L2T-STARS
COPY . /tmp/src/
RUN LD_LIBRARY_PATH=/opt/venv/lib cargo test --locked --release && \
    pip install --no-cache-dir --no-deps . && \
    rm -rf /tmp/src /tmp/conda-constraints.txt

# ==============================================================================
# STAGE 3: Runtime Image
# ==============================================================================
FROM build AS runtime

ENV TZ=UTC \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1 \
    MPLCONFIGDIR=/opt/matplotlib \
    GDAL_DRIVER_PATH="/opt/venv/lib/gdalplugins" \
    GDAL_DATA="/opt/venv/share/gdal" \
    PROJ_DATA="/opt/venv/share/proj" \
    SHELL=/usr/bin/fish

RUN mkdir -p /opt/matplotlib /etc/fish && \
    chsh -s /usr/bin/fish root && \
    micromamba shell init -s fish -r /opt/conda && \
    micromamba shell init -s bash -r /opt/conda && \
    printf '\nset -gx PATH /opt/venv/bin /usr/local/bin $PATH\n' >> /etc/fish/config.fish && \
    ECOv003-L2T-STARS test && \
    python -c "import matplotlib.font_manager" && \
    find /opt/venv /opt/matplotlib \
        \( -type d ! -perm -a+rx -o -type f ! -perm -a+r \) \
        -exec chmod a+rX {} +

WORKDIR /root

ENTRYPOINT []
CMD ["/usr/bin/fish"]
