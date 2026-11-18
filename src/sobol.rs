use crate::spatial::{get_ij_from_sij, SobolBounds};

/// 2D Sobol sequence generator matching Julia `Sobol.jl` (`SobolSeq(2)`):
/// - Dimension 1: s=1, a=0, m=[1]
/// - Dimension 2: s=2, a=1, m=[1, 1]
#[derive(Clone, Debug)]
pub struct SobolSeq2D {
    v: [[u32; 32]; 2],
    x: [u32; 2],
    count: u32,
}

impl SobolSeq2D {
    pub fn new() -> Self {
        let mut v = [[0u32; 32]; 2];

        // Dimension 1: m_i = 1 for all i
        for i in 0..32 {
            v[0][i] = 1u32 << (31 - i);
        }

        // Dimension 2: s = 2, a = 1, m = [1, 1]
        // Recurrence: m_i = 2 * a_1 * m_{i-1} XOR 4 * m_{i-2} XOR m_{i-2}
        let mut m = [0u32; 32];
        m[0] = 1;
        m[1] = 1;
        for i in 2..32 {
            m[i] = (m[i - 1] << 1) ^ (m[i - 2] << 2) ^ m[i - 2];
        }
        for i in 0..32 {
            v[1][i] = m[i] << (31 - i);
        }

        let mut seq = Self {
            v,
            x: [0, 0],
            count: 0,
        };
        // Advance once so the first call returns [0.5, 0.5], matching Sobol.next!
        seq.step();
        seq
    }

    #[inline]
    fn step(&mut self) {
        let c = self.count.trailing_ones() as usize;
        if c < 32 {
            self.x[0] ^= self.v[0][c];
            self.x[1] ^= self.v[1][c];
        }
        self.count = self.count.wrapping_add(1);
    }

    #[inline]
    pub fn next_point(&mut self) -> [f64; 2] {
        const SCALE: f64 = 1.0 / 4294967296.0; // 2^-32
        let out = [self.x[0] as f64 * SCALE, self.x[1] as f64 * SCALE];
        self.step();
        out
    }
}

/// Port of Julia `sobol_bau_ij`.
pub fn sobol_bau_ij(
    x_ext: [f64; 2],
    y_ext: [f64; 2],
    origin: [f64; 2],
    cell_size: [f64; 2],
    ndims: [usize; 2],
    nsamp: usize,
) -> Vec<[usize; 2]> {
    let bounds: SobolBounds = get_ij_from_sij(x_ext, y_ext, origin, cell_size, ndims);
    let lb = [bounds.i_min as f64, bounds.j_min as f64];
    let ub = [bounds.i_max as f64, bounds.j_max as f64];
    let span0 = ub[0] - lb[0];
    let span1 = ub[1] - lb[1];

    let mut seq = SobolSeq2D::new();
    let mut result: Vec<[usize; 2]> = Vec::with_capacity(nsamp);

    for _ in 0..nsamp {
        let u = seq.next_point();
        let i = (lb[0] + u[0] * span0).round_ties_even() as isize;
        let j = (lb[1] + u[1] * span1).round_ties_even() as isize;
        let ii = i.clamp(1, ndims[0] as isize) as usize;
        let jj = j.clamp(1, ndims[1] as isize) as usize;
        let pair = [ii, jj];
        if !result.contains(&pair) {
            result.push(pair);
        }
    }

    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sobol_first_points_match_sobol_jl() {
        let mut s = SobolSeq2D::new();
        let expected = [
            [0.5, 0.5],
            [0.75, 0.25],
            [0.25, 0.75],
            [0.375, 0.375],
            [0.875, 0.875],
            [0.625, 0.125],
            [0.125, 0.625],
            [0.1875, 0.3125],
        ];
        for exp in expected {
            let p = s.next_point();
            assert!((p[0] - exp[0]).abs() < 1e-12);
            assert!((p[1] - exp[1]).abs() < 1e-12);
        }
    }
}
