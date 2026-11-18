#[inline]
pub fn find_nearest_ind(target: f64, origin: f64, cell_size: f64) -> isize {
    ((target - origin) / cell_size + 1.0).round() as isize
}

#[inline]
pub fn find_nearest_inds_ext(ext: [f64; 2], origin: f64, cellsize: f64) -> [isize; 2] {
    let ind1 = (ext[0] - origin) / cellsize + 1.0;
    let ind2 = (ext[1] - origin) / cellsize + 1.0;
    [ind1.ceil() as isize, ind2.floor() as isize]
}

pub fn find_all_ij_ext(
    ext_ti: [f64; 2],
    ext_tj: [f64; 2],
    origin: [f64; 2],
    cellsize: [f64; 2],
    n_dims: [usize; 2],
    inclusive: bool,
) -> Vec<[usize; 2]> {
    let (oi, oj) = (origin[0], origin[1]);
    let (c, r) = (cellsize[0], cellsize[1]);

    let mut eti = ext_ti;
    let mut etj = ext_tj;
    if !inclusive {
        eti[1] -= c.signum() * 1e-8;
        etj[1] -= r.signum() * 1e-8;
    }

    let mut is = find_nearest_inds_ext(eti, oi, c);
    let mut js = find_nearest_inds_ext(etj, oj, r);
    let nx = n_dims[0] as isize;
    let ny = n_dims[1] as isize;

    if (is[0] > 0 || is[1] > 0)
        && (js[0] > 0 || js[1] > 0)
        && (is[0] <= nx || is[1] <= nx)
        && (js[0] <= ny || js[1] <= ny)
    {
        is[0] = is[0].clamp(1, nx);
        is[1] = is[1].clamp(1, nx);
        js[0] = js[0].clamp(1, ny);
        js[1] = js[1].clamp(1, ny);

        let mut out = Vec::with_capacity(((is[1] - is[0] + 1) * (js[1] - js[0] + 1)) as usize);
        for i in is[0]..=is[1] {
            for j in js[0]..=js[1] {
                let pair = [i as usize, j as usize];
                if !out.contains(&pair) {
                    out.push(pair);
                }
            }
        }
        out
    } else {
        Vec::new()
    }
}

#[inline]
pub fn get_sij_from_ij(ij: [usize; 2], origin: [f64; 2], cell_size: [f64; 2]) -> [f64; 2] {
    [
        origin[0] + cell_size[0] * ((ij[0] as f64) - 1.0),
        origin[1] + cell_size[1] * ((ij[1] as f64) - 1.0),
    ]
}

#[inline]
pub fn bbox_from_centroid(target: [f64; 2], cell_size: [f64; 2]) -> [[f64; 2]; 2] {
    [
        [target[0] - 0.5 * cell_size[0], target[0] + 0.5 * cell_size[0]],
        [target[1] - 0.5 * cell_size[1], target[1] + 0.5 * cell_size[1]],
    ]
}

pub fn find_overlapping_ext(
    ext_ti: [f64; 2],
    ext_tj: [f64; 2],
    origin: [f64; 2],
    cell_size: [f64; 2],
    inclusive: bool,
) -> [[f64; 2]; 2] {
    let (oi, oj) = (origin[0], origin[1]);
    let (c, r) = (cell_size[0], cell_size[1]);

    let mut eti = ext_ti;
    let mut etj = ext_tj;
    if !inclusive {
        eti[1] -= c.signum() * 1e-9;
        etj[1] -= r.signum() * 1e-9;
    }

    let is = [
        find_nearest_ind(eti[0], oi, c),
        find_nearest_ind(eti[1], oi, c),
    ];
    let js = [
        find_nearest_ind(etj[0], oj, r),
        find_nearest_ind(etj[1], oj, r),
    ];

    let si0 = oi + c * ((is[0] as f64) - 1.0);
    let si1 = oi + c * ((is[1] as f64) - 1.0);
    let sj0 = oj + r * ((js[0] as f64) - 1.0);
    let sj1 = oj + r * ((js[1] as f64) - 1.0);

    [
        [si0 - 0.5 * cell_size[0], si1 + 0.5 * cell_size[0]],
        [sj0 - 0.5 * cell_size[1], sj1 + 0.5 * cell_size[1]],
    ]
}

pub fn merge_extents(exts: &[[[f64; 2]; 2]], sgns: [f64; 2]) -> [[f64; 2]; 2] {
    let mut min_x = f64::INFINITY;
    let mut max_x = f64::NEG_INFINITY;
    let mut min_y = f64::INFINITY;
    let mut max_y = f64::NEG_INFINITY;

    for ext in exts {
        for &v in &ext[0] {
            if v < min_x {
                min_x = v;
            }
            if v > max_x {
                max_x = v;
            }
        }
        for &v in &ext[1] {
            if v < min_y {
                min_y = v;
            }
            if v > max_y {
                max_y = v;
            }
        }
    }

    let ex = if sgns[0] < 0.0 {
        [max_x, min_x]
    } else {
        [min_x, max_x]
    };
    let ey = if sgns[1] < 0.0 {
        [max_y, min_y]
    } else {
        [min_y, max_y]
    };
    [ex, ey]
}

/// Build row-major dense observation matrix `H` of shape `(ns, nt)` matching `unif_weighted_obs_operator_centroid`.
pub fn unif_weighted_obs_operator_centroid(
    sensor: &[[f64; 2]],
    target: &[[f64; 2]],
    sensor_res: [f64; 2],
) -> Vec<f64> {
    let ns = sensor.len();
    let nt = target.len();
    let mut h = vec![0.0f64; ns * nt];

    if sensor == target {
        for i in 0..nt {
            h[i * nt + i] = 1.0;
        }
        return h;
    }

    let hx = sensor_res[0] / 2.0 + 1e-12;
    let hy = sensor_res[1] / 2.0 + 1e-12;

    for i in 0..ns {
        let sx = sensor[i][0];
        let sy = sensor[i][1];
        let mut cnt = 0usize;
        let row_offset = i * nt;
        for j in 0..nt {
            if (sx - target[j][0]).abs() <= hx && (sy - target[j][1]).abs() <= hy {
                h[row_offset + j] = 1.0;
                cnt += 1;
            }
        }
        if cnt > 0 {
            let inv_cnt = 1.0 / (cnt as f64);
            for j in 0..nt {
                h[row_offset + j] *= inv_cnt;
            }
        }
    }
    h
}
