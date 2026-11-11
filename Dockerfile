# Using Debian-based python:3.13.2-bookworm base image
FROM python:3.10.16-bookworm as base
ENV HOME /root

FROM base as environment

# Update Debian and install required dependencies
RUN apt-get update && apt-get install -y --no-install-recommends tzdata wget fish ca-certificates

# Install Julia
ENV JULIA_VERSION=1.11.6
RUN wget -q https://julialang-s3.julialang.org/bin/linux/x64/1.11/julia-$JULIA_VERSION-linux-x86_64.tar.gz \
    && tar -xzf julia-$JULIA_VERSION-linux-x86_64.tar.gz -C /opt \
    && ln -s /opt/julia-$JULIA_VERSION/bin/julia /usr/local/bin/julia \
    && rm julia-$JULIA_VERSION-linux-x86_64.tar.gz

RUN pip install --upgrade pip
RUN pip install tomli

FROM environment as installation

# Creating directory inside container to store PGE code
RUN mkdir /app

# Copying current snapshot of PGE code repository into container
COPY . /app/

# Running pip install using pyproject.toml
COPY pyproject.toml /app/pyproject.toml
WORKDIR /app

# FROM dependencies as build
FROM installation as build
RUN make install
# Julia must match the version in the Manifest.toml files; fail the build if any Julia package or import is broken
RUN make test-julia
RUN rm -rvf build; rm -rvf dist; rm -rvf *.egg-