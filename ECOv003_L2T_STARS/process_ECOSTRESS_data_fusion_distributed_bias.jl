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
using Pkg
using Statistics
using Distributed
Pkg.add("OpenSSL")
using HTTP
using JSON

function read_json(file::String)::Dict
    open(file, "r") do f
        return JSON.parse(f)
    end
end

function write_json(file::String, data::Dict)
    open(file, "w") do f
        JSON.print(f, data)
    end
end

@info "processing STARS data fusion"

wrkrs = parse(Int64, ARGS[1])
# wrkrs = 8

@info "starting $(wrkrs) workers"
addprocs(wrkrs) ## need to set num workers

@everywhere using STARSDataFusion
@everywhere using LinearAlgebra
@everywhere BLAS.set_num_threads(1)

DEFAULT_MEAN = 0.12
DEFAULT_SD = 0.01

#### add bias components
DEFAULT_BIAS_MEAN = 0.0
DEFAULT_BIAS_SD = 0.001

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
    println(logger.stream, "[$t $(uppercase(string(level)))] $message")
end

global_logger(CustomLogger(stdout, Logging.Info))

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
coarse_directory = ARGS[9]
@info "coarse inputs directory: $(coarse_directory)"
fine_directory = ARGS[10]
@info "fine inputs directory: $(fine_directory)"
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

if size(ARGS)[1] >= 19
    prior_filename = ARGS[16]
    @info "prior filename: $(prior_filename)"
    prior_mean = Array(Raster(prior_filename))
    prior_UQ_filename = ARGS[17]
    @info "prior UQ filename: $(prior_UQ_filename)"
    prior_sd = Array(Raster(prior_UQ_filename))
    prior_bias_filename = ARGS[18]
    @info "prior bias filename: $(prior_bias_filename)"
    prior_bias_mean = Array(Raster(prior_bias_filename))
    prior_bias_UQ_filename = ARGS[19]
    @info "prior bias UQ filename: $(prior_bias_UQ_filename)"
    prior_bias_sd = Array(Raster(prior_bias_UQ_filename))

    replace!(prior_bias_mean, missing => NaN)
    replace!(prior_bias_sd, missing => NaN)
    replace!(prior_mean, missing => NaN)
    replace!(prior_sd, missing => NaN)
    ## if we do flag as HLS observed within last 7 days then we don't depend on prior flags
    # prior_flag_filename = ARGS[20]
    # @info "prior flag filename: $(prior_flag_filename)"
    # prior_flag = Raster(prior_flag_filename)
else
    prior_mean = nothing
end

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

coarse_image_filenames = sort(glob("*.tif", coarse_directory))
coarse_dates_found = [Date(split(basename(filename), "_")[3]) for filename in coarse_image_filenames]

fine_image_filenames = sort(glob("*.tif", fine_directory))
fine_dates_found = [Date(split(basename(filename), "_")[3]) for filename in fine_image_filenames]

coarse_start_date = VIIRS_start_date
coarse_end_date = VIIRS_end_date

fine_flag_start_date = HLS_end_date - Day(7)
fine_start_date = HLS_start_date
fine_end_date = HLS_end_date

dates = [fine_start_date + Day(d - 1) for d in 1:((fine_end_date - fine_start_date).value + 1)]
t = Ti(dates)
coarse_dims = (x_coarse, y_coarse, t)
fine_dims = (x_fine, y_fine, t)

covariance_dates = [coarse_start_date + Day(d - 1) for d in 1:((coarse_end_date - coarse_start_date).value + 1)]
t_covariance = Ti(covariance_dates)
covariance_dims = (x_coarse, y_coarse, t_covariance)

covariance_images = []

for (i, date) in enumerate(covariance_dates)
    date = Dates.format(date, dateformat"yyyy-mm-dd")
    match = findfirst(x -> occursin(date, x), coarse_image_filenames)
    timestep_index = Band(i:i)
    timestep_dims = (x_coarse, y_coarse, timestep_index)

    if match === nothing
        @info "coarse image is not available on $(date)"
        covariance_image = Raster(fill(NaN, x_coarse_size, y_coarse_size, 1), dims=timestep_dims, missingval=NaN)
        @info size(covariance_image)
    else
        filename = coarse_image_filenames[match]
        @info "ingesting coarse image on $(date): $(filename)"
        covariance_image = Raster(reshape(Raster(filename), x_coarse_size, y_coarse_size, 1), dims=timestep_dims, missingval=NaN)
        replace!(covariance_image, missing => NaN)
        @info size(covariance_image)
    end

    push!(covariance_images, covariance_image)
end

@info "concatenating coarse images for covariance calculation"
covariance_images = Raster(cat(covariance_images..., dims=3), dims=covariance_dims, missingval=NaN)

# estimate spatial var parameter
n_eff = compute_n_eff(Int(round(coarse_cell_size / fine_cell_size)), 2, smoothness=1.5) ## Matern: range = 200m, smoothness = 1.5
sp_var = fast_var_est(covariance_images, n_eff_agg = n_eff)

coarse_images = []
coarse_dates = Vector{Date}(undef,0)

tk=1
for (i, date) in enumerate(dates)
    date = Dates.format(date, dateformat"yyyy-mm-dd")
    matched = findfirst(x -> occursin(date, x), coarse_image_filenames)

    if matched === nothing
        @info "coarse image is not available on $(date)"
        # coarse_image = Raster(fill(NaN, x_coarse_size, y_coarse_size, 1), dims=timestep_dims, missingval=NaN)
        # @info size(coarse_image)
    else
        timestep_index = Band(tk:tk)
        timestep_dims = (x_coarse, y_coarse, timestep_index)
        filename = coarse_image_filenames[matched]
        @info "ingesting coarse image on $(date): $(filename)"
        coarse_image = Raster(reshape(Raster(filename), x_coarse_size, y_coarse_size, 1), dims=timestep_dims, missingval=NaN)
        replace!(coarse_image, missing => NaN)
        @info size(coarse_image)
        push!(coarse_dates, dates[i])
        push!(coarse_images, coarse_image)
        global tk += 1
    end
end
@info "concatenating coarse image inputs"
if length(coarse_images) == 0
    coarse_images = Raster(fill(NaN, x_coarse_size, y_coarse_size, 1), dims=(coarse_dims[1:2]..., Band(1:1)), missingval=NaN)
    coarse_array = zeros(x_coarse_size, y_coarse_size, 1)
    coarse_array .= NaN
    coarse_dates = [fine_end_date]
else
    coarse_images = Raster(cat(coarse_images..., dims=3), dims=(coarse_dims[1:2]..., Band(1:length(coarse_dates))), missingval=NaN)
    coarse_array = Array{Float64}(coarse_images)
end

fine_images = []
fine_dates = Vector{Date}(undef,0)

tk=1
for (i, date) in enumerate(dates)
    date = Dates.format(date, dateformat"yyyy-mm-dd")
    match = findfirst(x -> occursin(date, x), fine_image_filenames)

    if match === nothing
        @info "fine image is not available on $(date)"
        # fine_image = Raster(fill(NaN, x_fine_size, y_fine_size, 1), dims=timestep_dims, missingval=NaN)
        # @info size(fine_image)
    else
        timestep_index = Band(tk:tk)
        timestep_dims = (x_fine, y_fine, timestep_index)
        filename = fine_image_filenames[match]
        @info "ingesting fine image on $(date): $(filename)"
        fine_image = Raster(reshape(Raster(filename), x_fine_size, y_fine_size, 1), dims=timestep_dims, missingval=NaN)
        replace!(fine_image, missing => NaN)
        @info size(fine_image)
        push!(fine_images, fine_image)
        push!(fine_dates, dates[i])
        global tk += 1
    end
end

@info "concatenating fine image inputs"
if length(fine_images) == 0
    fine_images = Raster(fill(NaN, x_fine_size, y_fine_size, 1), dims=(fine_dims[1:2]..., Band(1:1)), missingval=NaN)
    fine_array = zeros(x_fine_size, y_fine_size, 1)
    fine_array .= NaN
    fine_dates = [fine_end_date]
else
    fine_images = Raster(cat(fine_images..., dims=3), dims=(fine_dims[1:2]..., Band(1:length(fine_dates))), missingval=NaN)
    fine_array = Array{Float64}(fine_images)
end

if length(dates) == 0
    target_date = fine_end_date
else
    target_date = dates[end]
end
target_time = length(dates)

## 0, 1 mask
fine_pixels = sum(.!isnan.(fine_images),dims=3)
if sum(fine_pixels.==0) > 0
    if fine_flag_start_date < fine_start_date
        flag_dates = [fine_flag_start_date + Day(d - 1) for d in 1:((fine_start_date - Day(1) - fine_flag_start_date).value + 1)]
        tf = Ti(flag_dates)
        fine_flag_dims = (x_fine, y_fine, tf)

        for (i, date) in enumerate(flag_dates)
            date = Dates.format(date, dateformat"yyyy-mm-dd")
            match = findfirst(x -> occursin(date, x), fine_image_filenames)

            if match === nothing
                @info "fine image for 7-day flag is not available on $(date)"
            else
                timestep_dims = (x_fine, y_fine, Band(1:1))
                filename = fine_image_filenames[match]
                @info "ingesting fine image for 7-day flag on $(date): $(filename)"
                fine_image = Raster(reshape(Raster(filename), x_fine_size, y_fine_size, 1), dims=timestep_dims, missingval=NaN)
                replace!(fine_image, missing => NaN)

                fine_pixels .+= sum(.!isnan.(fine_image),dims=3)
            end
        end
    end
end

hls_flag = Array(fine_pixels[:,:,1] .== 0)

### nan pixels with no historical data 
if isnothing(prior_mean)
    prior_flag = trues(size(fine_images)[1:2])
    fine_obs = sum(.!isnan.(fine_images),dims=3) 
    ## uncomment to keep viirs-only pixels 
    if sum(fine_obs.==0) > 0
        coarse_nans = resample(sum(.!isnan.(coarse_images),dims=3), to=fine_images[:,:,1], method=:near)
        prior_flag[coarse_nans[:,:,1] .> 0] .= false
    end

    prior_flag[fine_pixels[:,:,1] .> 0] .= false
elseif sum(isnan.(prior_mean)) .> 0
    prior_flag = isnan.(prior_mean[:,:,1]) .> 0
    fine_obs = sum(.!isnan.(fine_images),dims=3) 
    ## uncomment to keep viirs-only pixels 
    if sum(fine_obs.==0) > 0
        coarse_nans = resample(sum(.!isnan.(coarse_images),dims=3), to=fine_images[:,:,1], method=:near)
        prior_flag[coarse_nans[:,:,1] .> 0] .= false
    end
    prior_flag[fine_pixels[:,:,1] .> 0] .= false
else
    prior_flag = falses(size(fine_images)[1:2])  
end

@info "running data fusion"

#### new approach
fine_times = findall(dates .∈ Ref(fine_dates))
coarse_times = findall(dates .∈ Ref(coarse_dates))

fine_ndims = collect(size(fine_images)[1:2])
coarse_ndims = collect(size(coarse_images)[1:2])

## instrument origins and cell sizes
fine_origin = get_centroid_origin_raster(fine_images)
coarse_origin = get_centroid_origin_raster(coarse_images)

fine_csize = collect(cell_size(fine_images))
coarse_csize = collect(cell_size(coarse_images))

fine_geodata = STARSInstrumentGeoData(fine_origin, fine_csize, fine_ndims, 0, fine_times)
coarse_geodata = STARSInstrumentGeoData(coarse_origin, coarse_csize, coarse_ndims, 2, coarse_times)

fine_data = STARSInstrumentData(fine_array, 0.0, 1e-6, false, nothing, abs.(fine_csize), fine_times, [1. 1.])
coarse_data = STARSInstrumentData(coarse_array, 0.0, 1e-6, true, [1.0,1e-6], abs.(coarse_csize), coarse_times, [1. 1.])

nsamp=100
window_buffer = 4 ## set these differently for NDVI and albedo?

cov_pars = ones((size(fine_images)[1], size(fine_images)[2], 4))

sp_rs = resample(log.(sqrt.(sp_var[:,:,1])); to=fine_images[:,:,1], size=size(fine_images)[1:2], method=:cubicspline)
sp_rs[isnan.(sp_rs)] .= nanmean(sp_rs) ### the resampling won't go outside extent

cov_pars[:,:,1] = Array{Float64}(exp.(sp_rs))
cov_pars[:,:,2] .= coarse_cell_size
# cov_pars[:,:,2] .= 200.0
cov_pars[:,:,3] .= 1e-10
cov_pars[:,:,4] .= 0.5

if isnothing(prior_mean)
    fused_images, fused_sd_images, fused_bias_images, fused_bias_sd_images = coarse_fine_scene_fusion_cbias_pmap(fine_data,
        coarse_data,
        fine_geodata, 
        coarse_geodata,
        DEFAULT_MEAN .* ones(fine_ndims...),
        DEFAULT_SD^2 .* ones(fine_ndims...), 
        DEFAULT_BIAS_MEAN .* ones(coarse_ndims...),
        DEFAULT_BIAS_SD^2 .* ones(coarse_ndims...), 
        cov_pars;
        nsamp = nsamp,
        window_buffer = window_buffer,
        target_times = [target_time], 
        spatial_mod = exp_cor,                                           
        obs_operator = unif_weighted_obs_operator_centroid,
        state_in_cov = false,
        cov_wt = 0.2,
        nb_coarse = 2.0);
else
    ## fill in prior mean with mean prior
    nkp = isnan.(prior_mean)
    if sum(nkp) > 0
        mp = nanmean(prior_mean)
        prior_mean[nkp] .= mp
    end

    fused_images, fused_sd_images, fused_bias_images, fused_bias_sd_images = coarse_fine_scene_fusion_cbias_pmap(fine_data,
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
        nb_coarse = 2.0);
end;

## remove workers
rmprocs(workers())

if occursin("NDVI", posterior_filename)
    clamp!(fused_images, -1, 1) # NDVI clipped to [-1,1] range
else 
    clamp!(fused_images, 0, 1) # albedo clipped to [0,1]
end

dd = fused_images[:,:,:]
dd[prior_flag,:] .= NaN # set no data to NaN

fused_raster = Raster(dd, dims=(x_fine, y_fine, Band(1:1)), missingval=NaN)
flag_raster = Raster(Int.(hls_flag), dims=(x_fine, y_fine), missingval=NaN)

@info "writing fused mean: $(posterior_filename)"
write(posterior_filename, fused_raster, force=true)
@info "writing fused flag: $(posterior_flag_filename)"
write(posterior_flag_filename, flag_raster, force=true)
@info "writing fused SD: $(posterior_UQ_filename)"
write(posterior_UQ_filename, Raster(fused_sd_images, dims=(x_fine, y_fine, Band(1:1)), missingval=NaN), force=true)
@info "writing bias mean: $(posterior_bias_filename)"
write(posterior_bias_filename, Raster(fused_bias_images, dims=(x_coarse, y_coarse, Band(1:1)), missingval=NaN), force=true)
@info "writing bias SD: $(posterior_bias_UQ_filename)"
write(posterior_bias_UQ_filename, Raster(fused_bias_sd_images, dims=(x_coarse, y_coarse, Band(1:1)), missingval=NaN), force=true)

