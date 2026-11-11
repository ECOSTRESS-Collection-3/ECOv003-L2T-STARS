# Smoke test for the Julia environment: evaluates every top-level `using`/`import`
# statement from the package's Julia scripts, so missing packages and renamed or
# moved submodules (e.g. DimensionalData.Lookups) fail at build time, not run time.
# Usage: julia --project=<dir> julia_smoke_test.jl [script.jl ...]
# (see julia_environment.py)

const ROOT = @__DIR__

function find_scripts(root)
    scripts = String[]
    for (dir, _, files) in walkdir(root)
        for f in files
            endswith(f, ".jl") && push!(scripts, joinpath(dir, f))
        end
    end
    sort(scripts)
end

function import_statements(path)
    ast = Meta.parseall(read(path, String))
    [ex for ex in ast.args if ex isa Expr && ex.head in (:using, :import)]
end

failures = String[]
# Run in the project the scripts use: julia --project=<dir> julia_smoke_test.jl [script.jl ...]
for script in (isempty(ARGS) ? find_scripts(ROOT) : ARGS)
    for stmt in import_statements(script)
        try
            Core.eval(Main, stmt)
            println("OK    $(basename(script)): $stmt")
        catch err
            msg = "FAIL  $(basename(script)): $stmt -> $(sprint(showerror, err))"
            println(msg)
            push!(failures, msg)
        end
    end
end

if !isempty(failures)
    println("\n$(length(failures)) Julia import failure(s)")
    exit(1)
end
println("\nAll Julia imports succeeded")
