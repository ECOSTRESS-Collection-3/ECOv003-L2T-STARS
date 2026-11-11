# ==============================================================================
# DEBUG SCRIPT: GDALDriver::Create() Failure in STARS L2T Fusion Pipeline
# ==============================================================================
#
# CONTEXT & ROOT CAUSE ANALYSIS:
# ------------------------------
# 1. Pipeline Failure:
#    - Python orchestrator (L2T_STARS.py -> process_STARS_product.py:284) expects:
#      /Users/halverso/data/ECOv003_testing/L2T_STARS_MODEL/11SPS/2026-10-10/STARS_NDVI_2026-10-10_11SPS_70m.tif
#    - Downstream fails with: `OSError: raster file not found` because the upstream
#      Julia step crashed before the file could be written to disk.
#
# 2. Originating Julia Stacktrace:
#    - File: process_ECOSTRESS_data_fusion_distributed_bias.jl, line 404
#    - Error: GDALError (CE_Failure, code 6):
#             GDALDriver::Create() ... no create method implemented for this format.
#    - Call Path:
#        Rasters.write(filename, raster; force=true)
#          -> RastersArchGDALExt._create_with_driver(...)
#          -> ArchGDAL.create(f, args...; driver, options, width, height, nbands, dtype)
#          -> ArchGDAL.gdalcreatecopy / GDAL.GDALCreateCopy
#          -> GDALDriver::Create() throws CE_Failure (code 6)
#
# 3. Known Root Causes & Diagnostic Angles:
#    - Cause A: Driver Inference Fallback
#      Rasters.jl attempts to infer the driver from ".tif". If driver detection
#      resolves to an incorrect driver or an in-memory/read-only driver (or leaves
#      it ambiguous), GDAL falls back to a driver that lacks direct `Create` support
#      (only supporting `CreateCopy` or read operations).
#    - Cause B: Mamba / Conda vs. Julia GDAL_jll Dylib Pollution
#      The parent workflow runs under a Mamba environment:
#      `/Users/halverso/.local/share/mamba/envs/ECOv003-L2T-STARS/`
#      If Conda/Mamba exports GDAL_DATA, GDAL_DRIVER_PATH, or library search paths
#      into the process environment, Julia's `GDAL_jll` may load incompatible dynamic
#      driver plugins or fail internal driver registrations on macOS (DYLD path conflicts).
#    - Cause C: Data Type / Band Mismatch in Template Creation
#      `raster` is a 3D Float64 array with dimensions (X, Y, Band(1:1)), where X and Y
#      contain Projected coordinates and WKT CRS metadata. If the memory template dataset
#      cannot be instantiated with direct `Create()`, `CreateCopy()` must be used.
#
# POTENTIAL WORKAROUNDS & FIXES:
# ------------------------------
# - Solution 1: Explicitly pass `driver="GTiff"` to `Rasters.write(...)`.
# - Solution 2: Clear inherited GDAL / PROJ environment variables before calling Julia.
# - Solution 3: Direct write using `ArchGDAL.create` or `ArchGDAL.copy` if `Rasters.write`
#   remains blocked by the internal `RastersArchGDALExt` driver dispatch logic.
# ==============================================================================

using Rasters
import ArchGDAL
using STARSDataFusion.sentinel_tiles

println("="^70)
println("1. ENVIRONMENT & GDAL DRIVER AUDIT")
println("="^70)

# Check for environment variables set by Conda/Mamba that could pollute GDAL_jll
for env_var in ["GDAL_DATA", "GDAL_DRIVER_PATH", "PROJ_DATA", "PROJ_LIB", "DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH"]
    val = get(ENV, env_var, "<not set>")
    println("  $(rpad(env_var, 28)) = $val")
end

println("\nInspecting GTiff Driver Capabilities:")
gtiff = ArchGDAL.getdriver("GTiff")
dcap_create     = ArchGDAL.metadata(gtiff, "DCAP_CREATE")
dcap_createcopy = ArchGDAL.metadata(gtiff, "DCAP_CREATECOPY")

println("  Driver Short Name:          ", ArchGDAL.shortname(gtiff))
println("  Driver Long Name:           ", ArchGDAL.longname(gtiff))
println("  Supports DCAP_CREATE:       ", dcap_create == "YES" ? "YES (Direct Create supported)" : "NO ($dcap_create)")
println("  Supports DCAP_CREATECOPY:   ", dcap_createcopy == "YES" ? "YES (CreateCopy supported)" : "NO ($dcap_createcopy)")

# Check driver inference on target file pattern
test_path = "STARS_NDVI_2026-10-10_11SPS_70m.tif"
identified_driver = ArchGDAL.identifydriver(test_path)
println("\nDriver Inference Check:")
println("  Filename:                   ", test_path)
println("  Resolved Driver:            ", ArchGDAL.shortname(identified_driver))

println("\n" * "="^70)
println("2. PREPARING REPRODUCTION DATASET (MATCHING LINE 404 STACKTRACE)")
println("="^70)

# Exact spatial grid: Tile 11SPS @ 70m resolution, 3D Float64 with single Band and NaN missingval
x, y = sentinel_tile_dims("11SPS", 70)
data = fill(0.12, length(x), length(y), 1)
raster = Raster(data, dims=(x, y, Band(1:1)), missingval=NaN)

println("  Raster Size:      ", size(raster))
println("  Data Type:        ", eltype(raster))
println("  Missing Value:    ", missingval(raster))
println("  Dimensions:       ", map(name, dims(raster)))

println("\n" * "="^70)
println("3. TESTING WRITE WORKFLOWS")
println("="^70)

mktempdir() do dir
    # -------------------------------------------------------------------------
    # TEST A: Default Rasters.write (Exact replica of current line 404)
    # -------------------------------------------------------------------------
    output_a = joinpath(dir, "STARS_NDVI_test_default.tif")
    @info "Test A: Default Rasters.write (inferred driver)..." output_a
    try
        Rasters.write(output_a, raster; force=true)
        @info "✓ Test A succeeded: Default write works in isolation."
    catch e
        @error "✗ Test A failed: Reproduced line 404 failure." exception=(e, catch_backtrace())
    end

    # -------------------------------------------------------------------------
    # TEST B: Explicit GTiff Driver Argument
    # Fix hypothesis: Avoids faulty extension detection in RastersArchGDALExt
    # -------------------------------------------------------------------------
    output_b = joinpath(dir, "STARS_NDVI_test_explicit_driver.tif")
    @info "Test B: Rasters.write with explicit driver=\"GTiff\"..." output_b
    try
        Rasters.write(
            output_b, 
            raster; 
            driver="GTiff",
            options=["COMPRESS=DEFLATE", "TILED=YES"],
            force=true
        )
        @info "✓ Test B succeeded: Explicit driver solves the issue."
    catch e
        @error "✗ Test B failed: Driver override did not resolve the error." exception=(e, catch_backtrace())
    end

    # -------------------------------------------------------------------------
    # TEST C: Direct ArchGDAL Dataset Creation Fallback
    # Fix hypothesis: Bypasses RastersArchGDALExt write translation entirely
    # -------------------------------------------------------------------------
    output_c = joinpath(dir, "STARS_NDVI_test_archgdal_direct.tif")
    @info "Test C: Direct ArchGDAL.create write fallback..." output_c
    try
        ArchGDAL.create(
            output_c;
            driver=ArchGDAL.getdriver("GTiff"),
            width=size(raster, 1),
            height=size(raster, 2),
            nbands=size(raster, 3),
            dtype=Float64
        ) do ds
            band = ArchGDAL.getband(ds, 1)
            ArchGDAL.write!(band, raster[:, :, 1])
        end
        @info "✓ Test C succeeded: Direct ArchGDAL write bypassed the error."
    catch e
        @error "✗ Test C failed: ArchGDAL direct write also failed." exception=(e, catch_backtrace())
    end
end

println("="^70)
println("DEBUG RUN COMPLETE")
println("="^70)