using Glob
using Dates
using Rasters
using LinearAlgebra
using Logging
using Statistics
using Distributed
using ArchGDAL
using GeoDataFrames
using DataFrames
using SparseArrays
using BlockDiagonals
using DynamicIterators
using Trajectories
using ProgressMeter
using Distances
using Sobol
using Interpolations
using KernelFunctions
using Distributions
import GeoDataFrames as GDF
import ArchGDAL as AG
import GaussianRandomFields.CovarianceFunction
import GaussianRandomFields.Matern
import GaussianRandomFields.apply

@info "processing STARS data fusion"

wrkrs = parse(Int64, ARGS[1])
@info "starting $(wrkrs) workers"
addprocs(wrkrs)

@everywhere begin
    using Dates
    using Rasters
    using LinearAlgebra
    using Logging
    using Statistics
    using DataFrames
    using SparseArrays
    using BlockDiagonals
    using DynamicIterators
    using Trajectories
    using ProgressMeter
    using Distances
    using Sobol
    using Interpolations
    using KernelFunctions
    using Distributions
    import GaussianRandomFields.CovarianceFunction
    import GaussianRandomFields.Matern
    import GaussianRandomFields.apply

    BLAS.set_num_threads(1)

    # --- CORE DATA STRUCTURES & UTILITIES ---
    struct Point
        x::Float64
        y::Float64
    end

    struct BBox
        xmin::Float64
        ymin::Float64
        xmax::Float64
        ymax::Float64
    end

    function BBox(raster::Raster)::BBox
        if length(size(raster)) == 3
            ((xmin, xmax), (ymin, ymax)) = bounds(raster[:,:,1])[1:2]
        else
            ((xmin, xmax), (ymin, ymax)) = bounds(raster)[1:2]
        end
        return BBox(xmin, ymin, xmax, ymax)
    end

    function buffer(bbox::BBox, buffer::Float64)::BBox
        return BBox(bbox.xmin - buffer, bbox.ymin - buffer, bbox.xmax + buffer, bbox.ymax + buffer)
    end

    function calculate_centroid(bbox::BBox)::Point
        Point((bbox.xmin + bbox.xmax) / 2, (bbox.ymin + bbox.ymax) / 2)
    end

    const SENTINEL_FILENAME = joinpath(@__DIR__, "sentinel2.geojson")
    const SENTINEL_DF = ispath(SENTINEL_FILENAME) ? GDF.read(SENTINEL_FILENAME) : nothing

    function sentinel_tile_record(tile::String)
        search_results = SENTINEL_DF[isequal.(SENTINEL_DF.tile, tile), :]
        if size(search_results)[1] == 0
            error("tile $(tile) not found")
        end
        return search_results[1, :]
    end

    function sentinel_tile_bbox(tile::String)::BBox
        tile_row = sentinel_tile_record(tile)
        return BBox(tile_row.xmin, tile_row.ymin, tile_row.xmax, tile_row.ymax)
    end

    function sentinel_tile_EPSG(tile::String)::Int64
        tile_row = sentinel_tile_record(tile)
        if tile_row.EPSG == ""
            error("no projection found for tile $(tile)")
        end
        return parse(Int64, tile_row.EPSG)
    end

    function sentinel_tile_dims(tile::String, cell_size::Union{Float64,Int64})::Tuple{X,Y}
        bbox = sentinel_tile_bbox(tile)
        xmin, ymin, xmax, ymax = bbox.xmin, bbox.ymin, bbox.xmax, bbox.ymax
        tile_EPSG = sentinel_tile_EPSG(tile)
        cols = Int(trunc((ymax - ymin) / cell_size))
        rows = Int(trunc((xmax - xmin) / cell_size))
        x_dim = X(Projected(LinRange(xmin, xmin + (rows - 1) * cell_size, rows), order=ForwardOrdered(), span=Regular(cell_size), sampling=Intervals(Start()), crs=convert(WellKnownText, EPSG(tile_EPSG))))
        y_dim = Y(Projected(LinRange(ymax - cell_size, ymax - cols * cell_size, cols), order=ReverseOrdered(), span=Regular(-cell_size), sampling=Intervals(Start()), crs=convert(WellKnownText, EPSG(tile_EPSG))))
        return (x_dim, y_dim)
    end

    struct STARSInstrumentData
        data::AbstractArray
        bias::Union{Float64,AbstractArray}
        uq::Union{Float64,AbstractArray}
        dynamic_bias::Bool
        dynamic_bias_coefs::Union{AbstractVector{Float64}, Nothing}
        spatial_resolution::AbstractVector{Float64}
        dates::AbstractVector
        coords::AbstractArray
    end

    struct STARSInstrumentGeoData
        origin::AbstractVector
        cell_size::AbstractVector
        ndims::AbstractVector
        fidelity::Int64
        dates::AbstractVector
    end

    nanmean(x) = mean(filter(!isnan, x))
    nanvar(x) = var(filter(!isnan, x))

    function find_nearest_ind(target::T, origin::T, cell_size::T) where T <: Real
        return Int(round((target - origin) / cell_size + 1))
    end

    function find_nearest_inds_ext(ext::AbstractVector{T}, origin::T, cellsize::T) where T <: Real
        ind1 = (ext[1] - origin) / cellsize + 1
        ind2 = (ext[2] - origin) / cellsize + 1
        return [Int(ceil(ind1)), Int(floor(ind2))]
    end

    function find_all_ij_ext(ext_ti::AbstractVector{T}, ext_tj::AbstractVector{T}, origin::AbstractVector{T}, cellsize::AbstractVector{T}, n_dims::AbstractVector{<:Real}; inclusive=false) where T<:Real
        oi, oj = origin
        c, r = cellsize
        if !inclusive
            ext_ti = ext_ti .- sign(c)*[0,1e-8]
            ext_tj = ext_tj .- sign(r)*[0,1e-8]
        end
        is = find_nearest_inds_ext(ext_ti, oi, c)
        js = find_nearest_inds_ext(ext_tj, oj, r)
        if any(is .> 0) & any(js .> 0) & any(is .<= n_dims[1]) & any(js .<= n_dims[2])
            is[is .< 1] .= 1
            js[js .< 1] .= 1
            is[is .> n_dims[1]] .= n_dims[1]
            js[js .> n_dims[2]] .= n_dims[2]
            iss = repeat(is[1]:is[2], inner=js[2]-js[1]+1, outer=[1])
            jss = repeat(js[1]:js[2], inner=[1], outer=is[2]-is[1]+1)
            return unique(hcat(iss,jss),dims=1)
        else
            return Array{Int64}(undef, 0, 0)
        end
    end

    function sobol_bau_ij(ext_ti::AbstractVector{T}, ext_tj::AbstractVector{T}, origin::AbstractVector{T}, cell_size::AbstractVector{T}, n_dims::AbstractVector{<:Real}; nsamp=100, inclusive=false) where T<:Real
        oi, oj = origin
        c, r = cell_size
        if !inclusive
            ext_ti = ext_ti .- sign(c)*[0,1e-9]
            ext_tj = ext_tj .- sign(r)*[0,1e-9]
        end
        is = find_nearest_ind.(ext_ti, oi, c)
        js = find_nearest_ind.(ext_tj, oj, r)
        if any(is .> 0) & any(js .> 0) & any(is .<= n_dims[1]) & any(js .<= n_dims[2])
            is[is .< 1] .= 1
            js[js .< 1] .= 1
            is[is .> n_dims[1]] .= n_dims[1]
            js[js .> n_dims[2]] .= n_dims[2]
            ni = is[2]-is[1] + 1
            nj = js[2]-js[1] + 1
            if nsamp >= ni*nj
                iss = repeat(is[1]:is[2], inner=[nj], outer=[1])
                jss = repeat(js[1]:js[2], inner=[1], outer=[ni])
                dd = unique(hcat(iss,jss),dims=1)
            else
                s = SobolSeq([is[1],js[1]],[is[2],js[2]])
                p = reduce(hcat, Sobol.next!(s) for i = 1:nsamp)'
                dd = Int64.(unique(round.(p),dims=1))
            end
            return dd
        else
            return Array{Int64}(undef, 0, 0)
        end
    end

    function get_sij_from_ij(ij_array::AbstractArray{<:Real}, origin::AbstractVector{T}, cell_size::AbstractVector{T}) where T<:Real
        return origin' .+ cell_size' .* (ij_array .- [1.,1.]')
    end

    function get_centroid_origin_raster(rast::Raster)
        cc = abs.(collect(cell_size(rast)))
        return [rast.dims[1].val[1],rast.dims[2].val[1]] .+ cc./2
    end

    function bbox_from_centroid(target::AbstractVector{T},cell_size::AbstractVector{T}) where T<:Real
        return ones(2,2) .* [-0.5 0.5] .* cell_size .+ target
    end

    function find_overlapping_ext(ext_ti::AbstractVector{T}, ext_tj::AbstractVector{T}, origin::AbstractVector{T}, cell_size::AbstractVector{T}; inclusive=false) where T<:Real
        oi, oj = origin
        c, r = cell_size
        if !inclusive
            ext_ti = ext_ti .- sign(c)*[0,1e-9]
            ext_tj = ext_tj .- sign(r)*[0,1e-9]
        end
        is = find_nearest_ind.(ext_ti, oi, c)
        js = find_nearest_ind.(ext_tj, oj, r)
        si = oi .+ c * (is .- 1.)
        sj = oj .+ r * (js .- 1.)
        ext_ovi = si .+ [-0.5,0.5] .* cell_size[1]
        ext_ovj = sj .+ [-0.5,0.5] .* cell_size[2]
        return hcat(ext_ovi, ext_ovj)'
    end

    function merge_extents(exts::AbstractVector{<:AbstractArray}, sgns)
        aa = hcat(exts...)
        mms = extrema(aa, dims=2)
        es = hcat(first.(mms), last.(mms))
        if sign(sgns[1]) == -1
            es[1,:] = reverse(es[1,:])
        end
        if sign(sgns[2]) == -1
            es[2,:] = reverse(es[2,:])
        end
        return es
    end

    function cell_size(raster::Raster)
        rows = size(raster)[1]
        cols = size(raster)[2]
        if length(size(raster)) == 3
            bbox = Rasters.bounds(raster[:, :, 1])
        else
            bbox = Rasters.bounds(raster)
        end
        xmin, xmax = bbox[1]
        ymin, ymax = bbox[2]
        cell_width = (xmax - xmin) / rows
        cell_height = -(ymax - ymin) / cols
        return cell_width, cell_height
    end

    function unif_weighted_obs_operator_centroid(sensor::AbstractArray{T}, target::AbstractArray{T}, sensor_res::AbstractVector{T}) where T<:Real
        if sensor == target
            n = size(target,1)
            return sparse(1.0I, n, n)
        else
            d1 = pairwise(Euclidean(1e-12), sensor[:, 1]', target[:, 1]', dims=2) .<= sensor_res[1] / 2
            d2 = pairwise(Euclidean(1e-12), sensor[:, 2]', target[:, 2]', dims=2) .<= sensor_res[2] / 2
            H = d1 .* d2
            return sparse(broadcast(/, H, sum(H, dims=2)))
        end
    end

    function exp_cor(X::AbstractArray{T}, pars::AbstractVector{T}) where {T<:Real}
        σ = pars[1]
        reg = pars[2]
        return Diagonal(reg * ones(size(X)[2])) + exp.(-pairwise(Euclidean(1e-12), X, dims=2) ./ σ)
    end

    function kalman_filter!(x_new::AbstractVector{T}, P_new::AbstractMatrix{T}, Ht::Union{AbstractSparseMatrix{T},AbstractMatrix{T}}, y::AbstractVector{T}, err_vars::AbstractVector{T}, x_pred::AbstractVector{T}, P_pred::AbstractMatrix{T}) where T <: Real
        res_pred = y - Ht * x_pred
        HPpT = P_pred * Ht'
        S = Ht * HPpT .+ Diagonal(err_vars)
        begin
            LAPACK.potrf!('U', S)
            LAPACK.potri!('U', S)
            K = BLAS.symm('R', 'U', S, HPpT)
        end
        x_new .= x_pred
        mul!(x_new, K, res_pred, 1.0, 1.0)
        HP_pred = Ht * P_pred
        P_new .= P_pred
        mul!(P_new, K, HP_pred, -1.0, 1.0)
    end

    function fast_var_est(coarse_images::Raster; n_eff_agg = 50, min_num_obs = 8, default_var = 1e-4)
        if isnothing(coarse_images.missingval) || isnan(coarse_images.missingval)
            num_obs = sum(.!(isnan.(coarse_images)), dims=3)
            result = mapslices(x -> var(x[.!(isnan.(x))]), diff(coarse_images, dims=3), dims=3) .* n_eff_agg
        elseif ismissing(coarse_images.missingval)
            num_obs = sum(.!(ismissing.(coarse_images)), dims=3)
            result = mapslices(x -> var(x[.!(ismissing.(x))]), diff(coarse_images, dims=3), dims=3) .* n_eff_agg
        end
        result[num_obs .< min_num_obs] .= default_var
        return result
    end

    function compute_n_eff(agg_scale, range; smoothness=0.5)
        subsample_inds = hcat(repeat(1:agg_scale, inner=[1], outer=[agg_scale]), repeat(1:agg_scale, inner=[agg_scale], outer=[agg_scale]))'
        n = size(subsample_inds)[2]
        cc = CovarianceFunction(2, Matern(range, smoothness))
        n_eff = n^2 / sum(apply(cc, subsample_inds, subsample_inds))
        return n_eff
    end

    function coarse_fine_fusion_cbias!(fused_image, fused_sd_image, fused_bias_image, fused_bias_sd_image, measurements, target_coords, kp_ij, kp_bias_ij, prior_mean, prior_var, prior_bias_mean, prior_bias_var, model_pars; target_times = [1], spatial_mod::Function = exp_cor, obs_operator::Function = unif_weighted_obs_operator_centroid, state_in_cov::Bool = false, cov_wt::AbstractFloat = 0.3)
        ni = size(measurements)[1]
        nf = size(target_coords)[1]
        nnobs = Vector{Int64}(undef, ni)
        t0v = Vector{Int64}(undef, ni)
        ttv = Vector{Int64}(undef, ni)
        for i in 1:ni
            nnobs[i] = size(measurements[i].data)[1]
            t0v[i] = measurements[i].dates[1]
            ttv[i] = measurements[i].dates[end]
        end
        t0 = minimum(t0v)
        tt = maximum(ttv)
        tp = maximum(target_times)
        times = t0:tp
        nsteps = size(times)[1]
        K = 2
        biases = [x.dynamic_bias for x in measurements]
        nn_biases = nnobs[:]
        nn_biases[.!biases] .= 0
        nt_bias = sum(nn_biases)
        data_kp = falses(ni, nsteps)
        Hl = Vector(undef, ni)
        Qb = Float64[]
        Fb = Float64[]
        for (i, x) in enumerate(measurements)
            Hs = obs_operator(x.coords, target_coords, x.spatial_resolution)
            if x.dynamic_bias
                Hbb = [spzeros(x,x) for x in nn_biases]
                Hbb[i] .= 1.0 * I(nnobs[i])
                Hl[i] = hcat(Hs, Hbb[length.(Hbb) .> 0]...)
                append!(Fb, x.dynamic_bias_coefs[1] * ones(nnobs[i]))
                append!(Qb, x.dynamic_bias_coefs[2] * ones(nnobs[i]))
            else
                Hl[i] = hcat(Hs, spzeros(nnobs[i], nt_bias))
            end
            data_kp[i, in(measurements[i].dates).(t0:tp)] .= 1
        end
        H = vcat(Hl...)
        nb = sum(length.(Qb))
        n = nf + nb
        Q = zeros(n, n)
        cvs = Diagonal(model_pars[:,1])
        Q[1:nf, 1:nf] = cvs * spatial_mod(target_coords', model_pars[1, 2:end]) * cvs
        if length(Fb) > 0
            F = Diagonal([ones(nf)..., Fb...])
            @views Q[diagind(Q)[(nf+1):end]] = [Qb...]
        else
            F = UniformScaling(1.0)
        end
        nb = length(prior_bias_mean)
        n = nf + nb
        filtering_means = zeros(n, nsteps + 1)
        filtering_covs = zeros(n, n, nsteps + 1)
        filtering_means[1:nf, 1] = prior_mean
        filtering_means[(nf+1):end, 1] = prior_bias_mean
        @views filtering_covs[diagind(filtering_covs[:,:,1])[1:nf]] = prior_var
        @views filtering_covs[diagind(filtering_covs[:,:,1])[(nf+1):end]] = prior_bias_var
        x_pred = zeros(n)
        P_pred = zeros(n, n)
        x_new = zeros(n)
        P_new = zeros(n, n)
        Qss = zeros(nf, nf)
        FPpred = similar(P_pred)
        Qf = zeros(n, n)
        tk = 1
        for (t, t2) in enumerate(t0:tp)
            Qf .= Q
            if state_in_cov
                Xtt = @views filtering_means[1:nf, t:t]
                pairwise!(Qss, Euclidean(1e-12), Xtt, dims=1)
                phi = maximum([0.01, mean(Qss)])
                Qss ./= phi
                Qss .= cvs * exp.(-Qss) * cvs + UniformScaling(1e-8)
                Qss .*= (1.0 .- cov_wt)
                @view(Qf[1:nf, 1:nf]) .*= cov_wt
                @view(Qf[1:nf, 1:nf]) .+= Qss
            end
            if !any(data_kp[:, t])
                ys = fill(NaN, 1)
                err_vars = fill(NaN, 1)
            else
                ys = Float64[]
                err_vars = Float64[]
                yms = Int64[]
                nii = 0
                for x in 1:K
                    yss = @views measurements[x].data[:, measurements[x].dates .== t2][:]
                    ym = findall(.!isnan.(yss))
                    if length(ym) > 0
                        err_varss = @views measurements[x].uq * ones(length(ym))
                        @views append!(ys, yss[ym])
                        append!(err_vars, err_varss)
                        append!(yms, ym .+ nii)
                    end
                    nii += nnobs[x]
                end
                Ht = H[yms, :]
            end
            P_pred .= Qf
            mul!(x_pred, F, @view(filtering_means[:, t]))
            mul!(FPpred, F, @view(filtering_covs[:, :, t]))
            mul!(P_pred, FPpred, F', 1.0, 1.0)
            if sum(.!isnan.(ys)) == 0
                filtering_means[:, t+1] = x_pred
                filtering_covs[:, :, t+1] = P_pred
            else
                kalman_filter!(x_new, P_new, Ht, ys, err_vars, x_pred, P_pred)
                filtering_means[:, t+1] = x_new
                filtering_covs[:, :, t+1] = P_new
            end
            nbau = size(kp_ij, 1)
            if t2 ∈ Ref(target_times)
                fused_image[kp_ij, tk] = @views filtering_means[1:nbau, t+1]
                fused_sd_image[kp_ij, tk] = @views diag(filtering_covs[1:nbau, 1:nbau, t+1])
                fused_bias_image[kp_bias_ij, tk] = @views filtering_means[nf+1, t+1]
                fused_bias_sd_image[kp_bias_ij, tk] = @views filtering_covs[nf+1, nf+1, t+1]
                tk += 1
            end
        end
    end

    function coarse_fine_scene_fusion_cbias_pmap(fine_data, coarse_data, fine_geodata, coarse_geodata, prior_mean::AbstractArray, prior_var::AbstractArray, prior_bias_mean::AbstractArray, prior_bias_var::AbstractArray, model_pars::AbstractArray; nsamp = 100, window_buffer = 2, target_times = [1], spatial_mod::Function = exp_cor, obs_operator::Function = unif_weighted_obs_operator_centroid, state_in_cov::Bool = false, cov_wt::AbstractFloat = 0.2, phi::AbstractFloat = 0.001, ar_par::AbstractFloat = 1.0, nb_coarse=2.0, batchsize=1)
        window_csize = coarse_geodata.cell_size
        target_csize = fine_geodata.cell_size
        window_origin = coarse_geodata.origin
        window_ndims = coarse_geodata.ndims
        target_origin = fine_geodata.origin
        target_ndims = fine_geodata.ndims
        nwindows = coarse_geodata.ndims
        K = 2
        tkp = size(target_times, 1)
        fused_image = zeros(target_ndims[1], target_ndims[2], tkp)
        fused_sd_image = zeros(target_ndims[1], target_ndims[2], tkp)
        fused_bias_image = zeros(window_ndims[1], window_ndims[2], tkp)
        fused_bias_sd_image = zeros(window_ndims[1], window_ndims[2], tkp)
        inds = hcat(repeat(1:nwindows[1], inner=nwindows[2]), repeat(1:nwindows[2], outer=nwindows[1]))
        inst_geodata = [fine_geodata, coarse_geodata]
        n = size(inds, 1)
        
        for ii in 1:n
            k, l = inds[ii, :]
            bbox_centroid = window_origin .+ [k-1, l-1] .* window_csize
            window_bbox = bbox_from_centroid(bbox_centroid, window_csize)
            buffer_ext = window_bbox .+ window_buffer * [-1.01, 1.01] * target_csize'
            all_exts = Vector{AbstractMatrix{Float64}}(undef, K)
            for (i, x) in enumerate(inst_geodata)
                all_exts[i] = Matrix(find_overlapping_ext(buffer_ext[1, :], buffer_ext[2, :], x.origin, x.cell_size))
            end
            exx = window_bbox .+ [-nb_coarse - 0.01, nb_coarse + 0.01] * inst_geodata[2].cell_size'
            push!(all_exts, exx)
            full_ext = merge_extents(all_exts, sign.(target_csize))
            target_ij = find_all_ij_ext(window_bbox[1, :], window_bbox[2, :], target_origin, target_csize, target_ndims; inclusive=false)
            ss_target = find_all_ij_ext(buffer_ext[1, :], buffer_ext[2, :], target_origin, target_csize, target_ndims)
            ss_samp = sobol_bau_ij(full_ext[1, :], full_ext[2, :], target_origin, target_csize, target_ndims; nsamp=nsamp)
            bau_ij = unique(vcat(target_ij, ss_target, ss_samp), dims=1)
            bau_ci = CartesianIndex.(bau_ij[:, 1], bau_ij[:, 2])
            bau_xy = get_sij_from_ij(bau_ij, target_origin, target_csize)
            measurements = Vector{STARSInstrumentData}(undef, K)
            measurements[1] = @views STARSInstrumentData(fine_data.data[bau_ci, :], fine_data.bias, fine_data.uq, fine_data.dynamic_bias, fine_data.dynamic_bias_coefs, abs.(fine_geodata.cell_size), fine_geodata.dates, bau_xy)
            coarse_ij = find_all_ij_ext(full_ext[1, :], full_ext[2, :], coarse_geodata.origin, coarse_geodata.cell_size, coarse_geodata.ndims; inclusive=false)
            coarse_xy = get_sij_from_ij(coarse_ij, coarse_geodata.origin, coarse_geodata.cell_size)
            kp_bias = findall(sum(abs.(coarse_xy .- bbox_centroid'), dims=2)[:] .== 0)[1]
            pp = [kp_bias, 1:(kp_bias-1)..., (kp_bias+1):size(coarse_ij, 1)...]
            coarse_ci = CartesianIndex.(coarse_ij[pp, 1], coarse_ij[pp, 2])
            measurements[2] = @views STARSInstrumentData(coarse_data.data[coarse_ci, :], coarse_data.bias, coarse_data.uq, coarse_data.dynamic_bias, coarse_data.dynamic_bias_coefs, abs.(coarse_geodata.cell_size), coarse_geodata.dates, coarse_xy[pp, :])
            bau_coords = get_sij_from_ij(bau_ij, target_origin, target_csize)
            prior_mean_sub = @views prior_mean[bau_ci][:]
            prior_var_sub = @views prior_var[bau_ci][:]
            prior_bias_mean_sub = @views prior_bias_mean[coarse_ci][:]
            prior_bias_var_sub = @views prior_bias_var[coarse_ci][:]
            t_ind = CartesianIndex.(target_ij[:, 1], target_ij[:, 2])
            b_ind = CartesianIndex(coarse_ij[kp_bias, 1], coarse_ij[kp_bias, 2])
            model_pars_sub = model_pars[bau_ci, :]
            
            coarse_fine_fusion_cbias!(
                fused_image, fused_sd_image, fused_bias_image, fused_bias_sd_image,
                measurements, bau_coords, t_ind, b_ind,
                prior_mean_sub, prior_var_sub, prior_bias_mean_sub, prior_bias_var_sub, model_pars_sub;
                target_times = target_times, spatial_mod = spatial_mod, obs_operator = obs_operator, state_in_cov = state_in_cov, cov_wt = cov_wt
            )
        end
        return fused_image, fused_sd_image, fused_bias_image, fused_bias_sd_image
    end
end

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
downsampled_directory = ARGS[9]
@info "downsampled inputs directory: $(downsampled_directory)"
product_name = ARGS[10]
@info "Computing $(product_name) product"
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

coarse_start_date = VIIRS_start_date
coarse_end_date = VIIRS_end_date

coarse_dates = [coarse_start_date + Day(d - 1) for d in 1:((coarse_end_date - coarse_start_date).value + 1)]
coarse_image_filenames = [joinpath("$(downsampled_directory)", "$(year(date))", "$(Dates.format(date, dateformat"yyyy-mm-dd"))", "$(tile)", "STARS_$(product_name)_$(tile)_$(coarse_cell_size)m.tif") for date in coarse_dates]
coarse_image_filenames = [filename for filename in coarse_image_filenames if ispath(filename)]
coarse_dates_found = [Date(basename(dirname(dirname(filename)))) for filename in coarse_image_filenames]

fine_flag_start_date = HLS_end_date - Day(7)
fine_start_date = HLS_start_date
fine_end_date = HLS_end_date

dates = [fine_start_date + Day(d - 1) for d in 1:((fine_end_date - fine_start_date).value + 1)]
fine_image_filenames = [joinpath("$(downsampled_directory)", "$(year(date))", "$(Dates.format(date, dateformat"yyyy-mm-dd"))", "$(tile)", "STARS_$(product_name)_$(tile)_$(fine_cell_size)m.tif") for date in dates]
fine_image_filenames = [filename for filename in fine_image_filenames if ispath(filename)]
fine_dates_found = [Date(basename(dirname(dirname(filename)))) for filename in fine_image_filenames]

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
    else
        filename = coarse_image_filenames[match]
        @info "ingesting coarse image on $(date): $(filename)"
        covariance_image = Raster(reshape(Raster(filename), x_coarse_size, y_coarse_size, 1), dims=timestep_dims, missingval=NaN)
        replace!(covariance_image, missing => NaN)
    end

    push!(covariance_images, covariance_image)
end

@info "concatenating coarse images for covariance calculation"
covariance_images = Raster(cat(covariance_images..., dims=3), dims=covariance_dims, missingval=NaN)

n_eff = compute_n_eff(Int(round(coarse_cell_size / fine_cell_size)), 2, smoothness=1.5)
sp_var = fast_var_est(covariance_images, n_eff_agg = n_eff)

coarse_images = []
coarse_dates = Vector{Date}(undef, 0)

tk = 1
for (i, date) in enumerate(dates)
    date = Dates.format(date, dateformat"yyyy-mm-dd")
    matched = findfirst(x -> occursin(date, x), coarse_image_filenames)

    if matched === nothing
        @info "coarse image is not available on $(date)"
    else
        timestep_index = Band(tk:tk)
        timestep_dims = (x_coarse, y_coarse, timestep_index)
        filename = coarse_image_filenames[matched]
        @info "ingesting coarse image on $(date): $(filename)"
        coarse_image = Raster(reshape(Raster(filename), x_coarse_size, y_coarse_size, 1), dims=timestep_dims, missingval=NaN)
        replace!(coarse_image, missing => NaN)
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
    coarse_dates = [dates[1]]
else
    coarse_images = Raster(cat(coarse_images..., dims=3), dims=(coarse_dims[1:2]..., Band(1:length(coarse_dates))), missingval=NaN)
    coarse_array = Array{Float64}(coarse_images)
end

fine_images = []
fine_dates = Vector{Date}(undef, 0)

tk = 1
for (i, date) in enumerate(dates)
    date = Dates.format(date, dateformat"yyyy-mm-dd")
    match = findfirst(x -> occursin(date, x), fine_image_filenames)

    if match === nothing
        @info "fine image is not available on $(date)"
    else
        timestep_index = Band(tk:tk)
        timestep_dims = (x_fine, y_fine, timestep_index)
        filename = fine_image_filenames[match]
        @info "ingesting fine image on $(date): $(filename)"
        fine_image = Raster(reshape(Raster(filename), x_fine_size, y_fine_size, 1), dims=timestep_dims, missingval=NaN)
        replace!(fine_image, missing => NaN)
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
    fine_dates = [dates[1]]
else
    fine_images = Raster(cat(fine_images..., dims=3), dims=(fine_dims[1:2]..., Band(1:length(fine_dates))), missingval=NaN)
    fine_array = Array{Float64}(fine_images)
end

target_date = dates[end]
target_time = length(dates)

fine_pixels = sum(.!isnan.(fine_images), dims=3)
if sum(fine_pixels .== 0) > 0
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
                fine_pixels .+= sum(.!isnan.(fine_image), dims=3)
            end
        end
    end
end

hls_flag = Array(fine_pixels[:, :, 1] .== 0)

if isnothing(prior_mean)
    prior_flag = trues(size(fine_images)[1:2])
    fine_obs = sum(.!isnan.(fine_images), dims=3) 
    if sum(fine_obs .== 0) > 0
        coarse_nans = resample(sum(.!isnan.(coarse_images), dims=3), to=fine_images[:, :, 1], method=:near)
        prior_flag[coarse_nans[:, :, 1] .> 0] .= false
    end
    prior_flag[fine_pixels[:, :, 1] .> 0] .= false
elseif sum(isnan.(prior_mean)) .> 0
    prior_flag = isnan.(prior_mean[:, :, 1]) .> 0
    fine_obs = sum(.!isnan.(fine_images), dims=3) 
    if sum(fine_obs .== 0) > 0
        coarse_nans = resample(sum(.!isnan.(coarse_images), dims=3), to=fine_images[:, :, 1], method=:near)
        prior_flag[coarse_nans[:, :, 1] .> 0] .= false
    end
    prior_flag[fine_pixels[:, :, 1] .> 0] .= false
else
    prior_flag = falses(size(fine_images)[1:2])  
end

@info "running data fusion"

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

cov_pars = ones((size(fine_images)[1], size(fine_images)[2], 4))

sp_rs = resample(log.(sqrt.(sp_var[:, :, 1])); to=fine_images[:, :, 1], size=size(fine_images)[1:2], method=:cubicspline)
sp_rs[isnan.(sp_rs)] .= nanmean(sp_rs)

cov_pars[:, :, 1] = Array{Float64}(exp.(sp_rs))
cov_pars[:, :, 2] .= coarse_cell_size
cov_pars[:, :, 3] .= 1e-10
cov_pars[:, :, 4] .= 0.5

if isnothing(prior_mean)
    fused_images, fused_sd_images, fused_bias_images, fused_bias_sd_images = coarse_fine_scene_fusion_cbias_pmap(
        fine_data, coarse_data, fine_geodata, coarse_geodata,
        DEFAULT_MEAN .* ones(fine_ndims...),
        DEFAULT_SD^2 .* ones(fine_ndims...), 
        DEFAULT_BIAS_MEAN .* ones(coarse_ndims...),
        DEFAULT_BIAS_SD^2 .* ones(coarse_ndims...), 
        cov_pars;
        nsamp = nsamp, window_buffer = window_buffer, target_times = [target_time], 
        spatial_mod = exp_cor, obs_operator = unif_weighted_obs_operator_centroid,
        state_in_cov = false, cov_wt = 0.2, nb_coarse = 2.0
    );
else
    nkp = isnan.(prior_mean)
    if sum(nkp) > 0
        mp = nanmean(prior_mean)
        prior_mean[nkp] .= mp
    end

    fused_images, fused_sd_images, fused_bias_images, fused_bias_sd_images = coarse_fine_scene_fusion_cbias_pmap(
        fine_data, coarse_data, fine_geodata, coarse_geodata,
        prior_mean, prior_sd.^2, prior_bias_mean, prior_bias_sd.^2, 
        cov_pars;
        nsamp = nsamp, window_buffer = window_buffer, target_times = [target_time], 
        spatial_mod = exp_cor, obs_operator = unif_weighted_obs_operator_centroid,
        state_in_cov = false, cov_wt = 0.2, nb_coarse = 2.0
    );
end;

rmprocs(workers())

if occursin("NDVI", posterior_filename)
    clamp!(fused_images, -1, 1)
else 
    clamp!(fused_images, 0, 1)
end

dd = fused_images[:, :, :]
dd[prior_flag, :] .= NaN

function safe_write_geotiff(output_filename::String, template_filename::String, matrix_data::AbstractMatrix, nodata_val)
    mkpath(dirname(output_filename))
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
end

fine_template = if !isempty(fine_image_filenames)
    fine_image_filenames[1]
elseif ispath(posterior_filename)
    posterior_filename
else
    first(glob("*_$(fine_cell_size)m.tif", downsampled_directory))
end

coarse_template = if !isempty(coarse_image_filenames)
    coarse_image_filenames[1]
else
    first(glob("*_$(coarse_cell_size)m.tif", downsampled_directory))
end

@info "writing fused mean: $(posterior_filename)"
safe_write_geotiff(posterior_filename, fine_template, Float32.(dd[:, :, 1]), NaN32)

@info "writing fused flag: $(posterior_flag_filename)"
safe_write_geotiff(posterior_flag_filename, fine_template, Int32.(hls_flag), Int32(-9999))

@info "writing fused SD: $(posterior_UQ_filename)"
safe_write_geotiff(posterior_UQ_filename, fine_template, Float32.(fused_sd_images[:, :, 1]), NaN32)

@info "writing bias mean: $(posterior_bias_filename)"
safe_write_geotiff(posterior_bias_filename, coarse_template, Float32.(fused_bias_images[:, :, 1]), NaN32)

@info "writing bias SD: $(posterior_bias_UQ_filename)"
safe_write_geotiff(posterior_bias_UQ_filename, coarse_template, Float32.(fused_bias_sd_images[:, :, 1]), NaN32)