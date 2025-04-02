using Glob
using Dates
using Rasters
using Plots
using LinearAlgebra
using STARS
using STARS.BBoxes
using STARS.sentinel_tiles
using STARS.HLS
using STARS.VNP43
using STARS.STARS
using Logging

using Pkg

Pkg.add("OpenSSL")

using HTTP

BLAS.set_num_threads(1)

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

# command = f'cd "{STARS_source_directory}" && julia --project=@. "{julia_script_filename}" "{tile}" "{coarse_cell_size}" "{fine_cell_size}" "{VIIRS_start_date}" "{VIIRS_end_date}" "{HLS_start_date}" "{HLS_end_date}" "{coarse_directory}" "{fine_directory}" "{posterior_filename}" "{posterior_UQ_filename}" "{posterior_bias_filename}" "{posterior_bias_UQ_filename}" "{prior_filename}" "{prior_UQ_filename}" "{prior_bias_filename}" "{prior_bias_UQ_filename}"'

@info "processing STARS data fusion"
tile = ARGS[1]
@info "tile: $(tile)"
coarse_cell_size = parse(Int64, ARGS[2])
@info "coarse cell size: $(coarse_cell_size)"
fine_cell_size = parse(Int64, ARGS[3])
@info "fine cell size: $(fine_cell_size)"
VIIRS_start_date = Date(ARGS[4])
@info "VIIRS start date: $(VIIRS_start_date)"
VIIRS_end_date = Date(ARGS[5])
@info "VIIRS end date: $(VIIRS_end_date)"
HLS_start_date = Date(ARGS[6])
@info "HLS start date: $(HLS_start_date)"
HLS_end_date = Date(ARGS[7])
@info "HLS end date: $(HLS_end_date)"
coarse_directory = ARGS[8]
@info "coarse inputs directory: $(coarse_directory)"
fine_directory = ARGS[9]
@info "fine inputs directory: $(fine_directory)"
posterior_filename = ARGS[10]
@info "posterior filename: $(posterior_filename)"
posterior_UQ_filename = ARGS[11]
@info "posterior UQ filename: $(posterior_UQ_filename)"
posterior_bias_filename = ARGS[12]
@info "posterior bias filename: $(posterior_bias_filename)"
posterior_bias_UQ_filename = ARGS[13]
@info "posterior bias UQ filename: $(posterior_bias_UQ_filename)"

if size(ARGS)[1] >= 17
    prior_filename = ARGS[14]
    @info "prior filename: $(prior_filename)"
    prior_mean = Raster(prior_filename)
    prior_UQ_filename = ARGS[15]
    @info "prior UQ filename: $(prior_UQ_filename)"
    prior_sd = Raster(prior_UQ_filename)
    prior_bias_filename = ARGS[16]
    @info "prior bias filename: $(prior_bias_filename)"
    prior_bias_mean = Raster(prior_bias_filename)
    prior_bias_UQ_filename = ARGS[17]
    @info "prior bias UQ filename: $(prior_bias_UQ_filename)"
    prior_bias_sd = Raster(prior_bias_UQ_filename)
    prior = DataFusionState(prior_mean, prior_sd, prior_bias_mean, prior_bias_sd, nothing)
else
    prior = nothing
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
        @info size(covariance_image)
    end

    push!(covariance_images, covariance_image)
end

@info "concatenating coarse images for covariance calculation"
covariance_images = Raster(cat(covariance_images..., dims=3), dims=covariance_dims, missingval=NaN)

# estimate spatial var parameter
n_eff = compute_n_eff(Int(round(coarse_cell_size / fine_cell_size)), 2, smoothness=1.5) ## Matern: range = 200m, smoothness = 1.5
sp_var = fast_var_est(covariance_images, n_eff_agg = n_eff)

# cov_pars = ones((size(covariance_images)[1], size(covariance_images)[2], 4))
# cov_pars[:,:,1] = Array{Float64}(sp_var)
# cov_pars[:,:,2] .= 200
# cov_pars[:,:,3] .= 1e-10
# cov_pars[:,:,4] .= 1.5

coarse_images = []
coarse_dates = Vector{Date}(undef,0)

tk=1
for (i, date) in enumerate(dates)
    date = Dates.format(date, dateformat"yyyy-mm-dd")
    match = findfirst(x -> occursin(date, x), coarse_image_filenames)


    if match === nothing
        @info "coarse image is not available on $(date)"
        # coarse_image = Raster(fill(NaN, x_coarse_size, y_coarse_size, 1), dims=timestep_dims, missingval=NaN)
        # @info size(coarse_image)
    else
        timestep_index = Band(tk:tk)
        timestep_dims = (x_coarse, y_coarse, timestep_index)
        filename = coarse_image_filenames[match]
        @info "ingesting coarse image on $(date): $(filename)"
        coarse_image = Raster(reshape(Raster(filename), x_coarse_size, y_coarse_size, 1), dims=timestep_dims, missingval=NaN)
        @info size(coarse_image)
        push!(coarse_dates, dates[i])
        push!(coarse_images, coarse_image)
        tk += 1
    end
end
@info "concatenating coarse image inputs"
if length(coarse_images) == 0
    coarse_images = Raster(fill(NaN, x_coarse_size, y_coarse_size, 1), dims=(coarse_dims[1:2]..., Band(1:1)), missingval=NaN)
    coarse_array = zeros(x_coarse_size, y_coarse_size, 1)
    coarse_array .= NaN
    coarse_dates = [dates[1]]
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
        @info size(fine_image)
        push!(fine_images, fine_image)
        push!(fine_dates, dates[i])
        tk += 1
    end
end

@info "concatenating fine image inputs"
if length(fine_images) == 0
    fine_images = Raster(fill(NaN, x_fine_size, y_fine_size, 1), dims=(fine_dims[1:2]..., Band(1:1)), missingval=NaN)
    fine_array = zeros(x_fine_size, y_fine_size, 1)
    fine_array .= NaN
    fine_dates = [dates[1]]
else
    fine_images = Raster(cat(fine_images..., dims=3), dims=(fine_dims[1:2]..., Band(1:length(fine_dates))), missingval=NaN)
    fine_array = Array{Float64}(fine_images)
end

target_date = dates[end]
target_time = length(dates)

if isnothing(prior)
    mm = trues(size(fine_images)[1:2])
    data_pixels = sum(.!isnan.(fine_images),dims=3) 
    if sum(data_pixels.==0) > 0
        coarse_nans = resample(sum(.!isnan.(coarse_images),dims=3), to=fine_images[:,:,1], method=:near)
        data_pixels .+= coarse_nans 
    end
    mm[data_pixels[:,:,1] .> 0] .= false
    if sum(mm .> 0) == 0
        mm = nothing
    end
elseif sum(isnan.(prior.mean)) > 0
    mm = Array(isnan.(prior.mean))
    data_pixels = sum(.!isnan.(fine_images),dims=3)    
    ### uncomment to keep viirs-only pixels 
    # if sum(data_pixels.==0) > 0
    #     coarse_nans = resample(sum(.!isnan.(coarse_images),dims=3), to=fine_images[:,:,1], method=:near)
    #     data_pixels .+= coarse_nans 
    # end
    mm[data_pixels[:,:,1] .> 0] .= false
    if sum(mm .> 0) == 0
        mm = nothing
    end
else
    mm = nothing
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
# window_geodata = STARSInstrumentGeoData(coarse_origin, coarse_csize, coarse_ndims, 0, coarse_times)

# target_geodata = STARSInstrumentGeoData(fine_origin, fine_csize, fine_ndims, 0, 1:length(dates))

fine_data = STARSInstrumentData(fine_array, 0.0, 1e-6, false, nothing, abs.(fine_csize), fine_times, [1. 1.])
coarse_data = STARSInstrumentData(coarse_array, 0.0, 1e-6, true, [1.0, 1e-6], abs.(coarse_csize), coarse_times, [1. 1.])

cov_pars = ones((size(fine_images)[1], size(fine_images)[2], 4))

sp_rs = resample(log.(sqrt.(sp_var[:,:,1])); to=fine_images[:,:,1], size=size(fine_images)[1:2], method=:cubicspline)
sp_rs[isnan.(sp_rs)] .= nanmean(sp_rs) ### the resampling won't go outside extent

cov_pars[:,:,1] = Array{Float64}(exp.(sp_rs))
cov_pars[:,:,2] .= 200
cov_pars[:,:,3] .= 1e-10
cov_pars[:,:,4] .= 1.5

nsamp=100
window_buffer = 2

@time if isnothing(prior)
    fused_images, fused_sd_images, fused_bias_images, fused_bias_sd_images = coarse_fine_scene_fusion_ns(fine_data,
        coarse_data,
        fine_geodata, 
        coarse_geodata,
        coarse_ndims,
        DEFAULT_MEAN .* ones(fine_ndims...),
        DEFAULT_SD^2 .* ones(fine_ndims...), 
        DEFAULT_BIAS .* ones(coarse_ndims...),
        DEFAULT_BIAS_SD .* ones(coarse_ndims...),
        cov_pars;
        nsamp = nsamp,
        window_buffer = window_buffer,
        target_times = [target_time], 
        spatial_mod = mat32_cor,                                           
        obs_operator = unif_weighted_obs_operator,
        state_in_cov = false,
        cov_wt = 0.2,
        nb_coarse = 1.0);
else
    ## fill in prior mean with mean prior
    pmean = Array(prior.mean)
    nkp = isnan.(pmean)
    if sum(nkp) > 0
        mp = nanmean(pmean)
        pmean[nkp] .= mp
    end

    fused_images, fused_sd_images, fused_bias_images, fused_bias_sd_images = coarse_fine_scene_fusion_ns(fine_data,
        coarse_data,
        fine_geodata, 
        coarse_geodata,
        coarse_ndims,
        pmean,
        Array(prior.SD.^2),
        Array(prior.mean_bias),
        Array(prior.SD_bias.^2),
        cov_pars;
        nsamp = nsamp,
        window_buffer = window_buffer,
        target_times = [target_time], 
        spatial_mod = mat32_cor,                                           
        obs_operator = unif_weighted_obs_operator,
        state_in_cov = false,
        cov_wt = 0.2,
        nb_coarse = 1.0);
end

if occursin("NDVI", posterior_filename)
    clamp!(fused_images, -1, 1) # NDVI clipped to [-1,1] range
else 
    clamp!(fused_images, 0, 1) # albedo clipped to [0,1]
end

dd = fused_images[:,:,:]

### mask no historical data 
if !isnothing(mm)
    dd[mm,:] .= NaN
end
fused_raster = Raster(dd, dims=(x_fine, y_fine, Band(1:1)), missingval=NaN)

@info "writing fused mean: $(posterior_filename)"
write(posterior_filename, fused_raster, force=true)
@info "writing fused SD: $(posterior_UQ_filename)"
write(posterior_UQ_filename, Raster(fused_sd_images, dims=(x_fine, y_fine, Band(1:1)), missingval=NaN), force=true)

@info "writing bias mean: $(posterior_bias_filename)"
write(posterior_bias_filename, Raster(fused_bias_images, dims=(x_coarse, y_coarse, Band(1:1)), missingval=NaN), force=true)
@info "writing bias SD: $(posterior_bias_UQ_filename)"
write(posterior_bias_UQ_filename, Raster(fused_bias_sd_images, dims=(x_coarse, y_coarse, Band(1:1)), missingval=NaN), force=true)

