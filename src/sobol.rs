/// 2D Joe & Kuo base-2 Sobol sequence matching `Sobol.jl`'s `SobolSeq([lb0, lb1], [ub0, ub1])`.
pub struct SobolSeq2D {
    lb: [f64; 2],
    scale: [f64; 2],
    count: u32,
    x: [u32; 2],
    v: [[u32; 32]; 2],
}

impl SobolSeq2D {
    pub fn new(lb: [f64; 2], ub: [f64; 2]) -> Self {
        let mut v = [[0u32; 32]; 2];
        // Dimension 1: primitive polynomial x + 1 (degree 1), m_1 = 1
        for i in 0..32 {
            v[0][i] = 1u32 << (31 - i);
        }
        // Dimension 2: primitive polynomial x^2 + x + 1 (degree 2, a = 1), m = [1, 3]
        let mut m = [0u32; 32];
        m[0] = 1;
        m[1] = 3;
        for i in 2..32 {
            m[i] = m[i - 2] ^ (m[i - 2] << 2) ^ (m[i - 1] << 1);
        }
        for i in 0..32 {
            v[1][i] = m[i] << (31 - i);
        }

        // Sobol.jl advances one step on initialization so the first `next!` returns the midpoint
        let mut seq = Self {
            lb,
            scale: [
                (ub[0] - lb[0]) / (u32::MAX as f64 + 1.0),
                (ub[1] - lb[1]) / (u32::MAX as f64 + 1.0),
            ],
            count: 0,
            x: [0, 0],
            v,
        };
        seq.step();
        seq
    }

    #[inline]
    fn step(&mut self) {
        let c = self.count.trailing_ones() as usize;
        let idx = c.min(31);
        self.x[0] ^= self.v[0][idx];
        self.x[1] ^= self.v[1][idx];
        self.count = self.count.wrapping_add(1);
    }

    #[inline]
    pub fn next_point(&mut self) -> [f64; 2] {
        let out = [
            self.lb[0] + (self.x[0] as f64) * self.scale[0],
            self.lb[1] + (self.x[1] as f64) * self.scale[1],
        ];
        self.step();
        out
    }
}

/// Generate unique 1-based `(i, j)` BAU indices inside `[ext_ti, ext_tj]` matching `sobol_bau_ij`.
pub fn sobol_bau_ij(
    ext_ti: [f64; 2],
    ext_tj: [f64; 2],
    origin: [f64; 2],
    cell_size: [f64; 2],
    n_dims: [usize; 2],
    nsamp: usize,
    inclusive: bool,
) -> Vec<[usize; 2]> {
    let (oi, oj) = (origin[0], origin[1]);
    let (c, r) = (cell_size[0], cell_size[1]);

    let mut eti = ext_ti;
    let mut etj = ext_tj;
    if !inclusive {
        eti[1] -= c.signum() * 1e-9;
        etj[1] -= r.signum() * 1e-9;
    }

    let mut is = [
        ((eti[0] - oi) / c + 1.0).round() as isize,
        ((eti[1] - oi) / c + 1.0).round() as isize,
    ];
    let mut js = [
        ((etj[0] - oj) / r + 1.0).round() as isize,
        ((etj[1] - oj) / r + 1.0).round() as isize,
    ];

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

        let ni = (is[1] - is[0] + 1) as usize;
        let nj = (js[1] - js[0] + 1) as usize;

        let mut out = Vec::new();
        if nsamp >= ni * nj {
            out.reserve(ni * nj);
            for i in is[0]..=is[1] {
                for j in js[0]..=js[1] {
                    out.push([i as usize, j as usize]);
                }
            }
        } else {
            let mut seq = SobolSeq2D::new(
                [is[0] as f64, js[0] as f64],
                [is[1] as f64, js[1] as f64],
            );
            out.reserve(nsamp);
            for _ in 0..nsamp {
                let p = seq.next_point();
                let pair = [p[0].round() as usize, p[1].round() as usize];
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sobol_first_points_match_sobol_jl() {
        let mut seq = SobolSeq2D::new([0.0, 0.0], [1.0, 1.0]);
        let p1 = seq.next_point();
        let p2 = seq.next_point();
        let p3 = seq.next_point();
        assert!((p1[0] - 0.5).abs() < 1e-12 && (p1[1] - 0.5).abs() < 1e-12);
        assert!((p2[0] - 0.75).abs() < 1e-12 && (p2[1] - 0.25).abs() < 1e-12);
        assert!((p3[0] - 0.25).abs() < 1e-12 && (p3[1] - 0.75).abs() < 1e-12);
    }
}
