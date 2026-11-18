use rayon::prelude::*;

pub fn compute_n_eff(agg_scale: usize, range: f64, smoothness: f64) -> f64 {
    let n = agg_scale * agg_scale;
    let mut inds = Vec::with_capacity(n);
    for i in 1..=agg_scale {
        for j in 1..=agg_scale {
            inds.push([i as f64, j as f64]);
        }
    }

    let mut total_k = 0.0f64;
    for a in 0..n {
        for b in 0..n {
            let d = (inds[a][0] - inds[b][0]).hypot(inds[a][1] - inds[b][1]);
            let mut k = if (smoothness - 1.5).abs() < 1e-12 {
                let s = d / range;
                (-s).exp() * (1.0 + s)
            } else {
                (-d / range).exp()
            };
            if a == b {
                k += 1e-16;
            }
            total_k += k;
        }
    }
    ((n * n) as f64) / total_k
}

/// Parallel spatial variance estimator matching `fast_var_est` (`shape = [nx, ny, nt]`).
pub fn fast_var_est(
    coarse_cov: &[f64],
    nx: usize,
    ny: usize,
    nt: usize,
    n_eff_agg: f64,
    min_num_obs: usize,
    default_var: f64,
) -> Vec<f64> {
    let mut out = vec![default_var; nx * ny];
    if nt <= 1 {
        return out;
    }

    out.par_iter_mut().enumerate().for_each(|(idx, cell_out)| {
        let i = idx / ny;
        let j = idx % ny;
        let base = (i * ny + j) * nt;

        let mut cnt = 0usize;
        for t in 0..nt {
            if !coarse_cov[base + t].is_nan() {
                cnt += 1;
            }
        }
        if cnt < min_num_obs {
            return;
        }

        let mut diffs = Vec::with_capacity(nt - 1);
        for t in 0..(nt - 1) {
            let d = coarse_cov[base + t + 1] - coarse_cov[base + t];
            if !d.is_nan() {
                diffs.push(d);
            }
        }
        let nd = diffs.len();
        if nd >= 2 {
            let mean = diffs.iter().sum::<f64>() / (nd as f64);
            let var = diffs
                .iter()
                .map(|&v| {
                    let delta = v - mean;
                    delta * delta
                })
                .sum::<f64>()
                / ((nd - 1) as f64);
            *cell_out = var * n_eff_agg;
        }
    });

    out
}

/// Exponential correlation matrix `exp(-d / sigma) + reg * I` for `coords` of length `nf`.
pub fn exp_cor(coords: &[[f64; 2]], sigma: f64, reg: f64) -> Vec<f64> {
    let nf = coords.len();
    let mut c = vec![0.0f64; nf * nf];
    for j in 0..nf {
        c[j * nf + j] = 1.0 + reg;
        for i in (j + 1)..nf {
            let d = (coords[i][0] - coords[j][0]).hypot(coords[i][1] - coords[j][1]);
            let val = (-d / sigma).exp();
            c[i * nf + j] = val;
            c[j * nf + i] = val;
        }
    }
    c
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_compute_n_eff_matches_julia() {
        let n_eff_7 = compute_n_eff(7, 2.0, 1.5);
        assert!((n_eff_7 - 2.002616).abs() < 1e-5);
    }
}
