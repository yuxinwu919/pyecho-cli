#!/bin/bash
#SBATCH --time      0-10:01:00
#SBATCH --nodes    1
#SBATCH --partition xfel-sim
#SBATCH --job-name  echo2d-zagor
unset LD_PRELOAD
source /etc/profile.d/modules.sh
module purge
module load mpi/openmpi-x86_64
export OMPI_MCA_btl='^openib,uct,ofi'
export OMPI_MCA_mtl='^ofi'
export OMPI_MCA_pml='ucx'
export OMPI_MCA_opal_warn_on_missing_libcuda=0
echo "job start"
mpirun -np 15 ECHO2D > log.txt
echo "job stop"

