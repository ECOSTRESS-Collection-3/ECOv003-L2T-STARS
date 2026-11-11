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

@info "processing STARS data fusion"

wrkrs = parse(Int64, ARGS[1])
# wrkrs = 8

@info "starting \$(wrkrs) workers"
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
    println(logger.stream, "[\$t $(uppercase(string(level)))]$message")
end

global_logger(CustomLogger(stdout, Logging.Info))

tile = ARGS[2]
@info "tile: \$(tile)"
coarse_cell_size = parse(Int64, ARGS[3])
@info "coarse cell size: \$(coarse_cell_size)"
fine_cell_size = parse(Int64, ARGS[4])
@info "fine cell size: \$(fine_cell_size)"
VIIRS_start_date = Date(ARGS[5])
@info "VIIRS start date: \$(VIIRS_start_date)"
VIIRS_end_date = Date(ARGS[6])
@info "VIIRS end date: \$(VIIRS_end_date)"
HLS_start_date = Date(ARGS[7])
@info "HLS start date: \$(HLS_start_date)"
HLS_end_date = Date(ARGS[8])
@info "HLS end date: \$(HLS_end_date)"
downsampled_directory = ARGS[9]
@info "downsampled inputs directory: \$(downsampled_directory)"
product_name = ARGS[10]
@info "Computing \$(product_name) product"
posterior_filename = ARGS[11]
@info "posterior filename: \$(posterior_filename)"
posterior_UQ_filename = ARGS[12]
@info "posterior UQ filename: \$(posterior_UQ_filename)"
posterior_flag_filename = ARGS[13]
@info "posterior flag filename: \$(posterior_flag_filename)"
posterior_bias_filename = ARGS[14]
@info "posterior bias filename: \$(posterior_bias_filename)"
posterior_bias_UQ_filename = ARGS[15]
@info "posterior bias UQ filename: \$(posterior_bias_UQ_filename)"

if size(ARGS)[1] >= 19
    prior_filename = ARGS[16]
    @info "prior filename: \$(prior_filename)"
    prior_mean = Array(Raster(prior_filename))
    prior_UQ_filename = ARGS[17]
    @info "prior UQ filename: \$(prior_UQ_filename)"
    prior_sd = Array(Raster(prior_UQ_filename))
    prior_bias_filename = ARGS[18]
    @info "prior bias filename: \$(prior_bias_filename)"
    prior_bias_mean = Array(Raster(prior_bias_filename))
    prior_bias_UQ_filename = ARGS[19]
    @info "prior bias UQ filename: \$(prior_bias_UQ_filename)"
    prior_bias_sd = Array(Raster(prior_bias_UQ_filename))

    replace!(prior_bias_mean, missing => NaN)
    replace!(prior_bias_sd, missing => NaN)
    replace!(prior_mean, missing => NaN)
    replace!(prior_sd, missing => NaN)
    ## if we do flag as HLS observed within last 7 days then we don't depend on prior flags
    # prior_flag_filename = ARGS[20