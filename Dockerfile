# Using Debian-based python:3.12-bookworm base image
FROM python:3.12-bookworm AS base
ENV HOME=/root

FROM base AS environment

# Update Debian and install required system dependencies + Rust toolchain for building _stars_rust
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata wget curl ca-certificates build-essential pkg-config libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal

# Optional legacy Julia runtime (disabled by default; pass --build-arg INCLUDE_JULIA=1 to enable)
ARG INCLUDE_JULIA=0
ENV JULIA_VERSION=1.11.6
RUN if [ "$INCLUDE_JULIA" = "1" ]; then \
        wget -q https://julialang-s3.julialang.org/bin/linux/x64/1.11/julia-$JULIA_VERSION-linux-x86_64.tar.gz \
        && tar -xzf julia-$JULIA_VERSION-linux-x86_64.tar.gz -C /opt \
        && ln -s /opt/julia-$JULIA_VERSION/bin/julia /usr/local/bin/julia \
        && rm julia-$JULIA_VERSION-linux-x86_64.tar.gz; \
    fi

RUN pip install --upgrade pip && pip install "maturin>=1.7,<2.0" tomli

FROM environment AS installation

RUN mkdir /app
COPY . /app/
WORKDIR /app

FROM installation AS build
RUN make test-rust && pip install --no-cache-dir .
RUN ECOv003-L2T-STARS test
RUN if [ "$INCLUDE_JULIA" = "1" ]; then make test-julia; fi
RUN rm -rf build dist target *.egg-info
