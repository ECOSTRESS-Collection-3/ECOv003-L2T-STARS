use faer::prelude::*;
use faer::{Mat, Side};
use rayon::prelude::*;

use crate::covariance::exp_cor;
use crate::sobol::sobol_bau_ij;
use crate::spatial::{
    bbox_from_centroid, find_all_ij_ext, find_overlapping_ext, get_sij_from_ij, merge_extents,
    unif_weighted_obs_operator_centroid,
};

pub struct FusionInputs<'a> {
    pub coarse_stack: &'a [f64],
    pub coarse_nx: usize,
    pub coarse_ny: usize,
    pub coarse_nt: usize,
    pub coarse_times: &'a [usize], // 1-based time indices
    pub fine_stack: &'a [f64],
    pub fine_nx: usize,
    pub fine_ny: usize,
    pub fine_nt: usize,
    pub fine_times: &'a [usize], // 1-based time indices
    pub coarse_origin: [f64; 2],
    pub coarse_cell_size: [f64; 2],
    pub fine_origin: [f64; 2],
    pub fine_cell_size: [f64; 2],
    pub prior_mean: &'a [f64],
    pub prior_var: &'a [f64],
    pub prior_bias_mean: &'a [f64],
    pub prior_bias_var: &'a [f64],
    pub cov_scale: &'a [f64],
    pub coarse_res_scalar: f64,
    pub target_time: usize, // 1-based target time index
    pub nsamp: usize,
    pub window_buffer: f64,
    pub nb_coarse: f64,
    pub cov_wt: f64,
}

struct WindowResult {
    target_ij: Vec<[usize; 2]>,
    bias_ij: [usize; 2],
    fused_mean: Vec<f64>,
    fused_sd: Vec<f64>,
    fused_bias: f64,
    fused_bias_sd: f64,
}

fn solve_window(k: usize, l: usize, inp: &FusionInputs<'_>) -> WindowResult {
    let window_csize = inp.coarse_cell_size;
    let target_csize = inp.fine_cell_size;
    let window_origin = inp.coarse_origin;
    let target_origin = inp.fine_origin;
    let target_ndims = [inp.fine_nx, inp.fine_ny];
    let coarse_ndims = [inp.coarse_nx, inp.coarse_ny];

    let bbox_centroid = [
        window_origin[0] + ((k - 1) as f64) * window_csize[0],
        window_origin[1] + ((l - 1) as f64) * window_csize[1],
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

    let ov_fine = find_overlapping_ext(buffer_ext[0], buffer_ext[1], target_origin, target_csize, false);
    let ov_coarse = find_overlapping_ext(buffer_ext[0], buffer_ext[1], window_origin, window_csize, false);
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

    let full_ext = merge_extents(
        &[ov_fine, ov_coarse, exx],
        [target_csize[0].signum(), target_csize[1].signum()],
    );

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
        false,
    );
    let ss_samp = sobol_bau_ij(
        full_ext[0],
        full_ext[1],
        target_origin,
        target_csize,
        target_ndims,
        inp.nsamp,
        false,
    );

    let mut bau_ij = Vec::with_capacity(target_ij.len() + ss_target.len() + ss_samp.len());
    for pair in target_ij.iter().chain(ss_target.iter()).chain(ss_samp.iter()) {
        if !bau_ij.contains(pair) {
            bau_ij.push(*pair);
        }
    }

    let nf = bau_ij.len();
    let nbau = target_ij.len();

    let bau_xy: Vec<[f64; 2]> = bau_ij
        .iter()
        .map(|&ij| get_sij_from_ij(ij, target_origin, target_csize))
        .collect();

    let coarse_ij = find_all_ij_ext(
        full_ext[0],
        full_ext[1],
        window_origin,
        window_csize,
        coarse_ndims,
        false,
    );
    let coarse_xy_raw: Vec<[f64; 2]> = coarse_ij
        .iter()
        .map(|&ij| get_sij_from_ij(ij, window_origin, window_csize))
        .collect();

    let kp_bias = coarse_xy_raw
        .iter()
        .position(|xy| (xy[0] - bbox_centroid[0]).abs() + (xy[1] - bbox_centroid[1]).abs() == 0.0)
        .unwrap_or(0);

    let mut coarse_ordered_ij = Vec::with_capacity(coarse_ij.len());
    let mut coarse_xy = Vec::with_capacity(coarse_ij.len());
    coarse_ordered_ij.push(coarse_ij[kp_bias]);
    coarse_xy.push(coarse_xy_raw[kp_bias]);
    for idx in 0..coarse_ij.len() {
        if idx != kp_bias {
            coarse_ordered_ij.push(coarse_ij[idx]);
            coarse_xy.push(coarse_xy_raw[idx]);
        }
    }

    let nc = coarse_ordered_ij.len();
    let n = nf + nc;

    let h_fine = unif_weighted_obs_operator_centroid(&bau_xy, &bau_xy, [target_csize[0].abs(), target_csize[1].abs()]);
    let h_coarse = unif_weighted_obs_operator_centroid(&coarse_xy, &bau_xy, [window_csize[0].abs(), window_csize[1].abs()]);

    let nrows_h = nf + nc;
    let mut h_full = vec![0.0f64; nrows_h * n];
    for r in 0..nf {
        for c in 0..nf {
            h_full[r * n + c] = h_fine[r * nf + c];
        }
    }
    for r in 0..nc {
        let out_r = nf + r;
        for c in 0..nf {
            h_full[out_r * n + c] = h_coarse[r * nf + c];
        }
        h_full[out_r * n + (nf + r)] = 1.0;
    }

    let qs = exp_cor(&bau_xy, inp.coarse_res_scalar, 1e-10);
    let mut q_mat = Mat::<f64>::zeros(n, n);
    let mut cvs = Vec::with_capacity(nf);
    for &[bi, bj] in &bau_ij {
        cvs.push(inp.cov_scale[(bi - 1) * inp.fine_ny + (bj - 1)]);
    }
    for i in 0..nf {
        for j in 0..nf {
            q_mat[(i, j)] = cvs[i] * qs[i * nf + j] * cvs[j];
        }
    }
    for b in 0..nc {
        q_mat[(nf + b, nf + b)] = 1e-6;
    }

    let mut mean = vec![0.0f64; n];
    let mut cov = Mat::<f64>::zeros(n, n);
    for (idx, &[bi, bj]) in bau_ij.iter().enumerate() {
        let flat = (bi - 1) * inp.fine_ny + (bj - 1);
        mean[idx] = inp.prior_mean[flat];
        cov[(idx, idx)] = inp.prior_var[flat];
    }
    for (b, &[ci, cj]) in coarse_ordered_ij.iter().enumerate() {
        let flat = (ci - 1) * inp.coarse_ny + (cj - 1);
        mean[nf + b] = inp.prior_bias_mean[flat];
        cov[(nf + b, nf + b)] = inp.prior_bias_var[flat];
    }

    let t0 = inp.fine_times.iter().chain(inp.coarse_times.iter()).copied().min().unwrap_or(1);
    let tp = inp.target_time;

    let mut fused_mean = vec![0.0f64; nbau];
    let mut fused_sd = vec![0.0f64; nbau];
    let mut fused_bias = 0.0f64;
    let mut fused_bias_sd = 0.0f64;

    let uq_obs = 1e-6f64;

    for t2 in t0..=tp {
        for r in 0..n {
            for c in 0..n {
                cov[(r, c)] += q_mat[(r, c)];
            }
        }

        let mut active_rows = Vec::new();
        let mut y_obs = Vec::new();

        if let Some(ft_idx) = inp.fine_times.iter().position(|&t| t == t2) {
            for (idx, &[bi, bj]) in bau_ij.iter().enumerate() {
                let val = inp.fine_stack[((bi - 1) * inp.fine_ny + (bj - 1)) * inp.fine_nt + ft_idx];
                if !val.is_nan() {
                    active_rows.push(idx);
                    y_obs.push(val);
                }
            }
        }

        if let Some(ct_idx) = inp.coarse_times.iter().position(|&t| t == t2) {
            for (b, &[ci, cj]) in coarse_ordered_ij.iter().enumerate() {
                let val = inp.coarse_stack[((ci - 1) * inp.coarse_ny + (cj - 1)) * inp.coarse_nt + ct_idx];
                if !val.is_nan() {
                    let row_idx = nf + b;
                    let has_fine_support = (0..nf).any(|c| h_full[row_idx * n + c] > 0.0);
                    if has_fine_support {
                        active_rows.push(row_idx);
                        y_obs.push(val);
                    }
                }
            }
        }

        let m = active_rows.len();
        if m > 0 {
            let mut ht = Mat::<f64>::zeros(m, n);
            for (r_out, &r_in) in active_rows.iter().enumerate() {
                for c in 0..n {
                    ht[(r_out, c)] = h_full[r_in * n + c];
                }
            }

            let mut res = vec![0.0f64; m];
            for r in 0..m {
                let mut pred_y = 0.0;
                for c in 0..n {
                    pred_y += ht[(r, c)] * mean[c];
                }
                res[r] = y_obs[r] - pred_y;
            }

            let mut hp_pt = Mat::<f64>::zeros(n, m);
            for i in 0..n {
                for r in 0..m {
                    let mut acc = 0.0;
                    for c in 0..n {
                        acc += cov[(i, c)] * ht[(r, c)];
                    }
                    hp_pt[(i, r)] = acc;
                }
            }

            let mut s_mat = Mat::<f64>::zeros(m, m);
            for r1 in 0..m {
                for r2 in 0..m {
                    let mut acc = 0.0;
                    for c in 0..n {
                        acc += ht[(r1, c)] * hp_pt[(c, r2)];
                    }
                    if r1 == r2 {
                        acc += uq_obs;
                    }
                    s_mat[(r1, r2)] = acc;
                }
            }

            let llt = s_mat
                .cholesky(Side::Lower)
                .expect("Innovation covariance S must be symmetric positive definite");
            let mut kt = hp_pt.transpose().to_owned();
            llt.solve_in_place(kt.as_mut());

            for i in 0..n {
                let mut delta = 0.0;
                for r in 0..m {
                    delta += kt[(r, i)] * res[r];
                }
                mean[i] += delta;
            }

            for i in 0..n {
                for j in 0..n {
                    let mut sub = 0.0;
                    for r in 0..m {
                        sub += kt[(r, i)] * hp_pt[(j, r)];
                    }
                    cov[(i, j)] -= sub;
                }
            }
        }

        if t2 == tp {
            for idx in 0..nbau {
                fused_mean[idx] = mean[idx];
                fused_sd[idx] = cov[(idx, idx)].sqrt();
            }
            fused_bias = mean[nf];
            fused_bias_sd = cov[(nf, nf)];
        }
    }

    WindowResult {
        target_ij,
        bias_ij: coarse_ordered_ij[0],
        fused_mean,
        fused_sd,
        fused_bias,
        fused_bias_sd,
    }
}

pub fn fuse_scene_parallel(inp: &FusionInputs<'_>, num_workers: usize) -> (Vec<f64>, Vec<f64>, Vec<f64>, Vec<f64>) {
    let nwindows = inp.coarse_nx * inp.coarse_ny;
    let mut windows = Vec::with_capacity(nwindows);
    for k in 1..=inp.coarse_nx {
        for l in 1..=inp.coarse_ny {
            windows.push((k, l));
        }
    }

    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(num_workers.max(1))
        .build()
        .expect("Failed to construct Rayon thread pool");

    let results: Vec<WindowResult> = pool.install(|| {
        windows
            .par_iter()
            .map(|&(k, l)| solve_window(k, l, inp))
            .collect()
    });

    let fine_len = inp.fine_nx * inp.fine_ny;
    let coarse_len = inp.coarse_nx * inp.coarse_ny;
    let mut fused_image = vec![0.0f64; fine_len];
    let mut fused_sd_image = vec![0.0f64; fine_len];
    let mut fused_bias_image = vec![0.0f64; coarse_len];
    let mut fused_bias_sd_image = vec![0.0f64; coarse_len];

    for res in results {
        for (idx, &[ti, tj]) in res.target_ij.iter().enumerate() {
            let flat = (ti - 1) * inp.fine_ny + (tj - 1);
            fused_image[flat] = res.fused_mean[idx];
            fused_sd_image[flat] = res.fused_sd[idx];
        }
        let bflat = (res.bias_ij[0] - 1) * inp.coarse_ny + (res.bias_ij[1] - 1);
        fused_bias_image[bflat] = res.fused_bias;
        fused_bias_sd_image[bflat] = res.fused_bias_sd;
    }

    (fused_image, fused_sd_image, fused_bias_image, fused_bias_sd_image)
}