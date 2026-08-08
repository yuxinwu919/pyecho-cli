#!/bin/bash
#SBATCH --time      0-10:01:00
#SBATCH --nodes    2
#SBATCH --partition xfel-sim
#SBATCH --job-name  echo2d-zagor
export LD_PRELOAD=""
source /etc/profile.d/modules.sh
module load mpi/openmpi-x86_64
echo "job start"
mpirun -np 40 --mca pml ucx ECHO2D
echo "job stop"

