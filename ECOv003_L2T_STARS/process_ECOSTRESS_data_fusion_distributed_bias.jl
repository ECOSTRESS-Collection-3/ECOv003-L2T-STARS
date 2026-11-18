using Glob
using Dates
using Rasters
using LinearAlgebra
using STARSDataFusion
using STARSDataFusion.BBoxes
using STARSDataFusion.sentinel_tiles
using STARSDataFusion.HLS
using STARSDataFusion.VNP43
using Logging
using Statistics
using Distributed
using ArchGDAL

const SCRIPT_START_NS = time_ns()
elapsed_sec(t0_ns::UInt64) = round((time_ns() - t0_ns) / 1e9; digits=2)

struct CustomLogger <: AbstractLogger
    stream::IO
    min_level::LogLevel
end

Logging.min_enabled_level(logger::CustomLogger) = logger.min_level

function Logging.shouldlog(logger::CustomLogger, level, _module, group, id)
    return level >= logger.min_level
end

function Logging.handle_message(logger::CustomLogger, level, message, _module, group, id, file, line; kwargs...)
    t = Dates.format(now(), "yyyy-mm-dd HH:MM:SS")
    println(logger.stream, "[$t $(uppercase(string(level)))] [Julia] $message")
    flush(logger.stream)
end

global_logger(CustomLogger(stdout, Logging.Info))

@info "processing STARS data fusion"

wrkrs = parse(Int64, ARGS[1])

t_workers_start = time_ns()
@info "starting $(wrkrs) workers"
addprocs(wrkrs)

@everywhere using STARSDataFusion
@everywhere using LinearAlgebra
@everywhere BLAS.set_num_threads(1)
t_workers_sec = elapsed_sec(t_workers_start)
@info "worker startup and package loading completed in $(t_workers_sec) s"

DEFAULT_MEAN = 0.12
DEFAULT_SD = 0.01

DEFAULT_BIAS_MEAN = 0.0
DEFAULT_BIAS_SD = 0.001

tile = ARGS[2]
@info "tile: $(tile)"
coarse_cell_size = parse(Int64, ARGS[3])
@info "coarse cell size: $(coarse_cell_size)"
fine_cell_size = parse(Int64, ARGS[4])
@info "fine cell size: $(fine_cell_size)"
VIIRS_start_date = Date(ARGS[5])
@info "VIIRS start date: $(VIIRS_start_date)"
VIIRS_end_date = Date(ARGS[6])
@info "VIIRS end date: $(VIIRS_end_date)"
HLS_start_date = Date(ARGS[7])
@info "HLS start date: $(HLS_start_date)"
HLS_end_date = Date(ARGS[8])
@info "HLS end date: $(HLS_end_date)"
downsampled_directory = ARGS[9]
@info "downsampled inputs directory: $(downsampled_directory)"
product_name = ARGS[10]
@info "computing $(product_name) product"
posterior_filename = ARGS[11]
@info "posterior filename: $(posterior_filename)"
posterior_UQ_filename = ARGS[12]
@info "posterior UQ filename: $(posterior_UQ_filename)"
posterior_flag_filename = ARGS[13]
@info "posterior flag filename: $(posterior_flag_filename)"
posterior_bias_filename = ARGS[14]
@info "posterior bias filename: $(posterior_bias_filename)"
posterior_bias_UQ_filename = ARGS[15]
@info "posterior bias UQ filename: $(posterior_bias_UQ_filename)"

function read_raster_logged(label::String, filename::String)
    @info "reading $(label): $(filename)"
    return Raster(filename)
end

function to_float64_slice(r::AbstractArray, nx::Int, ny::Int)::Matrix{Float64}
    raw = parent(r)
    out = Matrix{Float64}(undef, nx, ny)
    @inbounds for idx in eachindex(out, raw)
        val = raw[idx]
        out[idx] = ismissing(val) ? NaN : Float64(val)
    end
    return out
end

t_inputs_start = time_ns()

x_coarse, y_coarse = sentinel_tile_dims(tile, coarse_cell_size)
x_coarse_size = size(x_coarse)[1]
y_coarse_size = size(y_coarse)[1]
@info "coarse x size: $(x_coarse_size)"
@info "coarse y size: $(y_coarse_size)"
x_fine, y_fine = sentinel_tile_dims(tile, fine_cell_size)
x_fine_size = size(x_fine)[1]
y_fine_size = size(y_fine)[1]
@info "fine x size: $(x_fine_size)"
@info "fine y size: $(y_fine_size)"

if size(ARGS)[1] >= 19
    prior_filename = ARGS[16]
    prior_mean = to_float64_slice(read_raster_logged("prior mean", prior_filename), x_fine_size, y_fine_size)
    prior_UQ_filename = ARGS[17]
    prior_sd = to_float64_slice(read_raster_logged("prior UQ", prior_UQ_filename), x_fine_size, y_fine_size)
    prior_bias_filename = ARGS[18]
    prior_bias_mean = to_float64_slice(read_raster_logged("prior bias", prior_bias_filename), x_coarse_size, y_coarse_size)
    prior_bias_UQ_filename = ARGS[19]
    prior_bias_sd = to_float64_slice(read_raster_logged("prior bias UQ", prior_bias_UQ_filename), x_coarse_size, y_coarse_size)
else
    @info "no prior files provided; using default prior initialization"
    prior_mean = nothing
end

# Build date -> filename lookups directly instead of repeated substring searches
coarse_start_date = VIIRS_start_date
coarse_end_date = VIIRS_end_date
coarse_dates_all = [coarse_start_date + Day(d - 1) for d in 1:((coarse_end_date - coarse_start_date).value + 1)]
coarse_file_by_date = Dict{String, String}()
for d in coarse_dates_all
    date_str = Dates.format(d, dateformat"yyyy-mm-dd")
    fn = joinpath(downsampled_directory, "$(year(d))", date_str, tile, "STARS_$(product_name)_$(tile)_$(coarse_cell_size)m.tif")
    if ispath(fn)
        coarse_file_by_date[date_str] = fn
    end
end

fine_flag_start_date = HLS_end_date - Day(7)
fine_start_date = HLS_start_date
fine_end_date = HLS_end_date

dates = [fine_start_date + Day(d - 1) for d in 1:((fine_end_date - fine_start_date).value + 1)]
all_fine_dates = [min(fine_flag_start_date, fine_start_date) + Day(d - 1) for d in 1:((fine_end_date - min(fine_flag_start_date, fine_start_date)).value + 1)]
fine_file_by_date = Dict{String, String}()
for d in all_fine_dates
    date_str = Dates.format(d, dateformat"yyyy-mm-dd")
    fn = joinpath(downsampled_directory, "$(year(d))", date_str, tile, "STARS_$(product_name)_$(tile)_$(fine_cell_size)m.tif")
    if ispath(fn)
        fine_file_by_date[date_str] = fn
    end
end

t = Ti(dates)
coarse_dims = (x_coarse, y_coarse, t)
fine_dims = (x_fine, y_fine, t)

# Pre-allocate covariance buffer and cache loaded coarse slices to avoid duplicate disk I/O
covariance_dates = coarse_dates_all
t_covariance = Ti(covariance_dates)
covariance_dims = (x_coarse, y_coarse, t_covariance)
covariance_buffer = fill(NaN, x_coarse_size, y_coarse_size, length(covariance_dates))
coarse_raster_cache = Dict{String, Matrix{Float64}}()

for (i, d) in enumerate(covariance_dates)
    date_str = Dates.format(d, dateformat"yyyy-mm-dd")
    filename = get(coarse_file_by_date, date_str, nothing)

    if filename === nothing
        @info "coarse covariance image is not available on $(date_str)"
    else
        raw_covariance = read_raster_logged("coarse covariance image on $(date_str)", filename)
        slice = to_float64_slice(raw_covariance, x_coarse_size, y_coarse_size)
        coarse_raster_cache[date_str] = slice
        covariance_buffer[:, :, i] .= slice
        @info "loaded covariance raster of size ($(x_coarse_size), $(y_coarse_size), 1)"
    end
end

@info "concatenating coarse images for covariance calculation"
covariance_images = Raster(covariance_buffer, dims=covariance_dims, missingval=NaN)

t_cov_est_start = time_ns()
n_eff = compute_n_eff(Int(round(coarse_cell_size / fine_cell_size)), 2, smoothness=1.5)
sp_var = fast_var_est(covariance_images, n_eff_agg = n_eff)
t_cov_est_sec = elapsed_sec(t_cov_est_start)
@info "spatial variance estimation completed in $(t_cov_est_sec) s"

# Assemble coarse fusion inputs from cache (no second disk read)
matched_coarse_dates = Date[]
matched_coarse_slices = Matrix{Float64}[]
for d in dates
    date_str = Dates.format(d, dateformat"yyyy-mm-dd")
    if haskey(coarse_raster_cache, date_str)
        push!(matched_coarse_dates, d)
        push!(matched_coarse_slices, coarse_raster_cache[date_str])
    else
        @info "coarse image is not available on $(date_str)"
    end
end

@info "concatenating coarse image inputs"
if isempty(matched_coarse_slices)
    coarse_array = fill(NaN, x_coarse_size, y_coarse_size, 1)
    coarse_dates = [dates[1]]
else
    coarse_dates = matched_coarse_dates
    coarse_array = Array{Float64, 3}(undef, x_coarse_size, y_coarse_size, length(coarse_dates))
    for (k, slice) in enumerate(matched_coarse_slices)
        coarse_array[:, :, k] .= slice
    end
end
coarse_images = Raster(coarse_array, dims=(coarse_dims[1:2]..., Band(1:length(coarse_dates))), missingval=NaN)

# Load fine fusion inputs into a pre-allocated 3D buffer
matched_fine_dates = Date[]
matched_fine_slices = Matrix{Float64}[]
for d in dates
    date_str = Dates.format(d, dateformat"yyyy-mm-dd")
    filename = get(fine_file_by_date, date_str, nothing)
    if filename === nothing
        @info "fine image is not available on $(date_str)"
    else
        raw_fine = read_raster_logged("fine image on $(date_str)", filename)
        slice = to_float64_slice(raw_fine, x_fine_size, y_fine_size)
        @info "loaded fine raster of size ($(x_fine_size), $(y_fine_size), 1)"
        push!(matched_fine_dates, d)
        push!(matched_fine_slices, slice)
    end
end

@info "concatenating fine image inputs"
if isempty(matched_fine_slices)
    fine_array = fill(NaN, x_fine_size, y_fine_size, 1)
    fine_dates = [dates[1]]
else
    fine_dates = matched_fine_dates
    fine_array = Array{Float64, 3}(undef, x_fine_size, y_fine_size, length(fine_dates))
    for (k, slice) in enumerate(matched_fine_slices)
        fine_array[:, :, k] .= slice
    end
end
fine_images = Raster(fine_array, dims=(fine_dims[1:2]..., Band(1:length(fine_dates))), missingval=NaN)

target_date = dates[end]
target_time = length(dates)

## 0, 1 mask
fine_pixels = sum(.!isnan.(fine_array), dims=3)
if sum(fine_pixels .== 0) > 0
    if fine_flag_start_date < fine_start_date
        flag_dates = [fine_flag_start_date + Day(d - 1) for d in 1:((fine_start_date - Day(1) - fine_flag_start_date).value + 1)]

        for d in flag_dates
            date_str = Dates.format(d, dateformat"yyyy-mm-dd")
            filename = get(fine_file_by_date, date_str, nothing)

            if filename === nothing
                @info "fine image for 7-day flag is not available on $(date_str)"
            else
                raw_flag_fine = read_raster_logged("fine image for 7-day flag on $(date_str)", filename)
                slice = to_float64_slice(raw_flag_fine, x_fine_size, y_fine_size)
                fine_pixels[:, :, 1] .+= .!isnan.(slice)
            end
        end
    end
end

hls_flag = Array(fine_pixels[:, :, 1] .== 0)

### nan pixels with no historical data
if isnothing(prior_mean)
    prior_flag = trues(x_fine_size, y_fine_size)
    fine_obs = sum(.!isnan.(fine_array), dims=3)
    if sum(fine_obs .== 0) > 0
        coarse_nans = resample(sum(.!isnan.(coarse_images), dims=3), to=fine_images[:, :, 1], method=:near)
        prior_flag[coarse_nans[:, :, 1] .> 0] .= false
    end
    prior_flag[fine_pixels[:, :, 1] .> 0] .= false
elseif sum(isnan.(prior_mean)) > 0
    prior_flag = isnan.(prior_mean[:, :, 1])
    fine_obs = sum(.!isnan.(fine_array), dims=3)
    if sum(fine_obs .== 0) > 0
        coarse_nans = resample(sum(.!isnan.(coarse_images), dims=3), to=fine_images[:, :, 1], method=:near)
        prior_flag[coarse_nans[:, :, 1] .> 0] .= false
    end
    prior_flag[fine_pixels[:, :, 1] .> 0] .= false
else
    prior_flag = falses(x_fine_size, y_fine_size)
end

t_inputs_sec = round(elapsed_sec(t_inputs_start) - t_cov_est_sec; digits=2)
@info "input loading and preprocessing completed in $(t_inputs_sec) s"

@info "running data fusion"
t_fusion_start = time_ns()

fine_times = findall(dates .∈ Ref(fine_dates))
coarse_times = findall(dates .∈ Ref(coarse_dates))

fine_ndims = collect(size(fine_images)[1:2])
coarse_ndims = collect(size(coarse_images)[1:2])

fine_origin = get_centroid_origin_raster(fine_images)
coarse_origin = get_centroid_origin_raster(coarse_images)

fine_csize = collect(cell_size(fine_images))
coarse_csize = collect(cell_size(coarse_images))

fine_geodata = STARSInstrumentGeoData(fine_origin, fine_csize, fine_ndims, 0, fine_times)
coarse_geodata = STARSInstrumentGeoData(coarse_origin, coarse_csize, coarse_ndims, 2, coarse_times)

fine_data = STARSInstrumentData(fine_array, 0.0, 1e-6, false, nothing, abs.(fine_csize), fine_times, [1. 1.])
coarse_data = STARSInstrumentData(coarse_array, 0.0, 1e-6, true, [1.0, 1e-6], abs.(coarse_csize), coarse_times, [1. 1.])

nsamp = 100
window_buffer = 4

cov_pars = ones((x_fine_size, y_fine_size, 4))

sp_rs = resample(log.(sqrt.(sp_var[:, :, 1])); to=fine_images[:, :, 1], size=(x_fine_size, y_fine_size), method=:cubicspline)
sp_rs[isnan.(sp_rs)] .= nanmean(sp_rs)

cov_pars[:, :, 1] = Array{Float64}(exp.(sp_rs))
cov_pars[:, :, 2] .= coarse_cell_size
cov_pars[:, :, 3] .= 1e-10
cov_pars[:, :, 4] .= 0.5

if isnothing(prior_mean)
    fused_images, fused_sd_images, fused_bias_images, fused_bias_sd_images = coarse_fine_scene_fusion_cbias_pmap(
        fine_data,
        coarse_data,
        fine_geodata,
        coarse_geodata,
        fill(DEFAULT_MEAN, fine_ndims...),
        fill(DEFAULT_SD^2, fine_ndims...),
        fill(DEFAULT_BIAS_MEAN, coarse_ndims...),
        fill(DEFAULT_BIAS_SD^2, coarse_ndims...),
        cov_pars;
        nsamp = nsamp,
        window_buffer = window_buffer,
        target_times = [target_time],
        spatial_mod = exp_cor,
        obs_operator = unif_weighted_obs_operator_centroid,
        state_in_cov = false,
        cov_wt = 0.2,
        nb_coarse = 2.0
    )
else
    nkp = isnan.(prior_mean)
    if sum(nkp) > 0
        mp = nanmean(prior_mean)
        prior_mean[nkp] .= mp
    end

    fused_images, fused_sd_images, fused_bias_images, fused_bias_sd_images = coarse_fine_scene_fusion_cbias_pmap(
        fine_data,
        coarse_data,
        fine_geodata,
        coarse_geodata,
        prior_mean,
        prior_sd.^2,
        prior_bias_mean,
        prior_bias_sd.^2,
        cov_pars;
        nsamp = nsamp,
        window_buffer = window_buffer,
        target_times = [target_time],
        spatial_mod = exp_cor,
        obs_operator = unif_weighted_obs_operator_centroid,
        state_in_cov = false,
        cov_wt = 0.2,
        nb_coarse = 2.0
    )
end

t_fusion_sec = elapsed_sec(t_fusion_start)
@info "data fusion completed in $(t_fusion_sec) s; removing workers"

t_rmprocs_start = time_ns()
rmprocs(workers())
t_rmprocs_sec = elapsed_sec(t_rmprocs_start)

if occursin("NDVI", posterior_filename)
    clamp!(fused_images, -1, 1)
else
    clamp!(fused_images, 0, 1)
end

dd = fused_images[:, :, :]
dd[prior_flag, :] .= NaN

# --- ROBUST GEOTIFF WRITER ---
function safe_write_geotiff(label::String, output_filename::String, template_filename::String, matrix_data::AbstractMatrix, nodata_val)
    mkpath(dirname(output_filename))
    @info "reading template GeoTIFF for $(label): $(template_filename)"
    @info "writing $(label) GeoTIFF: $(output_filename)"

    ArchGDAL.read(template_filename) do template_ds
        driver = ArchGDAL.getdriver("GTiff")
        gt = ArchGDAL.getgeotransform(template_ds)
        proj = ArchGDAL.getproj(template_ds)

        w, h = size(matrix_data, 1), size(matrix_data, 2)
        dtype = eltype(matrix_data)

        creation_options = ["COMPRESS=DEFLATE", "PREDICTOR=2", "TILED=YES"]

        ArchGDAL.create(output_filename; driver=driver, width=w, height=h, nbands=1, dtype=dtype, options=creation_options) do target_ds
            ArchGDAL.setgeotransform!(target_ds, gt)
            ArchGDAL.setproj!(target_ds, proj)
            band = ArchGDAL.getband(target_ds, 1)
            ArchGDAL.setnodatavalue!(band, nodata_val)
            ArchGDAL.write!(band, matrix_data)
        end
    end

    @info "wrote $(label) GeoTIFF: $(output_filename)"
end

t_write_start = time_ns()

fine_template = if !isempty(fine_file_by_date)
    first(values(fine_file_by_date))
elseif ispath(posterior_filename)
    posterior_filename
else
    first(glob("*_$(fine_cell_size)m.tif", downsampled_directory))
end
@info "selected fine template GeoTIFF: $(fine_template)"

coarse_template = if !isempty(coarse_file_by_date)
    first(values(coarse_file_by_date))
else
    first(glob("*_$(coarse_cell_size)m.tif", downsampled_directory))
end
@info "selected coarse template GeoTIFF: $(coarse_template)"

safe_write_geotiff("fused mean", posterior_filename, fine_template, Float32.(dd[:, :, 1]), NaN32)
safe_write_geotiff("fused flag", posterior_flag_filename, fine_template, Int32.(hls_flag), Int32(-9999))
safe_write_geotiff("fused SD", posterior_UQ_filename, fine_template, Float32.(fused_sd_images[:, :, 1]), NaN32)
safe_write_geotiff("bias mean", posterior_bias_filename, coarse_template, Float32.(fused_bias_images[:, :, 1]), NaN32)
safe_write_geotiff("bias SD", posterior_bias_UQ_filename, coarse_template, Float32.(fused_bias_sd_images[:, :, 1]), NaN32)

t_write_sec = elapsed_sec(t_write_start)
t_total_sec = elapsed_sec(SCRIPT_START_NS)

@info "timing summary ($(product_name), tile $(tile)): workers=$(t_workers_sec)s, inputs=$(t_inputs_sec)s, cov_est=$(t_cov_est_sec)s, fusion=$(t_fusion_sec)s, rmprocs=$(t_rmprocs_sec)s, write=$(t_write_sec)s, total=$(t_total_sec)s"
@info "finished STARS data fusion for $(product_name) at tile $(tile)"