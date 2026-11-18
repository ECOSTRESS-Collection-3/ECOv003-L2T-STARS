using Glob
using Dates
using Rasters
using DimensionalData.Dimensions.LookupArrays
using LinearAlgebra
using SparseArrays
using Sobol
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

@everywhere begin
    using LinearAlgebra
    using SparseArrays
    using Sobol
    using Statistics
    using Distributed

    BLAS.set_num_threads(1)

    nanmean(x) = mean(filter(!isnan, x))
    nanmean(x, y) = mapslices(nanmean, x, dims=y)
    nanvar(x) = var(filter(!isnan, x))

    struct STARSInstrumentData
        data::AbstractArray
        bias::Union{Float64, AbstractArray}
        uq::Union{Float64, AbstractArray}
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

    function find_nearest_ind(target::T, origin::T, cell_size::T) where T <: Real
        return Int(round((target - origin) / cell_size + 1))
    end

    function find_nearest_inds_ext(ext::AbstractVector{T}, origin::T, cellsize::T) where T <: Real
        ind1 = (ext[1] - origin) / cellsize + 1
        ind2 = (ext[2] - origin) / cellsize + 1
        return [Int(ceil(ind1)), Int(floor(ind2))]
    end

    function find_all_ij_ext(ext_ti::AbstractVector{T}, ext_tj::AbstractVector{T}, origin::AbstractVector{T}, cellsize::AbstractVector{T}, n_dims::AbstractVector{<:Real}; inclusive=false) where T <: Real
        oi, oj = origin
        c, r = cellsize

        if !inclusive
            ext_ti = ext_ti .- sign(c) * [0, 1e-8]
            ext_tj = ext_tj .- sign(r) * [0, 1e-8]
        end

        is = find_nearest_inds_ext(ext_ti, oi, c)
        js = find_nearest_inds_ext(ext_tj, oj, r)

        if any(is .> 0) & any(js .> 0) & any(is .<= n_dims[1]) & any(js .<= n_dims[2])
            is[is .< 1] .= 1
            js[js .< 1] .= 1

            is[is .> n_dims[1]] .= n_dims[1]
            js[js .> n_dims[2]] .= n_dims[2]

            iss = repeat(is[1]:is[2], inner=js[2] - js[1] + 1, outer=[1])
            jss = repeat(js[1]:js[2], inner=[1], outer=is[2] - is[1] + 1)

            return unique(hcat(iss, jss), dims=1)
        else
            return Array{Int64}(undef, 0, 0)
        end
    end

    function sobol_bau_ij(ext_ti::AbstractVector{T}, ext_tj::AbstractVector{T}, origin::AbstractVector{T}, cell_size::AbstractVector{T}, n_dims::AbstractVector{<:Real}; nsamp=100, inclusive=false) where T <: Real
        oi, oj = origin
        c, r = cell_size

        if !inclusive
            ext_ti = ext_ti .- sign(c) * [0, 1e-9]
            ext_tj = ext_tj .- sign(r) * [0, 1e-9]
        end

        is = find_nearest_ind.(ext_ti, oi, c)
        js = find_nearest_ind.(ext_tj, oj, r)

        if any(is .> 0) & any(js .> 0) & any(is .<= n_dims[1]) & any(js .<= n_dims[2])
            is[is .< 1] .= 1
            js[js .< 1] .= 1

            is[is .> n_dims[1]] .= n_dims[1]
            js[js .> n_dims[2]] .= n_dims[2]

            ni = is[2] - is[1] + 1
            nj = js[2] - js[1] + 1

            if nsamp >= ni * nj
                iss = repeat(is[1]:is[2], inner=[nj], outer=[1])
                jss = repeat(js[1]:js[2], inner=[1], outer=[ni])
                dd = unique(hcat(iss, jss), dims=1)
            else
                s = SobolSeq([is[1], js[1]], [is[2], js[2]])
                p = reduce(hcat, Sobol.next!(s) for i = 1:nsamp)'
                dd = Int64.(unique(round.(p), dims=1))
            end

            return dd
        else
            return Array{Int64}(undef, 0, 0)
        end
    end

    function get_sij_from_ij(ij_array::AbstractArray{<:Real}, origin::AbstractVector{T}, cell_size::AbstractVector{T}) where T <: Real
        origin' .+ cell_size' .* (ij_array .- [1., 1.]')
    end

    function bbox_from_centroid(target::AbstractVector{T}, cell_size::AbstractVector{T}) where T <: Real
        return ones(2, 2) .* [-0.5 0.5] .* cell_size .+ target
    end

    function find_overlapping_ext(ext_ti::AbstractVector{T}, ext_tj::AbstractVector{T}, origin::AbstractVector{T}, cell_size::AbstractVector{T}; inclusive=false) where T <: Real
        oi, oj = origin
        c, r = cell_size

        if !inclusive
            ext_ti = ext_ti .- sign(c) * [0, 1e-9]
            ext_tj = ext_tj .- sign(r) * [0, 1e-9]
        end

        is = find_nearest_ind.(ext_ti, oi, c)
        js = find_nearest_ind.(ext_tj, oj, r)

        si = oi .+ c * (is .- 1.)
        sj = oj .+ r * (js .- 1.)

        ext_ovi = si .+ [-0.5, 0.5] .* cell_size[1]
        ext_ovj = sj .+ [-0.5, 0.5] .* cell_size[2]

        return hcat(ext_ovi, ext_ovj)'
    end

    function merge_extents(exts::AbstractVector{<:AbstractArray}, sgns)
        aa = hcat(exts...)
        mms = extrema(aa, dims=2)
        es = hcat(first.(mms), last.(mms))

        if sign(sgns[1]) == -1
            es[1, :] = reverse(es[1, :])
        end
        if sign(sgns[2]) == -1
            es[2, :] = reverse(es[2, :])
        end

        return es
    end

    function _pairwise_col_euclidean(X::AbstractMatrix{T})::Matrix{Float64} where T <: Real
        n = size(X, 2)
        D = zeros(Float64, n, n)
        @inbounds for j in 1:n
            xj1 = Float64(X[1, j])
            xj2 = Float64(X[2, j])
            for i in (j + 1):n
                dx = Float64(X[1, i]) - xj1
                dy = Float64(X[2, i]) - xj2
                d = hypot(dx, dy)
                D[i, j] = d
                D[j, i] = d
            end
        end
        return D
    end

    function exp_cor(X::AbstractArray{T}, pars::AbstractVector{T}) where {T <: Real}
        σ = pars[1]
        reg = pars[2]
        D = _pairwise_col_euclidean(X)
        C = exp.(-D ./ σ)
        @inbounds for i in 1:size(C, 1)
            C[i, i] += reg
        end
        return C
    end

    function unif_weighted_obs_operator_centroid(sensor::AbstractArray{T}, target::AbstractArray{T}, sensor_res::AbstractVector{T}) where T <: Real
        if sensor == target
            n = size(target, 1)
            return sparse(1.0I, n, n)
        else
            ns = size(sensor, 1)
            nt = size(target, 1)
            hx = sensor_res[1] / 2 + 1e-12
            hy = sensor_res[2] / 2 + 1e-12
            H = zeros(Float64, ns, nt)
            @inbounds for i in 1:ns
                sx = sensor[i, 1]
                sy = sensor[i, 2]
                cnt = 0
                for j in 1:nt
                    if abs(sx - target[j, 1]) <= hx && abs(sy - target[j, 2]) <= hy
                        H[i, j] = 1.0
                        cnt += 1
                    end
                end
                if cnt > 0
                    inv_cnt = 1.0 / cnt
                    for j in 1:nt
                        H[i, j] *= inv_cnt
                    end
                end
            end
            return sparse(H)
        end
    end

    function kalman_filter!(x_new::AbstractVector{T}, P_new::AbstractMatrix{T},
            Ht::Union{AbstractSparseMatrix{T}, AbstractMatrix{T}},
            y::AbstractVector{T}, err_vars::AbstractVector{T},
            x_pred::AbstractVector{T},
            P_pred::AbstractMatrix{T}) where T <: Real

        res_pred = y - Ht * x_pred
        HPpT = P_pred * Ht'

        S = Ht * HPpT
        @inbounds for idx in eachindex(err_vars)
            S[idx, idx] += err_vars[idx]
        end

        LAPACK.potrf!('U', S)
        LAPACK.potri!('U', S)
        K = BLAS.symm('R', 'U', S, HPpT)

        x_new .= x_pred
        mul!(x_new, K, res_pred, 1.0, 1.0)

        HP_pred = Ht * P_pred
        P_new .= P_pred
        mul!(P_new, K, HP_pred, -1.0, 1.0)
    end

    function coarse_fine_fusion_cbias_dict(d,
            target_times = [1],
            spatial_mod::Function = exp_cor,
            obs_operator::Function = unif_weighted_obs_operator_centroid,
            state_in_cov::Bool = false,
            cov_wt::AbstractFloat = 0.3,
            phi::AbstractFloat = 0.001,
            ar_par::AbstractFloat = 1.0)

        measurements = @views d[:measurements]
        target_coords = @views d[:target_coords]
        kp_ij = @views d[:kp_ij]
        kp_bias_ij = @views d[:kp_bias_ij]
        prior_mean = @views d[:prior_mean]
        prior_var = @views d[:prior_var]
        prior_bias_mean = @views d[:prior_bias_mean]
        prior_bias_var = @views d[:prior_bias_var]
        model_pars = @views d[:model_pars]

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
        tp = maximum(target_times)
        times = t0:tp
        nsteps = size(times)[1]

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
                Hbb = [spzeros(x, x) for x in nn_biases]
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
        cvs = Diagonal(model_pars[:, 1])

        Qs = spatial_mod(target_coords', model_pars[1, 2:end])
        @views Q[1:nf, 1:nf] = cvs * Qs * cvs

        if length(Fb) > 0
            F = Diagonal([ar_par .* ones(nf)..., Fb...])
            @views Q[diagind(Q)[(nf + 1):end]] = [Qb...]
        else
            F = UniformScaling(ar_par)
        end

        nb = length(prior_bias_mean)
        n = nf + nb

        filtering_means = zeros(n, nsteps + 1)
        filtering_covs = zeros(n, n, nsteps + 1)
        filtering_prec = zeros(nf, nsteps + 1)

        @views filtering_means[1:nf, 1] = prior_mean
        @views filtering_means[(nf + 1):end, 1] = prior_bias_mean
        @views filtering_prec[1:nf, 1] = 1 ./ sqrt.(prior_var[1:nf])

        @views filtering_covs[diagind(filtering_covs[:, :, 1])[1:nf]] = prior_var
        @views filtering_covs[diagind(filtering_covs[:, :, 1])[(nf + 1):end]] = prior_bias_var

        x_pred = zeros(n)
        P_pred = zeros(n, n)
        x_new = zeros(n)
        P_new = zeros(n, n)
        Qss = state_in_cov ? zeros(nf, nf) : zeros(0, 0)
        FPpred = similar(P_pred)
        Qf = state_in_cov ? zeros(n, n) : Q

        nbau = size(kp_ij, 1)
        nbias = size(kp_bias_ij, 1)

        fused_image = zeros(nbau, size(target_times, 1))
        fused_sd_image = zeros(nbau, size(target_times, 1))
        fused_bias_image = zeros(nbias, size(target_times, 1))
        fused_bias_sd_image = zeros(nbias, size(target_times, 1))

        tk = 1
        for (t, t2) in enumerate(t0:tp)
            if state_in_cov
                Qf .= Q
                if t > 1
                    Xtt = @views filtering_means[1:nf, 2:t]
                    Wt = @views filtering_prec[:, 2:t] ./ sum(filtering_prec[:, 2:t], dims=2)
                    XW = Xtt .* Wt
                    @inbounds for j in 1:nf, i in 1:nf
                        s = 0.0
                        for c in axes(XW, 2)
                            d = XW[i, c] - XW[j, c]
                            s += d * d
                        end
                        Qss[i, j] = sqrt(s)
                    end
                    Qss ./= phi
                    Qss .= cvs * exp.(-Qss) * cvs + UniformScaling(1e-10)
                    Qss .*= (1.0 .- cov_wt)
                    @view(Qf[1:nf, 1:nf]) .*= cov_wt
                    @view(Qf[1:nf, 1:nf]) .+= Qss
                end
            end

            if !any(data_kp[:, t])
                ys = fill(NaN, 1)
                err_vars = fill(NaN, 1)
                kp = BitVector([1])
                Ht = H
            else
                ys = Float64[]
                err_vars = Float64[]
                yms = Int64[]
                nii = 0
                for x in 1:2
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
                if length(yms) == 1
                    Ht = reshape(Ht, 1, n)
                end
                kp = sum(Ht[:, 1:nf], dims=2)[:] .> 0
            end

            P_pred .= Qf
            mul!(x_pred, F, @view(filtering_means[:, t]))
            mul!(FPpred, F, @view(filtering_covs[:, :, t]))
            mul!(P_pred, FPpred, F', 1.0, 1.0)

            if sum(.!isnan.(ys[kp])) == 0
                filtering_means[:, t + 1] = x_pred
                filtering_covs[:, :, t + 1] = P_pred
                filtering_prec[:, t + 1] = 1.0 ./ sqrt.(diag(P_pred)[1:nf])
            else
                kalman_filter!(x_new, P_new, Ht[kp, :], ys[kp], err_vars[kp], x_pred, P_pred)
                filtering_means[:, t + 1] = x_new
                filtering_covs[:, :, t + 1] = P_new
                filtering_prec[:, t + 1] = 1.0 ./ sqrt.(diag(P_new)[1:nf])
            end

            if t2 .∈ Ref(target_times)
                fused_image[:, tk] = @views filtering_means[1:nbau, t + 1]
                fused_sd_image[:, tk] = @views 1.0 ./ filtering_prec[1:nbau, t + 1]

                fused_bias_image[:, tk] .= @views filtering_means[nf + 1, t + 1]
                fused_bias_sd_image[:, tk] .= @views filtering_covs[nf + 1, nf + 1, t + 1]
                tk += 1
            end
        end
        return kp_ij, kp_bias_ij, fused_image, fused_sd_image, fused_bias_image, fused_bias_sd_image
    end
end

function get_origin_raster(rast::Raster)
    return [rast.dims[1].val[1], rast.dims[2].val[1]]
end

function get_centroid_origin_raster(rast::Raster)
    cc = abs.(collect(cell_size(rast)))
    return [rast.dims[1].val[1], rast.dims[2].val[1]] .+ cc ./ 2
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
    width = xmax - xmin
    height = ymax - ymin
    cell_width = width / rows
    cell_height = -height / cols
    return cell_width, cell_height
end

function compute_n_eff(agg_scale::Int, range::Real; smoothness=0.5)
    subsample_inds = hcat(
        repeat(1:agg_scale, inner=[1], outer=[agg_scale]),
        repeat(1:agg_scale, inner=[agg_scale], outer=[1])
    )'
    n = size(subsample_inds)[2]
    dd = _pairwise_col_euclidean(subsample_inds)
    # Match GaussianRandomFields.Matern(range, smoothness) parameterization
    if smoothness == 1.5
        s = dd ./ range
        K = exp.(-s) .* (1.0 .+ s)
    elseif smoothness == 0.5
        K = exp.(-dd ./ range)
    else
        error("unsupported smoothness $(smoothness)")
    end
    @inbounds for i in 1:n
        K[i, i] += 1e-16
    end
    return n^2 / sum(K)
end

function fast_var_est(coarse_images::Raster; n_eff_agg = 50, min_num_obs = 8, default_var = 1e-4)
    arr = parent(coarse_images)
    nx, ny, nt = size(arr)
    result = fill(Float64(default_var), nx, ny, 1)
    diffs = Vector{Float64}(undef, max(nt - 1, 0))

    @inbounds for j in 1:ny, i in 1:nx
        cnt = 0
        for t in 1:nt
            if !isnan(arr[i, j, t])
                cnt += 1
            end
        end
        if cnt >= min_num_obs && nt > 1
            nd = 0
            for t in 1:(nt - 1)
                d = arr[i, j, t + 1] - arr[i, j, t]
                if !isnan(d)
                    nd += 1
                    diffs[nd] = d
                end
            end
            if nd >= 2
                result[i, j, 1] = var(@view(diffs[1:nd])) * n_eff_agg
            end
        end
    end

    return Raster(result, dims=(coarse_images.dims[1], coarse_images.dims[2], Band(1:1)), missingval=NaN)
end

function sentinel_tile_dims_from_template(template_filename::String, cell_size::Union{Float64, Int64})::Tuple{X, Y}
    template_rast = Raster(template_filename)
    crs = Rasters.crs(template_rast)
    bbox = Rasters.bounds(template_rast)
    xmin, xmax = bbox[1]
    ymin, ymax = bbox[2]
    cols = Int(trunc((ymax - ymin) / cell_size))
    rows = Int(trunc((xmax - xmin) / cell_size))
    x_dim = X(Projected(LinRange(xmin, xmin + (rows - 1) * cell_size, rows), order=ForwardOrdered(), span=Regular(cell_size), sampling=Intervals(Start()), crs=crs))
    y_dim = Y(Projected(LinRange(ymax - cell_size, ymax - cols * cell_size, cols), order=ReverseOrdered(), span=Regular(-cell_size), sampling=Intervals(Start()), crs=crs))
    return (x_dim, y_dim)
end

function coarse_fine_scene_fusion_cbias_pmap(fine_data, coarse_data,
        fine_geodata, coarse_geodata,
        prior_mean::AbstractArray,
        prior_var::AbstractArray,
        prior_bias_mean::AbstractArray,
        prior_bias_var::AbstractArray,
        model_pars::AbstractArray;
        nsamp = 100,
        window_buffer = 2,
        target_times = [1],
        spatial_mod::Function = exp_cor,
        obs_operator::Function = unif_weighted_obs_operator_centroid,
        state_in_cov::Bool = false,
        cov_wt::AbstractFloat = 0.2,
        phi::AbstractFloat = 0.001,
        ar_par::AbstractFloat = 1.0,
        nb_coarse = 2.0,
        batchsize = 1)

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
    T = Vector{Dict{Symbol, Any}}(undef, n)

    for ii in 1:n
        k, l = inds[ii, :]
        bbox_centroid = window_origin .+ [k - 1, l - 1] .* window_csize
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

        fine_sub = fine_data.data[bau_ci, :]
        coarse_ij = find_all_ij_ext(full_ext[1, :], full_ext[2, :], coarse_geodata.origin, coarse_geodata.cell_size, coarse_geodata.ndims; inclusive=false)
        coarse_xy = get_sij_from_ij(coarse_ij, coarse_geodata.origin, coarse_geodata.cell_size)

        kp_bias = findall(sum(abs.(coarse_xy .- bbox_centroid'), dims=2)[:] .== 0)[1]
        pp = [kp_bias, 1:(kp_bias - 1)..., (kp_bias + 1):size(coarse_ij, 1)...]
        coarse_ci = CartesianIndex.(coarse_ij[pp, 1], coarse_ij[pp, 2])
        coarse_sub = coarse_data.data[coarse_ci, :]

        t_ind = CartesianIndex.(target_ij[:, 1], target_ij[:, 2])
        b_ind = CartesianIndex.(coarse_ij[kp_bias:kp_bias, 1], coarse_ij[kp_bias:kp_bias, 2])

        measurements = Vector{STARSInstrumentData}(undef, K)
        measurements[1] = STARSInstrumentData(
            fine_sub,
            fine_data.bias,
            fine_data.uq,
            fine_data.dynamic_bias,
            fine_data.dynamic_bias_coefs,
            abs.(fine_geodata.cell_size),
            fine_geodata.dates,
            bau_xy
        )
        measurements[2] = STARSInstrumentData(
            coarse_sub,
            coarse_data.bias,
            coarse_data.uq,
            coarse_data.dynamic_bias,
            coarse_data.dynamic_bias_coefs,
            abs.(coarse_geodata.cell_size),
            coarse_geodata.dates,
            coarse_xy[pp, :]
        )

        bau_coords = get_sij_from_ij(bau_ij, target_origin, target_csize)
        prior_mean_sub = @views prior_mean[bau_ci][:]
        prior_var_sub = @views prior_var[bau_ci][:]
        prior_bias_mean_sub = @views prior_bias_mean[coarse_ci][:]
        prior_bias_var_sub = @views prior_bias_var[coarse_ci][:]
        model_pars_sub = model_pars[bau_ci, :]

        T[ii] = Dict{Symbol, Any}(
            :measurements => measurements,
            :target_coords => bau_coords,
            :kp_ij => t_ind,
            :kp_bias_ij => b_ind,
            :prior_mean => prior_mean_sub,
            :prior_var => prior_var_sub,
            :prior_bias_mean => prior_bias_mean_sub,
            :prior_bias_var => prior_bias_var_sub,
            :model_pars => model_pars_sub
        )
    end

    @info "dispatching $(n) spatial windows across $(nworkers()) workers"
    result = pmap(
        x -> coarse_fine_fusion_cbias_dict(
            x,
            target_times,
            spatial_mod,
            obs_operator,
            state_in_cov,
            cov_wt,
            phi,
            ar_par
        ),
        T;
        batch_size = batchsize
    )

    for i in 1:n
        @views fused_image[result[i][1], :] = result[i][3]
        @views fused_sd_image[result[i][1], :] = result[i][4]

        @views fused_bias_image[result[i][2], :] = result[i][5]
        @views fused_bias_sd_image[result[i][2], :] = result[i][6]
    end

    return fused_image, fused_sd_image, fused_bias_image, fused_bias_sd_image
end

t_workers_sec = elapsed_sec(t_workers_start)
@info "worker startup and inline setup completed in $(t_workers_sec) s"

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

dim_reference_file = if !isempty(fine_file_by_date)
    first(values(fine_file_by_date))
elseif !isempty(coarse_file_by_date)
    first(values(coarse_file_by_date))
elseif size(ARGS)[1] >= 16 && ispath(ARGS[16])
    ARGS[16]
else
    first(glob("*_$(tile)_*.tif", downsampled_directory))
end

x_coarse, y_coarse = sentinel_tile_dims_from_template(dim_reference_file, coarse_cell_size)
x_coarse_size = size(x_coarse)[1]
y_coarse_size = size(y_coarse)[1]
@info "coarse x size: $(x_coarse_size)"
@info "coarse y size: $(y_coarse_size)"
x_fine, y_fine = sentinel_tile_dims_from_template(dim_reference_file, fine_cell_size)
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

t = Ti(dates)
coarse_dims = (x_coarse, y_coarse, t)
fine_dims = (x_fine, y_fine, t)

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