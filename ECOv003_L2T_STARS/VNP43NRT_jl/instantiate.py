import subprocess
from os.path import abspath, dirname

directory = abspath(dirname(__file__))

def main():
        command = f"julia --project={VNP43NRT_jl_directory} -e 'using Pkg; Pkg.instantiate()'"
    subprocess.run(command, shell=True, check=False)
    print(command)
    # system(command)
    subprocess.run(command, shell=True)

if __name__ == "__main":
    main()
