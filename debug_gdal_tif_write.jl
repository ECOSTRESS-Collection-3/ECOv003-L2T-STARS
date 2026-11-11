using Rasters
using STARSDataFusion.sentinel_tiles

x, y = sentinel_tile_dims("11SPS", 70)
data = fill(0.12, length(x), length(y), 1)
raster = Raster(data, dims=(x, y, Band(1:1)), missingval=NaN)

mktempdir() do dir
    output = joinpath(dir, "STARS_NDVI_2026-10-10_11SPS_70m.tif")
    @info "Writing test GeoTIFF" output
    write(output, raster, force=true)
    @info "GeoTIFF write succeeded"
end
