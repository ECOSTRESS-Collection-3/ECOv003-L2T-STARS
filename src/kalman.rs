use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Instant;

use faer::linalg::matmul::matmul;
use faer::prelude::*;
use faer::{Mat, Parallelism};
use indicatif::{ProgressBar, ProgressStyle};
use ndarray::{Array2, ArrayView2, ArrayView3};
use rayon::prelude::*;

use crate::sobol::sobol_bau_ij;
use crate::spatial::{
    bbox_from_centroid, find_all_ij_ext, find_overlapping_ext, get_sij_from_ij, merge_extents,
};

pub struct FusionInputs<'a> {
    pub coarse_data: ArrayView3<'a, f64>, // (nx_c, ny_c, nt_c)
    pub coarse_dates: &'a [usize],         // 1-based time indices
    pub fine_data: ArrayView3<'a, f64>,   // (nx_f, ny_f, nt_f)
    pub fine_dates: &'a [usize],           // 1-based time indices
    pub coarse_origin: [f64; 2],
    pub coarse_csize: [f64; 2],
    pub fine_origin: [f64; 2],
    pub fine_csize: [f64; 2],
    pub prior_mean: ArrayView2<'a, f64>,
    pub prior_var: ArrayView2<'a, f64>,
    pub prior_bias_mean: ArrayView2<'a, f64>,
    pub prior_bias_var: ArrayView2<'a, f64>,
    pub cov_scale: ArrayView2<'a, f64>, // model_pars[:, :, 1]
    pub coarse_cell_size: f64,
    pub n_times: usize,
    pub nsamp: usize,
    pub window_buffer: f64,
    pub cov_wt: f64,
    pub phi: f64,
    pub ar_par: f64,
    pub nb_coarse: f64,
}

pub struct FusionOutputs {
    pub fused_mean: Array2<f64>,
    pub fused_sd: Array2<f64>,
    pub fused_bias: Array2<f64>,
    pub fused_bias_sd: Array2<f64>,
}

/// Port of Julia `coarse_fine_scene_fusion_cbias_pmap` + `coarse_fine_fusion_cbias_dict`.
pub fn run_scene_fusion(inp: &FusionInputs<'_>, num_workers: usize) -> FusionOutputs {
    let t_total = Instant::now();
    let window_csize = inp.coarse_csize;
    let target_csize = inp.fine_csize;
    let window_origin = inp.coarse_origin;
    let target_origin = inp.fine_origin;

    let window_ndims = [inp.coarse_data.shape()[0], inp.coarse_data.shape()[1]];
    let target_ndims = [inp.fine_data.shape()[0], inp.fine_data.shape()[1]];

    let n_win = window_ndims[0] * window_ndims[1];
    let mut win_indices = Vec::with_capacity(n_win);
    for k in 1..=window_ndims[0] {
        for l in 1..=window_ndims[1] {
            win_indices.push((k, l));
        }
    }

    let sgn_target = [
        if target_csize[0] >= 0.0 { 1.0 } else { -1.0 },
        if target_csize[1] >= 0.0 { 1.0 } else { -1.0 },
    ];
    let abs_fine_csize = [target_csize[0].abs(), target_csize[1].abs()];
    let abs_coarse_csize = [window_csize[0].abs(), window_csize[1].abs()];

    let t_pool = Instant::now();
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(num_workers.max(1))
        .build()
        .expect("failed to build rayon thread pool");
    let pool_init_sec = t_pool.elapsed().as_secs_f64();

    let pb = ProgressBar::new(n_win as u64);
    pb.set_style(
        ProgressStyle::with_template(
            "{spinner:.green} [{elapsed_precise}] [{bar:36.cyan/blue}] {pos}/{len} windows ({per_sec}, ETA {eta})",
        )
        .unwrap()
        .progress_chars("█▉▊▋▌▍▎▏ "),
    );
    let completed = AtomicUsize::new(0);

    let t_solve = Instant::now();
    let results: Vec<WindowResult> = pool.install(|| {
        win_indices
            .par_iter()
            .map(|&(k, l)| {
                let res = solve_window(
                    inp,
                    k,
                    l,
                    window_origin,
                    window_csize,
                    window_ndims,
                    target_origin,
                    target_csize,
                    target_ndims,
                    sgn_target,
                    abs_fine_csize,
                    abs_coarse_csize,
                );
                let prev = completed.fetch_add(1, Ordering::Relaxed) + 1;
                if prev & 63 == 0 || prev == n_win {
                    pb.set_position(prev as u64);
                }
                res
            })
            .collect()
    });
    let solve_sec = t_solve.elapsed().as_secs_f64();
    pb.finish_and_clear();

    let t_assemble = Instant::now();
    let mut fused_mean = Array2::<f64>::zeros((target_ndims[0], target_ndims[1]));
    let mut fused_sd = Array2::<f64>::zeros((target_ndims[0], target_ndims[1]));
    let mut fused_bias = Array2::<f64>::zeros((window_ndims[0], window_ndims[1]));
    let mut fused_bias_sd = Array2::<f64>::zeros((window_ndims[0], window_ndims[1]));

    for res in results {
        fused_bias[[res.bias_ij[0] - 1, res.bias_ij[1] - 1]] = res.bias_mean;
        fused_bias_sd[[res.bias_ij[0] - 1, res.bias_ij[1] - 1]] = res.bias_sd;
        for (idx, &[ti, tj]) in res.target_ij.iter().enumerate() {
            fused_mean[[ti - 1, tj - 1]] = res.target_mean[idx];
            fused_sd[[ti - 1, tj - 1]] = res.target_sd[idx];
        }
    }
    let assemble_sec = t_assemble.elapsed().as_secs_f64();
    let total_sec = t_total.elapsed().as_secs_f64();
    let win_per_sec = if solve_sec > 0.0 {
        (n_win as f64) / solve_sec
    } else {
        0.0
    };

    eprintln!(
        "[Rust] kernel timing breakdown: pool_init={:.3}s, kalman_solve={:.2}s ({:.1} windows/s), assemble={:.3}s, kernel_total={:.2}s",
        pool_init_sec, solve_sec, win_per_sec, assemble_sec, total_sec
    );

    FusionOutputs {
        fused_mean,
        fused_sd,
        fused_bias,
        fused_bias_sd,
    }
}

struct WindowResult {
    target_ij: Vec<[usize; 2]>,
    bias_ij: [usize; 2],
    target_mean: Vec<f64>,
    target_sd: Vec<f64>,
    bias_mean: f64,
    bias_sd: f64,
}

#[allow(clippy::too_many_arguments)]
fn solve_window(
    inp: &FusionInputs<'_>,
    k: usize,
    l: usize,
    window_origin: [f64; 2],
    window_csize: [f64; 2],
    window_ndims: [usize; 2],
    target_origin: [f64; 2],
    target_csize: [f64; 2],
    target_ndims: [usize; 2],
    sgn_target: [f64; 2],
    abs_fine_csize: [f64; 2],
    abs_coarse_csize: [f64; 2],
) -> WindowResult {
    let bbox_centroid = [
        window_origin[0] + (k - 1) as f64 * window_csize[0],
        window_origin[1] + (l - 1) as f64 * window_csize[1],
    ];
    let window_bbox = bbox_from_centroid(bbox_centroid, window_csize);

    let buffer_ext = [
        [
            window_bbox[0][0] + inp.window_buffer * (-1.01) * target_csize[0],
            window_bbox[0][1] + inp.window_buffer * 1.01 * target_csize[0],
        ],
        [
            window_bbox[1][0] + inp.window_buffer * (-1.01) * target_csize[1],
            window_bbox[1][1] + inp.window_buffer * 1.01 * target_csize[1],
        ],
    ];

    let ext_fine = find_overlapping_ext(buffer_ext[0], buffer_ext[1], target_origin, target_csize);
    let ext_coarse = find_overlapping_ext(buffer_ext[0], buffer_ext[1], window_origin, window_csize);
    let exx = [
        [
            window_bbox[0][0] + (-inp.nb_coarse - 0.01) * window_csize[0],
            window_bbox[0][1] + (inp.nb_coarse + 0.01) * window_csize[0],
        ],
        [
            window_bbox[1][0] + (-inp.nb_coarse - 0.01) * window_csize[1],
            window_bbox[1][1] + (inp.nb_coarse + 0.01) * window_csize[1],
        ],
    ];
    let full_ext = merge_extents(&[ext_fine, ext_coarse, exx], sgn_target);

    let target_ij = find_all_ij_ext(
        window_bbox[0],
        window_bbox[1],
        target_origin,
        target_csize,
        target_ndims,
        false,
    );
    let ss_target = find_all_ij_ext(
        buffer_ext[0],
        buffer_ext[1],
        target_origin,
        target_csize,
        target_ndims,
        true,
    );
    let ss_samp = sobol_bau_ij(
        full_ext[0],
        full_ext[1],
        target_origin,
        target_csize,
        target_ndims,
        inp.nsamp,
    );

    let mut bau_ij: Vec<[usize; 2]> =
        Vec::with_capacity(target_ij.len() + ss_target.len() + ss_samp.len());
    for &p in target_ij.iter().chain(ss_target.iter()).chain(ss_samp.iter()) {
        if !bau_ij.iter().any(|&q| q == p) {
            bau_ij.push(p);
        }
    }

    let nf = bau_ij.len();
    let n_kp = target_ij.len();
    let bau_xy = get_sij_from_ij(&bau_ij, target_origin, target_csize);

    let coarse_ij = find_all_ij_ext(
        full_ext[0],
        full_ext[1],
        window_origin,
        window_csize,
        window_ndims,
        false,
    );
    let coarse_xy = get_sij_from_ij(&coarse_ij, window_origin, window_csize);

    let kp_bias = coarse_xy
        .iter()
        .position(|&c| (c[0] - bbox_centroid[0]).abs() + (c[1] - bbox_centroid[1]).abs() == 0.0)
        .unwrap_or(0);

    let nb = coarse_ij.len();
    let mut pp = Vec::with_capacity(nb);
    pp.push(kp_bias);
    for idx in 0..nb {
        if idx != kp_bias {
            pp.push(idx);
        }
    }

    let n = nf + nb;

    let mut x_cur = vec![0.0f64; n];
    let mut p_cur = Mat::<f64>::zeros(n, n);
    let mut q_mat = Mat::<f64>::zeros(n, n);
    let mut sqrt_pars = vec![0.0f64; nf];

    for (idx, &[i, j]) in bau_ij.iter().enumerate() {
        let ii = i - 1;
        let jj = j - 1;
        x_cur[idx] = inp.prior_mean[[ii, jj]];
        p_cur[(idx, idx)] = inp.prior_var[[ii, jj]];
        sqrt_pars[idx] = inp.cov_scale[[ii, jj]];
    }

    // Q[1:nf, 1:nf] = cvs * exp_cor(target_coords', range, 1e-10) * cvs
    let inv_range = 1.0 / inp.coarse_cell_size;
    for r in 0..nf {
        let sr = sqrt_pars[r];
        let xr = bau_xy[r][0];
        let yr = bau_xy[r][1];
        q_mat[(r, r)] = sr * sr * (1.0 + 1e-10);
        for c in (r + 1)..nf {
            let dist = (xr - bau_xy[c][0]).hypot(yr - bau_xy[c][1]);
            let corr = (-dist * inv_range).exp();
            let val = sr * corr * sqrt_pars[c];
            q_mat[(r, c)] = val;
            q_mat[(c, r)] = val;
        }
    }

    // Bias states and diagonal process noise Q[(nf+1):end] = 1e-6
    let mut bias_ij_ordered = Vec::with_capacity(nb);
    let mut bias_xy_ordered = Vec::with_capacity(nb);
    for (b_pos, &orig_idx) in pp.iter().enumerate() {
        let [ci, cj] = coarse_ij[orig_idx];
        bias_ij_ordered.push([ci, cj]);
        bias_xy_ordered.push(coarse_xy[orig_idx]);
        let st = nf + b_pos;
        x_cur[st] = inp.prior_bias_mean[[ci - 1, cj - 1]];
        p_cur[(st, st)] = inp.prior_bias_var[[ci - 1, cj - 1]];
        q_mat[(st, st)] = 1e-6;
    }

    let hx = abs_coarse_csize[0] / 2.0 + 1e-12;
    let hy = abs_coarse_csize[1] / 2.0 + 1e-12;
    let mut h_coarse = vec![0.0f64; nb * nf];
    for r in 0..nb {
        let sx = bias_xy_ordered[r][0];
        let sy = bias_xy_ordered[r][1];
        let mut cnt = 0usize;
        for c in 0..nf {
            if (sx - bau_xy[c][0]).abs() <= hx && (sy - bau_xy[c][1]).abs() <= hy {
                h_coarse[r * nf + c] = 1.0;
                cnt += 1;
            }
        }
        if cnt > 0 {
            let inv_cnt = 1.0 / (cnt as f64);
            for c in 0..nf {
                h_coarse[r * nf + c] *= inv_cnt;
            }
        }
    }

    let fine_is_identity =
        (abs_fine_csize[0] - abs_coarse_csize[0]).abs() < 1e-12 && nf == nb;

    let mut x_pred = vec![0.0f64; n];
    let mut p_pred = Mat::<f64>::zeros(n, n);
    let max_m = nf + nb;
    let mut y_vec = Vec::with_capacity(max_m);
    let mut err_vars = Vec::with_capacity(max_m);
    let mut ht_buf = Mat::<f64>::zeros(max_m, n);
    let mut h_t_buf = Mat::<f64>::zeros(n, max_m);
    let mut hp_pt_buf = Mat::<f64>::zeros(n, max_m);
    let mut s_buf = Mat::<f64>::zeros(max_m, max_m);
    let mut rhs_buf = Mat::<f64>::zeros(max_m, n);
    let mut k_buf = Mat::<f64>::zeros(n, max_m);
    let mut hp_pred_buf = Mat::<f64>::zeros(max_m, n);
    let mut res_pred = Vec::with_capacity(max_m);

    let ar = inp.ar_par;
    let ar2 = ar * ar;

    for t in 1..=inp.n_times {
        for idx in 0..nf {
            x_pred[idx] = ar * x_cur[idx];
        }
        for idx in nf..n {
            x_pred[idx] = x_cur[idx];
        }
        for r in 0..n {
            for c in 0..n {
                let mult = if r < nf && c < nf {
                    ar2
                } else if r < nf || c < nf {
                    ar
                } else {
                    1.0
                };
                p_pred[(r, c)] = mult * p_cur[(r, c)] + q_mat[(r, c)];
            }
        }

        y_vec.clear();
        err_vars.clear();
        let mut m = 0usize;

        if let Some(f_pos) = inp.fine_dates.iter().position(|&d| d == t) {
            if fine_is_identity {
                for (r, &[bi, bj]) in bau_ij.iter().enumerate() {
                    let val = inp.fine_data[[bi - 1, bj - 1, f_pos]];
                    if !val.is_nan() {
                        for col in 0..n {
                            let h_val = if col == r { 1.0 } else { 0.0 };
                            ht_buf[(m, col)] = h_val;
                            h_t_buf[(col, m)] = h_val;
                        }
                        y_vec.push(val);
                        err_vars.push(1e-6);
                        m += 1;
                    }
                }
            } else {
                let fhx = abs_fine_csize[0] / 2.0 + 1e-12;
                let fhy = abs_fine_csize[1] / 2.0 + 1e-12;
                for (r, &[bi, bj]) in bau_ij.iter().enumerate() {
                    let val = inp.fine_data[[bi - 1, bj - 1, f_pos]];
                    if !val.is_nan() {
                        let sx = bau_xy[r][0];
                        let sy = bau_xy[r][1];
                        let mut cnt = 0usize;
                        for col in 0..n {
                            ht_buf[(m, col)] = 0.0;
                            h_t_buf[(col, m)] = 0.0;
                        }
                        for c in 0..nf {
                            if (sx - bau_xy[c][0]).abs() <= fhx && (sy - bau_xy[c][1]).abs() <= fhy
                            {
                                ht_buf[(m, c)] = 1.0;
                                cnt += 1;
                            }
                        }
                        if cnt > 0 {
                            let inv_cnt = 1.0 / (cnt as f64);
                            for c in 0..nf {
                                let h_val = ht_buf[(m, c)] * inv_cnt;
                                ht_buf[(m, c)] = h_val;
                                h_t_buf[(c, m)] = h_val;
                            }
                        }
                        y_vec.push(val);
                        err_vars.push(1e-6);
                        m += 1;
                    }
                }
            }
        }

        if let Some(c_pos) = inp.coarse_dates.iter().position(|&d| d == t) {
            for (r, &[ci, cj]) in bias_ij_ordered.iter().enumerate() {
                let val = inp.coarse_data[[ci - 1, cj - 1, c_pos]];
                if !val.is_nan() {
                    for c in 0..nf {
                        let h_val = h_coarse[r * nf + c];
                        ht_buf[(m, c)] = h_val;
                        h_t_buf[(c, m)] = h_val;
                    }
                    for b in 0..nb {
                        let h_val = if b == r { 1.0 } else { 0.0 };
                        ht_buf[(m, nf + b)] = h_val;
                        h_t_buf[(nf + b, m)] = h_val;
                    }
                    y_vec.push(val);
                    err_vars.push(1e-6);
                    m += 1;
                }
            }
        }

        if m == 0 {
            x_cur.copy_from_slice(&x_pred);
            p_cur.copy_from(&p_pred);
            continue;
        }

        let ht = ht_buf.as_ref().submatrix(0, 0, m, n);
        let h_t = h_t_buf.as_ref().submatrix(0, 0, n, m);
        let mut hp_pt = hp_pt_buf.as_mut().submatrix_mut(0, 0, n, m);
        let mut s_mat = s_buf.as_mut().submatrix_mut(0, 0, m, m);
        let mut rhs = rhs_buf.as_mut().submatrix_mut(0, 0, m, n);
        let mut k_mat = k_buf.as_mut().submatrix_mut(0, 0, n, m);
        let mut hp_pred = hp_pred_buf.as_mut().submatrix_mut(0, 0, m, n);

        matmul(
            hp_pt.as_mut(),
            p_pred.as_ref(),
            h_t,
            None,
            1.0,
            Parallelism::None,
        );

        matmul(
            s_mat.as_mut(),
            ht,
            hp_pt.as_ref(),
            None,
            1.0,
            Parallelism::None,
        );
        for idx in 0..m {
            s_mat[(idx, idx)] += err_vars[idx];
        }

        for r in 0..m {
            for c in 0..n {
                rhs[(r, c)] = hp_pt[(c, r)];
            }
        }
        match s_mat.as_ref().cholesky(faer::Side::Lower) {
            Ok(chol) => {
                chol.solve_in_place(rhs.as_mut());
            }
            Err(_) => {
                let lu = s_mat.as_ref().partial_piv_lu();
                lu.solve_in_place(rhs.as_mut());
            }
        }
        for r in 0..n {
            for c in 0..m {
                k_mat[(r, c)] = rhs[(c, r)];
            }
        }

        res_pred.clear();
        for r in 0..m {
            let mut hx = 0.0;
            for c in 0..n {
                hx += ht[(r, c)] * x_pred[c];
            }
            res_pred.push(y_vec[r] - hx);
        }

        for r in 0..n {
            let mut delta = 0.0;
            for c in 0..m {
                delta += k_mat[(r, c)] * res_pred[c];
            }
            x_cur[r] = x_pred[r] + delta;
        }

        matmul(
            hp_pred.as_mut(),
            ht,
            p_pred.as_ref(),
            None,
            1.0,
            Parallelism::None,
        );

        p_cur.copy_from(&p_pred);
        matmul(
            p_cur.as_mut(),
            k_mat.as_ref(),
            hp_pred.as_ref(),
            Some(1.0),
            -1.0,
            Parallelism::None,
        );
    }

    let mut target_mean = Vec::with_capacity(n_kp);
    let mut target_sd = Vec::with_capacity(n_kp);
    for idx in 0..n_kp {
        target_mean.push(x_cur[idx]);
        target_sd.push(p_cur[(idx, idx)].max(0.0).sqrt());
    }

    let bias_mean = x_cur[nf];
    let bias_sd = p_cur[(nf, nf)].max(0.0);

    WindowResult {
        target_ij,
        bias_ij: bias_ij_ordered[0],
        target_mean,
        target_sd,
        bias_mean,
        bias_sd,
    }
}
