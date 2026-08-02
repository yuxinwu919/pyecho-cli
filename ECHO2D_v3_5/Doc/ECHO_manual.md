Electromagnetic code ECHO 

![](images/7692bc2fdcf0b969afb8bbae76f180a1181af78aab80577e5ef370cf290b9f48.jpg)


![](images/baf0cf4fcb23d7be94e9762b9e7d261b20a27e95031e80ee261b654b9ed306d9.jpg)


Copyright c 2005-2020 Igor Zagorodnov 

PUBLISHED BY IGOR ZAGORODNOV 

WWW.ECHO4D.DE 

The program package ECHO can be downloaded free of charge for non-commercial and nonmilitary use. Dissemination to third parties is illegal. The author reserves copyrights and all rights for commercial use for the program package ECHO, parts of the program package and of procedures developed for the program package. The author undertakes no obligation for the maintenance of the program, nor responsibility for its correctness, and accepts no liability whatsoever resulting from its use. 

Printing, 1 April 2020 

## Contents

1 Introduction 7  
2 ECHOz1: Full Rotational Symmetry 9  
2.1 Introduction 9  
2.2 Installation 10  
2.3 Input files 10  
2.3.1 Geometry description 10  
2.3.2 Parameters of simulation 11  
2.4 Wakefield Calculation 11  
2.5 Output files 12  
2.6 Postprocessing 12  
2.7 Examples 12  
2.7.1 Example 1: Round collimator 12  
2.7.2 Example 2: TESLA cavity 14  
3 ECHOz2: Rotationally Symmetric Geometry 15  
3.1 Introduction 15  
3.2 Installation 16  
3.3 Input files 16  
3.3.1 Geometry description 16  
3.3.2 Parameters of simulation 17  
3.4 Wakefield Calculation 17  
3.5 Output files 18  
3.6 Postprocessing 18 

3.7 Examples 18  
3.7.1 Example 1: Round collimator 19  
3.7.2 Example 2: Resistive pillbox cavity 21  
3.7.3 Example 3: TESLA cavity 21  
4 ECHO2D: Rectangular and Round Geometries 23  
4.1 Introduction 23  
4.2 Installation 26  
4.3 Input files 26  
4.3.1 Geometry description 27  
4.3.2 Parameters of simulation 27  
4.3.3 Beam setup 30  
4.3.4 Initial field setup 30  
4.3.5 Waveguide port setup 30  
4.3.6 Field monitors setups 30  
4.4 Wakefield Calculation 31  
4.5 Output files 31  
4.6 Postprocessing 33  
4.6.1 Wakes 33  
4.7 Examples 34  
4.7.1 Example 1: Round collimator 34  
4.7.2 Example 2: Resistive pillbox cavity 34  
4.7.3 Example 3: TESLA cavity 34  
4.7.4 Example 4: Flat absorber 35  
4.7.5 Example 5: Pohang Dechirper 36  
4.7.6 Example 7: Flat tapered collimator with resistivity 37  
4.7.7 Example 8: Field monitor for flat taper 38  
4.7.8 Example 9: Round dielectric pipe 38  
4.7.9 Example 10: Flat dielectric pipe 39  
4.7.10 Example 11: TESLA cavity with restart procedure, wake monitors and arbitrary bunch shape 39  
4.7.11 Example 12: Particle tracking in dielectric pipe 40  
5 ECHO3D: Three Dimensional Geometry 45  
5.1 Introduction 45  
5.2 Installation and work-flow 46  
5.3 Input files 46  
5.3.1 Geometry description 46  
5.3.2 Parameters of simulation 48  
5.4 Wakefield Calculation 49  
5.5 Output files 50  
5.6 Postprocessing 50  
5.7 Examples 50 

6 ECHO1D: Anisotropic Waveguides 51
6.1 Introduction 51
6.2 Installation 54
6.3 Input files 54
6.3.1 Geometry description 54
6.3.2 Parameters of simulation 55
6.4 Impedance Calculation 56
6.5 Output files 56
6.6 Postprocessing 57
6.6.1 Impedances 57
6.6.2 Wakes 58
6.7 Examples 58
6.7.1 Example 1: Round dielectric pipe 58
6.7.2 Example 2: Flat dielectric pipe 60
6.7.3 Example 3: Flat anisotropic pipe 61
6.7.4 Example 4: Round pipe with two layers 61
Bibliography 67
Books 67
Articles 67
Index 69 

## 1. Introduction

Program ECHO calculates electromagnetic fields of charged bunches in accelerators. 

The package consists of three archives: 

• ECHO1D.zip 

• ECHO2D.zip 

• ECHO3D.zip 

Archive ECHO1D.zip contains program ECHO1D which calculates impedances and wakes of rotationally symmetric and rectangular waveguides. 

Archive ECHO2D.zip includes three different programs: ECHOz1, ECHOz2 and ECHO2D for rotationally symmetric and rectangular geometries. 

Archive ECHO3D.zip contains program ECHO3D for arbitrary three dimensional structures. 

![](images/9df46f363b786deeefc1d24d82b74e4e116d386bbb71577328141db0f016f479.jpg)


R Under rectangular geometries we mean structures having rectangular cross-section, where the height can vary as function of longitudinal coordinate but the width and side walls remain fixed. 

In order to start I would advice to use code ECHOz1 or code ECHOz2 as they have GUI and only few simulation parameters. 

The codes use conformal finite-difference method. In the time-domain wake filed calculations the mesh resolution with 5 mesh points on the rms bunch width should be enough to obtain accurate results. To check the accuracy I would advice to do 2 tests: 

• for the coarsest mesh resolution to change bunch offset (with indirect integration algorithm switched on); 

• double the mesh resolution. 

If the first test fails it means that there is a meshing error. In this case change a little the mesh steps to try to avoid it and contact me for fixing a possible bug in the code. If the first test is OK then check the convergence and the accuracy with the second test. 

ECHOz2 and ECHO2D include a model of conductive walls. The meshes in the vacuum and in the metal should agree as follows. As a default mesh use 5 mesh lines on sigma in vacuum and “NStepsInConductive=10” in metal. It means that the skin depth in the metal will be meshed with 10 mesh lines. If you increase the mesh density in vacuum by factor 2 (10 mesh lines on sigma) you should simultaneously increase by the same factor “NStepsInConductive” in metal: “NStepsInConductive=20”. It means that the calculation depth in the metal remains the same. For 20 mesh lines on sigma use”NStepsInConductive=40” and so on. In this case the calculation domain remains the same and the wake converges. 

## 2. ECHOz1: Full Rotational Symmetry

## 2.1 Introduction

Code ECHOz1 calculates in time domain the electromagnetic fields generated by an electron bunch passing through rotationally symmetric perfectly conducting structure on axis of symmetry [8]. 

![](images/8ab0d3e70b8c9a9b045c565968ef6449481fba6f9c8fb5470aae23d7219fd1f7.jpg)



Figure 2.1: The beam moves on axis in rotationally symmetric stricture.


We consider a charged bunch moving with light velocity c through a rotationally symmetric structure as shown in Fig. 2.1. The bunch has Gaussian longitudinal charge density $\lambda ( s )$ with rms length $\sigma _ { z } .$ . It moves on the symmetry axis and the whole problem is rotationally symmetric. 

The charge density in time domain can be written as 

$$
\rho (r, \varphi , z, t) = Q \frac {\delta (r - r _ {0})}{2 \pi r _ {0}} \lambda (z - c t), \quad \lambda (s) = \frac {1}{\sqrt {2 \pi} \sigma_ {z}} e ^ {\frac {s ^ {2}}{2 \sigma_ {z} ^ {2}}},\tag{2.1}
$$

where $Q$ is the bunch charge, $r _ { 0 }$ is the "hollow" bunch radius, c is velocity of light in vacuum, and $\delta ( \cdot )$ means the Dirac delta function. 

We are interested in longitudinal wake potential as defined in [1]. For fully rotationally symetric problem it can be written as 

$$
W _ {\parallel} (r _ {0}, r, \varphi , s) = W _ {0} (s),\tag{2.2}
$$

where s is the position of the wittness particle in the bunch. 

## 2.2 Installation

The program ECHOz1 is compiled for Windows. It can be downloaded as archive ECHO2D.zip from https://www.echo4d.de. Extract the archive keeping the stricture of folders and files. 

The archive contains the following folders. 

1. Docs. It contains this manual. 

2. Codes. It contains the executable ECHOz1.exe. 

3. Examples. It contains several examples. 

4. MatLib4ECHO. It contains Matlab functions for postprocessing. 

5. PostProcessor2D. It contains Matlab scripts for postprocessing. 

6. System. It contains two files which are required for parallel execution. If ECHOz1 do not start or start with error, install vc_redist.x64.exe on your computer. It puts file vcomp140.dll in Windows system directory. Alternatively you can put only the file vcomp140.dll to the directory ECHOz1. 

## 2.3 Input files

The program ECHOz1 does not require any input files. A geometry and a setup can be done in the program itself and saved in a binary file with extension "*.e2d". 

Alternatively two files can be used as input: 

• a file with geometry description in ASCII format; it can have an arbitrary name and it will be imported in the programm through GUI menu, 

• a file with parameters of the simulation and the geometry in binary format with extension "*.e2d" created early with ECHOz1. 

## 2.3.1 Geometry description

The geometry can be imported as a file in ASCII format with extension "*.txt". 

The geometry file has the following format. 

N 

$z_{1,1} r_{1,1} z_{2,1} r_{2,1} z_{3,1} r_{3,1} z_{4,1} r_{4,1} d_{1}$ 

$z_{1,N} r_{1,N} z_{2,N} r_{2,N} z_{3,N} r_{3,N} z_{4,N} r_{4,N} d_{N}$ 

The parameters in the geometry file are: 

• N - total number of segments (lines or elliptical arcs). 

• z , r - coordinates in cm of start point for segment number i. 

• z <sub>,</sub> , r <sub>,</sub> - coordinates in cm of end point for segment number i. 

• z<sub>3,i</sub>, r<sub>3,i</sub>, z<sub>4,i</sub>, r<sub>4,i</sub> - - coordinates in cm of square in which the ellipse is inscribed (for lines these parameters should be zeros). 

• z , r - coordinates in cm of top left corner. 

• z , r - coordinates in cm of bottom right corner. 

• d - orientation (0-clock, 1-anticlock). 

As example let us consider the geometry shown in Fig. 2.2. The corresponding file will have the following content 

3 

```txt
z0 r1 z1 r1 0 0 0 0 0 
```

$$
\mathrm{z1r1z2r2z3r3z4r40}
$$

$$
\mathrm{z2r2z5r200000.}
$$

In oder to export the geometry in ECHOz1 go to GUI menu "Geometry/Import". Alternatively it is possible to create a geometry in ECHOz1 GUI. Use for it menu "Geometry/Edit" and the button "Add" in the dialog box. The format is the same as described above. After the geometry creation save it with help of menu "File/Save As" in file with extension "*.e2d". 

![](images/f08c294725b0d9278d5fcdf8b11d8e579248a2dbd835e4926a0ee31328d7f777.jpg)



Figure 2.2: Example for geometry file format.


## 2.3.2 Parameters of simulation

The parameters of simulation can be set only through the GUI. The setup of the simulation can be done only after the geometry description is created or imported in the program. 

In order to set the Gaussian bunch length σ go to menu "Bunch" and set the value in cm in the box "Sigma". It is only the parameter in the dialog "Bunch". 

The mesh can be set through menu "Mesh". In order to use 5 mesh points on sigma press the button "Default". If you are going to use different mesh steps then put the new values in the boxes "Z step" and "R step" in cm and press the button "Apply". 

After the setup of parameters is finished save them in "*.e2d" file: go to menu "File/Save" or use the "Save" symbol in the tool-bar. 

## 2.4 Wakefield Calculation

After creation of the mesh, setup of the bunch length and setup of the mesh steps you can go to menu "Solver". It opens the dialog box shown in Fig. 2.3. 

![](images/cd111d5bf320c445f6a3a5d4d64aeeb8e159eb8f7a9b65e84cbf7d95c0754777.jpg)



Figure 2.3: Parameters of solver.



The parameters in the dialog are:


• Mesh length - length og the calculation window moving with the bunch. It is given as number of steps. The length of window in cm can be found by multiplication of this number with value of "Step Z" from "Mesh" dialog. 

• Timer - this parameter defines the time interval of update of the field picture on the display during the calculation. The program shows the scaterred field potential $r A _ { \varphi } .$ 

• Offset - defines value of $r _ { 0 }$ in mesh lines. It can be found as $r _ { 0 } = ( " \mathrm { O f f s e t " } + 0 . 5 ) " \mathrm { ^ { * } \mathrm { ^ { * } S t e p } } \mathrm { R " }$ The value "-1" mens that we use $r _ { 0 }$ as large as possible. The last choice provides the best accuracy. 

• Convex geometry - check ON this check-box to accelerate the calculation for "convex" geometry. "Convex" means here a geometry that has only one connected vacuum region in each plane transverse to the symmetry axis. 

• Syncronization - check OFF this check-box to accelerate the calculation if you are not interested in synchronization of field map with the geometry. It has impact only on the display picture during the calculation. 

• Integration Method - use "Indirect" choice if you do not really know what "Direct" means. 

• Conformal - use this choice together with "Simple" check-box. Other choices can be used only if you have problems with this one. 

• Parallel threads - set up how many threads will be used. Usually it should be equal to the number of cores in your computer, but check the efficiency of parallelism experimentally. 

Press "OK" button to start the calculation. After the box "Ready!" finish the calculation with menu "Stop". Press the green button "W" to see the wake and the loss factor. After the calculation is finished or interrupted with menu "Stop", save the parameters in "*.e2d" file with menu command "File/Save". It will save the parameters of the solver as well. 

## 2.5 Output files

After execution of ECHOz1.exe the folder will contain two files: 

• wake.dat - with longitudinal wake. It has two columns. In the first column is s-coordinate in cm, in the second column is function W(s) in V/pC. 

• bunch.dat - with bunch charge profile. It has two columns. In the first column is s-coordinate in cm, in the second column is current profile in arbitrary units. 

## 2.6 Postprocessing

Use matlab script PP_ECHOz1 from directory PostProcessor2D/ Wakes/ Round. It plots the wake and calculates the loss factor and the rms spread of the wake. 

## 2.7 Examples

In this section we consider several examples included in the archive at the directory Examples. 

## 2.7.1 Example 1: Round collimator

The example of round collimator can be found in directory Examples/ N1_RoundCollimatorLong. 

In order to make the simulation proceed as follows: 

• Go to directory Codes and start ECHOz1.exe. 

• Go to menu "File/Open" and navigate to directory Examples/ N1_RoundCollimatorLong/ ECHOz1. Open the input file N1.e2d. You should see the geometry shown in Fig. 2.4. 

• Go to menu "Bunch" and press "OK". 

• Go to menu "Mesh" and press "Close". 

![](images/39240b94750d6b63710bf25fcedc9f4a9f2d4539eb611bd41adaa18dc0db4bf2.jpg)



Figure 2.4: Geometry of round collimator.


• Go to menu "Sover" and press "OK". The calculation starts. 

• Wait until message "Ready" appears and press "OK". The calculations is done. 

• Go to menu "Stop". 

• Press button with green "W" in the panel under main menu. You will see the wake and the loss factor. 

• Press button with yellow "G" to return to the geometry. 

• Close the program. 

![](images/9e8c725dfddb8bbdd69f2282ac40984938b075c83d25fa4688ef6ed4928b223f.jpg)



Figure 2.5: Longitudinal wake of round collimator (in green).


Now the wake is saved in file wake.dat in directory Examples/ N1_RoundCollimatorLong/ ECHOz1. You can use the matlab script PostProcessor2D/ Round/ PP_ECHOz1.m to see the wake shown in Fig. 2.5. 

## 2.7.2 Example 2: TESLA cavity

The example of TESLA cavity can be found in directory Examples/ N10_TESLACavityLong. 

![](images/c4b61b8e1c338f5592ba9f30b40a54aa9005b7c4e3d455fa679d1e8186e413e4.jpg)



Figure 2.6: Geometry of TESLA cavity.


In order to make the simulation proceed as follows: 

• Go to directory Codes and start ECHOz1.exe. 

• Go to menu "File/Open" and navigate to directory Examples/ N10_TESLACavityLong/ECHOz1. Open the input file N10.e2d. You should see the geometry shown in Fig. 2.6. 

• Go to menu "Bunch" and press "OK". 

• Go to menu "Mesh" and press "Close". 

• Go to menu "Sover" and press "OK". The calculation starts. 

• Wait until message "Ready" appears and press "OK". The calculations is done. 

• Go to menu "Stop". 

• Press button with green "W" in the panel under main menu. You will see the wake and the loss factor. 

• Press button with yellow "G" to return to the geometry. 

• Close the program. 

![](images/3d6953635df63fbf15a9dcbb4bf17a6b86d77e87943a5e98780514358437f6d1.jpg)



Figure 2.7: Longitudinal wake of TESLA cavity (in green).


Now the wake is saved in file wake.dat in directory /Examples/ N10_TESLACavityLong/ ECHOz1. You can use the matlab script PostProcessor2D/ Round/ PP_ECHOz1.m to see the wake shown in Fig. 2.5. 

## 3. ECHOz2: Rotationally Symmetric Geometry

## 3.1 Introduction

Code ECHOz2 calculates in time domain the electromagnetic fields generated by an electron bunch passing through rotationally symmetric conducting structure off axis [6, 9]. The structure can have only metal conductive walls with finite or infinite conductivity. 

![](images/4e8a7c06b1fab63274741402f41a73bfab87a8db4502bef2dd8a2595ff983e19.jpg)



Figure 3.1: The beam moves off axis in rotationally symmetric stricture.


We consider a charged bunch moving with light velocity c through a rotationally symmetric structure as shown in Fig. 3.1. The bunch has Gaussian longitudinal charge density $\lambda ( s )$ with rms width σ. It moves off axis and the whole problem is not rotationally symmetric but can be expanded in infinite number of independent problems for Fourier azimuthal harmonics. 

The charge density in time domain can be written as 

$$
\rho (r _ {0}, \varphi_ {0}, r, \varphi , z, t) = \sum_ {m = 0} ^ {\infty} \rho_ {m} (r _ {0}, r, z, t) \cos (m (\varphi - \varphi_ {0})),\tag{3.1}
$$

$$
\rho_ {m} (r _ {0}, r, z, t) = Q \frac {\delta (r - r _ {0})}{\pi r _ {0} (1 + \delta_ {m 0})} \lambda (z - c t), \quad \lambda (s) = \frac {1}{\sqrt {2 \pi} \sigma} e ^ {\frac {s ^ {2}}{2 \sigma^ {2}}},\tag{3.2}
$$

where Q is the bunch charge, $r _ { 0 } , \varphi _ { 0 }$ is the "pincel" bunch offset coordinates, c is velocity of light in vacuum, and $\delta ( \cdot )$ means the Dirac delta function, and $\delta _ { m 0 } = 1 \mathrm { i f } m = 1 , 0$ otherwise. 

The longitudinal wake potential can be represented through one dimensional functions, with only one function for each azimuthal mode number $m ,$ 

$$
W _ {\parallel} (r _ {0}, \varphi_ {0}, r, \varphi , s) = \sum_ {m = 0} ^ {\infty} W _ {m} (s) r _ {0} ^ {m} r ^ {m} \cos (m (\varphi - \varphi_ {0})).\tag{3.3}
$$

## 3.2 Installation

The program ECHOz2 is compiled for Windows. It can be downloaded as archive ECHO2D.zip from https://www.echo4d.de. Extract the archive keeping the stricture of folders and files. 

The archive contains the following folders. 

1. Docs. It contains this manual. 

2. Codes. It contains the executable ECHOz2.exe. 

3. Examples. It contains several examples. 

4. MatLib4ECHO. It contains Matlab functions for postprocessing. 

5. PostProcessor2D. It contains Matlab scripts for postprocessing. 

6. System. It contains two files which are required for parallel execution. If ECHOz2 do not start or start with error, install vc_redist.x64.exe on your computer. It puts file vcomp140.dll in Windows system directory. Alternatively you can put only the file vcomp140.dll to the directory ECHOz2. 

## 3.3 Input files

The program ECHOz2 does not require any input files. A geometry and a setup can be done in the program itself and saved in a binary file with extension "*.e2dx". 

Alternatively two files can be used as input: 

• a file with geometry description in ASCII format; it can have an arbitrary name and it will be imported in the programm through GUI menu, 

• a file with parameters of the simulation and the geometry in binary format with extension "*.e2dx" created early with ECHOz2. 

## 3.3.1 Geometry description

The geometry can be imported as a file in ASCII format with extension "*.txt". 

The geometry file has the following format. 

N 

$$
z _ {1, 1} r _ {1, 1} z _ {2, 1} r _ {2, 1} z _ {3, 1} r _ {3, 1} z _ {4, 1} r _ {4, 1} d _ {1} k _ {1}
$$

$$
z _ {1, N} r _ {1, N} z _ {2, N} r _ {2, N} z _ {3, N} r _ {3, N} z _ {4, N} r _ {4, N} d _ {N} k _ {N}
$$

The parameters in the geometry file are: 

• $N \cdot$ total number of segments (lines or elliptical arcs). 

$z _ { 1 , i } , r _ { 1 , i } -$ coordinates in cm of start point for segment number $i .$ 

$z _ { 2 , i } , r _ { 2 , i } - \mathrm { c o o r d i n a }$ tes in cm of end point for segment number i. 

$z _ { 3 , i } , r _ { 3 , i } , z _ { 4 , i } , r _ { 4 , i } -$ coordinates in cm of square in which the ellipse is inscribed (for lines these parameters should be zeros). 

$z _ { 3 , i } , r _ { 3 , i } -$ coordinates in cm of top left corner. 

$z _ { 4 , i } , r _ { 4 , i } -$ coordinates in cm of bottom right corner. 

$d _ { i } \cdot -$ orientation (0-clock, 1-anticlock). 

$k _ { i } \cdot$ conductivity in S/m. 

As example let us consider the geometry shown in Fig. 2.2. The corresponding file will have the following content 

```txt
3
z0 r1 z1 r1 0 0 0 0 0 k1
z1 r1 z2 r2 z3 r3 z4 r4 0 k2
z2 r2 z5 r2 0 0 0 0 0 k3, 
```

where k1, k2, k3 are conductivities of the segments. 

In oder to export the geometry in ECHOz2 go to GUI menu "Geometry/Import". Alternatively it is possible to create a geometry in ECHOz2 GUI. Use for it menu "Geometry/Edit" and the button "Add" in the dialog box. The format is the same as described above. After the geometry creation save it with help of menu "File//Save As" in file with extension "*.e2dx". 

## 3.3.2 Parameters of simulation

The parameters of simulation can be set only through the GUI. The setup of the simulation can be done only after the geometry description is created or imported in the program. 

In order to set the Gaussian bunch length go to menu "Bunch" and set the value in cm in the box "Sigma". It is only the parameter in the dialog "Bunch". 

The mesh can be set through menu "Mesh". In order to use 5 mesh points on sigma press the button "Default". If you are going to use different mesh steps then put then in the boxes "Z step" and "R step" in cm and press the button "Apply". 

The mesh dialog has box "Lossy metal 1D mesh length". It should be set to "0" if the structure is perfectly electric conductive. Otherwise it defines an one dimensional mesh length for tangential components of electromagnetic field in the conductive parts [6]. The default value is 10. Increase this value to obtain a better accuracy. 

After the setup of parameters save them in "*.e2dx" file. For it go to menu "File/Save" or use the "Save" symbol in the panel under menu. 

## 3.4 Wakefield Calculation

After creation of the mesh, setup of the bunch length and setup of the mesh steps you can go to menu "Solver". It opens the dialog box shown in Fig. 3.2. 

The parameters in the dialog are: 

• Mode # - mode number m in the azimuthal expansion. 

• Mesh length - length og the calculation window moving with the bunch. It is given as number of steps. The length of window in cm can be found by multiplication of this number with value of "Step Z" from "Mesh" dialog. 

• Update on the screen - this parameter defines the time interval of update of the field picture on the display during the calculation. The program shows the electric field component E . 

• Bunch offset - defines value of r in mesh lines. It can be found as $r _ { 0 } = ( \mathrm { " O f f s e t " } { + } 0 . 5 ) \mathrm { * " S }$ tep R". The value "-1" mens that we use r as large as possible. The last choice provides the best accuracy. 

• Convex geometry - check ON this check-box to accelerate the calculation for "convex" geometry. "Convex" means here a geometry that has only one connected vacuum region in each plane transverse to the symmetry axis. 

• Syncronization - check OFF this check-box to accelerate the calculation if you are not interested in synchronization of field map with the geometry. It has impact only on the display picture during the calculation. 

• Integration Method - use "Indirect" choice if you do not really know what "Direct" means. 

![](images/3677830b8779de8a04958b6b090e1ca776e61cb7a652122e1a096c5825089c09.jpg)



Figure 3.2: Parameters of solver ECHOz2.


• PEC factor - it defines which cells near the boundary will be treated with extended stencil [7]. The value shoul be between 0.5 and 1.0. The lower value gives a better accuracy, the higher value provides a better stability. 

• Parallel threads - set up how many threads will be used. Usually it should be equal to the number of cores in your computer, but check the efficiency of parallelism experimentally. 

Press "OK" button to start the calculation. After the box "Ready!" finish the calculation with menu "Stop". Press the green button "L" to see the longitudinal wake and the loss factor. Press the green button "T" to see the transverse wake and the kick factor. After the calculation is finished or interrupted with menu "Stop", save the parameters in "*.e2d" file with menu command "File/Save". It will save the parameters of the solver as well. 

## 3.5 Output files

After execution of ECHOz2.exe the folder will contain three files: 

• wakeL.dat - with longitudinal wake for mode m. It has two columns. In the first column is s-coordinate in cm, in the second column is function $W _ { m } ( s )$ in $\mathrm { V } / \mathrm { p C } / \mathrm { m } ^ { 2 m }$ 

• wakeT.dat - with transverse wake for mode m. It has two columns. In the first column is s-coordinate in cm, in the second column is function $\begin{array} { r l } { \int _ { - \infty } ^ { s } W _ { m } ( s ) d s \mathrm { i n } \mathrm { V } / \mathrm { p C } / \mathrm { m } ^ { 2 m - 1 } } \end{array}$ 

• bunch.dat - with bunch charge profile. It has two columns. In the first column is s-coordinate in cm, in the second column is current profile in arbitrary units. 

## 3.6 Postprocessing

Use matlab script PP_ECHOz2 from directory PostProcessor2D/ Wakes/ Round. It plots the wake and calculates the loss factor and the rms spread of the wake. 

## 3.7 Examples

In this section we consider several examples included in the archive at the directory Examples. 

## 3.7.1 Example 1: Round collimator

The examples of round collimator can be found in directories Examples/ N1_RoundCollimatorLong, Examples/ N2_RoundCollimatorDipole, Examples/ N3_RoundCollimatorDipoleConductive. 

![](images/7058793196e40144dba35eb03275463bae586af145543ec3584fa50750310257.jpg)



Trans. wake, Kick=92.7396V/pC/m1, Spread=53.6677V/pC/m1


![](images/b857ca5fc8de9f5a13b9c576106d1b6f85f3221588d1ff999e16ed6a91df13ef.jpg)



Figure 3.3: Longitudinal and transverse wakes of round collimator (dipole mode).


In order to calculate the longitudinal wake of monopole mode (m = 0) proceed as follows: 

• Go to directory Codes and start ECHOz2.exe. 

• Go to menu "File/Open" and navigate to directory Examples/ N1_RoundCollimatorLong/ ECHOz2. Open the input file N1.e2dx. You should see the geometry shown in Fig. 2.4. 

• Go to menu "Bunch" and press "OK". 

• Go to menu "Mesh" and press "Close". 

• Go to menu "Sover" and press "OK". The calculation starts. 

• Wait until message "Ready" appears and press "OK". The calculations is done. 

• Go to menu "Stop". 

• Press button with green "L" in the panel under main menu. You will see the wake and the loss factor. 

• Press button with yellow "G" to return to the geometry. 

• Close the program. 

Now the wake is saved in file wakeL.dat in directory Examples/ N1_RoundCollimatorLong/ ECHOz2. You can use the matlab script PostProcessor2D/ Round/ PP_ECHOz2.m to see the wake shown in Fig. 2.5. The transverse wake is zero for the monopole mode. 

In order to calculate the transverse wake of dipole mode (m = 1) proceed as follows: 

• Go to directory Codes and start ECHOz2.exe. 

• Go to menu "File/Open" and navigate to directory Examples/ N2_RoundCollimatorDipole/ ECHOz2. Open the input file N2.e2dx. You should see the geometry shown in Fig. 2.4. 

• Go to menu "Bunch" and press "OK". 

• Go to menu "Mesh" and press "Close". 

• Go to menu "Sover" and press "OK". The calculation starts. 

![](images/2644e30353722027c5ee00ef61fcecb0aec8e5e2864143f870b4ae9030bd6de6.jpg)



Trans. wake, Kick=118.1849V/pC/m1, Spread=73.2448V/pC/m1


![](images/63636adbbaecac2d67f853eff84c95296cfd500c7f40d4caa6b00af1566616a2.jpg)



Figure 3.4: Longitudinal and transverse wakes of round conductive collimator (dipole mode).


• Wait until message "Ready" appears and press "OK". The calculations is done. 

• Go to menu "Stop". 

• Press button with green "T" in the panel under main menu. You will see the transverse wake and the kick factor 

• Press button with yellow "G" to return to the geometry. 

• Close the program. 

Now the wake is saved in file wakeT.dat in directory /Examples/ N2_RoundCollimatorDipole/ ECHOz2. You can use the matlab script PostProcessor2D/ Round/ PP_ECHOz2.m to see the wake shown in Fig. 3.3. 

The last example is the same collimator but with conductive small pipe. The conductovity is equat ti 1 S/m. It can be seen and changed through menu "Geometry/Edit". In order to calculate the transverse wake of dipole mode (m = 1) for the conductive collimator proceed as follows: 

• Go to directory Codes and start ECHOz2.exe. 

• Go to menu "File/Open" and navigate to directory Examples/ N3_RoundCollimatorDipoleConductive/ ECHOz2. Open the input file N3.e2dx. You should see the geometry shown in Fig. 2.4. 

• Go to menu "Bunch" and press "OK". 

• Go to menu "Mesh" and press "Close". 

• Go to menu "Sover" and press "OK". The calculation starts. 

• Wait until message "Ready" appears and press "OK". The calculations is done. 

• Go to menu "Stop". 

• Press button with green "T" in the panel under main menu. You will see the transverse wake and the kick factor. 

• Press button with yellow "G" to return to the geometry. 

• Close the program. 

Now the wake is saved in file wakeT.dat in directory Examples/ N3_RoundCollimatorDipoleConductive/ ECHOz2. You can use the matlab script PostProcessor2D/ Round/ PP_ECHOz2.m to see the wake shown in Fig. 3.4. 

## 3.7.2 Example 2: Resistive pillbox cavity

The example of pillbox cavity can be found in directory Examples/N9_ResistivePillbox. The cavity walls have conductivity equal to 1000 S/m. 

![](images/ae9246cb2a1e5e218a9732934c9bf8f5db2ab612b00af3c1a3af8c899a90e7ed.jpg)



Figure 3.5: Pillbox cavity geometry.


In order to calculate the transverse wake of dipole mode (m = 1) proceed as follows: 

• Go to directory Codes and start ECHOz2.exe. 

• Go to menu "File/Open" and navigate to directory Examples/ N9_ResistivePillbox/ ECHOz2. Open the input file N9.e2dx. You should see the geometry shown in Fig. 3.5. 

• Go to menu "Bunch" and press "OK". 

• Go to menu "Mesh" and press "Close". 

• Go to menu "Sover" and press "OK". The calculation starts. 

• Wait until message "Ready" appears and press "OK". The calculations is done. 

• Go to menu "Stop". 

• Press button with green "L" in the panel under main menu. You will see the wake and the loss factor. 

• Press button with yellow "G" to return to the geometry. 

• Close the program. 

Now the wake is saved in file wakeL.dat in directory Examples/ N9_ResistivePillbox/ ECHOz2. You can use the matlab script PostProcessor2D/ Round/ PP_ECHOz2.m to see the wake shown in Fig. 3.6. The transverse wake is zero for the monopole mode. 

In order to calculate the monopole or the higher order modes change only "Mode #" value in solver box in the route described above. 

## 3.7.3 Example 3: TESLA cavity

The example of TESLA cavity can be found in directory Examples/ N10_TESLACavityLong. In order to make the simulation proceed as follows: 

• Go to directory Codes and start ECHOz2.exe. 

• Go to menu "File/Open" and navigate to directory Examples/ N10_TESLACavityLong/ ECHOz2. Open the input file N10.e2dx. You should see the geometry shown in Fig. 2.6. 

• Go to menu "Bunch" and press "OK". 

![](images/f9c03d5759dc4f050f08a968236d4f528bf321890e743b8635c9b32c5465a2b8.jpg)



Trans. wake, Kick=538.077V/pC/m1, Spread=219.2172V/pC/m


![](images/925191e204af5a849f1deea98328b9ac01b52e0ccd983093db54154c9eb24df5.jpg)



Figure 3.6: Dipole wakes of resistive pillbox.


• Go to menu "Mesh" and press "Close". 

• Go to menu "Sover" and press "OK". The calculation starts. 

• Wait until message "Ready" appears and press "OK". The calculations is done. 

• Go to menu "Stop". 

• Press button with green "L" in the panel under main menu. You will see the wake and the loss factor. 

• Press button with yellow "G" to return to the geometry. 

• Close the program. 

Now the wake is saved in file wake.dat in directory Examples/ N10_TESLACavityLong/ ECHOz2. You can use the matlab script PostProcessor2D/ Round/ PP_ECHOz2.m to see the wake shown in Fig. 2.5. 

In order to calculate the dipole or the higher order modes change only "Mode #" value in solver box in the route described above. 

## 4. ECHO2D: Rectangular and Round Geometries

## 4.1 Introduction

Code ECHO2D calculates in time domain the electromagnetic fields generated by an electron bunch passing through rotationally symmetric or rectangular structures [6, 9]. The structure can consist of several materials with different permeabilities, permitivities and conductivities. The wall conductivity model for metals is available as well. This code has all possibilities of ECHOz1 and ECHOz2. Additionally it is able to calculate wakefields in rectangular structures.The bunch form can be arbitrary and the bunch can have finite energy. At the current version there is possibility to do particle tracking for fully rotationally symmetric case. 

Let us consider a line-charge beam with vanishing transverse dimensions, 

$$
\begin{array}{l} \rho (x _ {0}, y _ {0}, x, y, s) = Q \delta (x - x _ {0}) \delta (y - y _ {0}) \lambda (s), \\ j _ {z} (x _ {0}, y _ {0}, x, y, s) = c \rho (x _ {0}, y _ {0}, x, y, s), \end{array}\tag{4.1}
$$

where $x _ { 0 } , y _ { 0 } ,$ define the transverse offset of the beam, $s = z - c t$ is the local longitudinal coordinate in the bunch, Q is the bunch charge and $\lambda ( s )$ is the longitudinal bunch profile [for a point charge, $\lambda ( s ) = \delta ( s ) ]$ . The longitudinal wake potential $W _ { \parallel }$ at point $( x , y , s )$ is defined as [1] 

$$
W _ {\parallel} (x _ {0}, y _ {0}, x, y, s) = Q ^ {- 1} \int_ {- \infty} ^ {\infty} [ E _ {z} (x, y, z, t) ] _ {t = (z - s) / c} d z,\tag{4.2}
$$

where the electric field on the right-hand side is the solution to Maxwell’s equation with the sources of Eqs. (4.1) (this field, of course, is also a function of $x _ { 0 }$ and $y _ { 0 }$ omitted in the arguments of $E _ { z }$ for brevity). 

The charge distribution can be Fourier expanded as 

$$
\begin{array}{c} \rho (x _ {0}, y _ {0}, x, y, s) = \frac {1}{w} \sum_ {m = 1} ^ {\infty} \rho_ {m} (y _ {0}, y, s) \sin (k _ {x, m} x _ {0}) \sin (k _ {x, m} x), \\ \rho_ {m} (y _ {0}, y, s) = Q \delta (y - y _ {0}) \lambda (s). \end{array}\tag{4.3}
$$


(a)


![](images/247619acd3e0c7315a376a80993e771cdbe1160de81c83c6ad0241cb020335ac.jpg)


![](images/e77668ef38a4df1532a9ec0a004de3247e20808a7c578ee7ee05b67496170d22.jpg)



(b)


![](images/f872ca2174220332aedeb4a70285a1e26b30f30e02188e72ec9b7d3353b74246.jpg)



Figure 4.1: Structures of rectangular geometry: (a) dechirper, (b) tapered collimator.


The longitudinal wake potential can be written as: 

$$
W _ {\parallel} (x _ {0}, y _ {0}, x, y, s) = \frac {1}{w} \sum_ {m = 1} ^ {\infty} W _ {m} (y _ {0}, y, s) \sin (k _ {x, m} x _ {0}) \sin (k _ {x, m} x),\tag{4.4}
$$

where 

$$
\begin{array}{c} W _ {m} (y _ {0}, y, s) = [ W _ {m} ^ {c c} (s) \cosh (k _ {x, m} y _ {0}) + W _ {m} ^ {s c} (s) \sinh (k _ {x, m} y _ {0}) ] \cosh (k _ {x, m} y) \\ + [ W _ {m} ^ {c s} (s) \cosh (k _ {x, m} y _ {0}) + W _ {m} ^ {s s} (s) \sinh (k _ {x, m} y _ {0}) ] \sinh (k _ {x, m} y). \end{array}\tag{4.5}
$$

Thus in structures of constant width, for each mode number m four functions are needed to completely describe the longitudinal wake potential. These functions can be calculated as follows 

$$
W _ {m} ^ {c c} = W _ {m} (0, 0, s),
$$

$$
W _ {m} ^ {s c} = \frac {1}{k _ {x , m}} \frac {\partial}{\partial y} W _ {m} (0, 0, s),
$$

$$
W _ {m} ^ {c s} = \frac {1}{k _ {x , m}} \frac {\partial}{\partial y _ {0}} W _ {m} (0, 0, s),
$$

$$
W _ {m} ^ {s s} = \frac {1}{(k _ {x , m}) ^ {2}} \frac {\partial^ {2}}{\partial y \partial y _ {0}} W _ {m} (0, 0, s),\tag{4.6}
$$

where the $m ^ { \mathrm { t h } }$ modal component of the wake potential 

$$
W _ {m} (y _ {0}, y, s) = Q ^ {- 1} \int_ {- \infty} ^ {\infty} [ E _ {z, m} (y, z, t) ] _ {t = (z - s) / c} d z\tag{4.7}
$$

is excited by a charge distribution that does not depend on x, 

$$
\rho_ {m} (y _ {0}, y, s) = Q \delta (y - y _ {0}) \lambda (s).\tag{4.8}
$$

With a knowledge of the longitudinal wake we can calculate the transverse wakes. For example, the vertical wake potential, $W _ { y }$ , can be easily found through the Panofsky-Wenzel theorem 

$$
\frac {\partial}{\partial s} W _ {y} (x _ {0}, y _ {0}, x, y, s) = \frac {\partial}{\partial y} W _ {\parallel} (x _ {0}, y _ {0}, x, y, s).\tag{4.9}
$$

Let us consider a structure of constant width 2w that also has a vertical symmetry plane, at $y = 0$ . Structures in Fig. 6.1 (a) and (b) possess this symmetry; hence, they have a symmetry axis located at $x = w , y = 0$ . Due to the symmetry, the wake potential satisfies the equation 

$$
W _ {\parallel} (x _ {0}, y _ {0}, x, y, s) = W _ {\parallel} (x _ {0}, - y _ {0}, x, - y, s),\tag{4.10}
$$

and Eq. (4.5) simplifies: 

$$
W _ {m} (y _ {0}, y, s) = W _ {m} ^ {c c} (s) \cosh (k _ {x, m} y _ {0}) \cosh (k _ {x, m} y) + W _ {m} ^ {s s} (s) \sinh (k _ {x, m} y _ {0}) \sinh (k _ {x, m} y).\tag{4.11}
$$

Note that 

$$
W _ {m} (y _ {0}, y, s) = W _ {m} (y, y _ {0}, s).\tag{4.12}
$$

Let us consider the transverse wakes in such structures. We first introduce the integrated wake functions (sometimes called the step function response) 

$$
S _ {m} ^ {c c} = \int_ {- \infty} ^ {s} W _ {m} ^ {c c} (s ^ {\prime}) d s ^ {\prime}, \quad S _ {m} ^ {s s} = \int_ {- \infty} ^ {s} W _ {m} ^ {s s} (s ^ {\prime}) d s ^ {\prime}.\tag{4.13}
$$

It then follows from (4.9) that the transverse wake function can be written as 

$$
W _ {y} (x _ {0}, y _ {0}, x, y, s) = \frac {1}{w} \sum_ {m = 1} ^ {\infty} k _ {x, m} W _ {y, m} (y _ {0}, y, s) \sin (k _ {x, m} x _ {0}) \sin (k _ {x, m} x),\tag{4.14}
$$

$$
W _ {x} (x _ {0}, y _ {0}, x, y, s) = \frac {1}{w} \sum_ {m = 1} ^ {\infty} k _ {x, m} W _ {x, m} (y _ {0}, y, s) \sin (k _ {x, m} x _ {0}) \cos (k _ {x, m} x),\tag{4.15}
$$

where 

$$
\begin{array}{l} W _ {y, m} (y _ {0}, y, s) = S _ {m} ^ {c c} (s) \cosh (k _ {x, m} y _ {0}) \sinh (k _ {x, m} y) + S _ {m} ^ {s s} (s) \sinh (k _ {x, m} y _ {0}) \cosh (k _ {x, m} y), \\ W _ {x, m} (y _ {0}, y, s) = S _ {m} ^ {c c} (s) \cosh (k _ {x, m} y _ {0}) \cosh (k _ {x, m} y) + S _ {m} ^ {s s} (s) \sinh (k _ {x, m} y _ {0}) \sinh (k _ {x, m} y). \end{array}
$$

Representations (4.14), (4.15), are valid for arbitrary offsets of leading and trailing particles. 

For small offsets near the symmetry axis, $x = w , y = 0$ , the transverse wake potential is usually expanded in Taylor series, 

$$
W _ {y} (w, y _ {0}, w, y, s) \approx y _ {0} \frac {\partial}{\partial y _ {0}} W _ {y} (w, y _ {0}, w, 0, s) \big | _ {y _ {0} = 0} + y \frac {\partial}{\partial y} W _ {y} (w, 0, w, y, s) \big | _ {y = 0}.\tag{4.16}
$$

The first term in (4.16) is usually called the transverse dipole wake in the y-direction. It can be calculated as follows 

$$
W _ {y, d} (s) \equiv \frac {\partial}{\partial y _ {0}} W _ {y} (w, y _ {0}, w, 0, s) \big | _ {y _ {0} = 0} = \frac {1}{w} \sum_ {m = 1, \text { odd }} ^ {\infty} (k _ {x, m}) ^ {2} S _ {m} ^ {s s} (s).\tag{4.17}
$$

The second term in (4.16) is called the transverse quadrupole wake in y-direction; it is obtained by 

$$
W _ {y, q} (s) \equiv \frac {\partial}{\partial y} W _ {x} (w, 0, w, y, s) \big | _ {y = 0} = \frac {1}{w} \sum_ {m = 1, \text { odd }} ^ {\infty} (k _ {x, m}) ^ {2} S _ {m} ^ {c c} (s).\tag{4.18}
$$

The transverse wakes in the x direction are obtained by equations corresponding to those of Eqs. (4.17), (4.18). Note that $W _ { y , q } ( s ) = - W _ { x , q } ( s )$ 

In numerical calculations of structures with symmetry we can use the approach of paper [4] that allows us to reduce the calculation domain in half. Indeed the charge distribution (4.8) can be written as a sum of symmetric and antisymmetric parts 

$$
\rho_ {m} (y _ {0}, y, s) = \rho_ {m} ^ {E} (y _ {0}, y, s) + \rho_ {m} ^ {H} (y _ {0}, y, s),\tag{4.19}
$$

where 

$$
\rho_ {m} ^ {H} (y _ {0}, y, s) = \frac {1}{2} Q [ \delta (y - y _ {0}) + \delta (y + y _ {0}) ] \lambda (s),\tag{4.20}
$$

$$
\rho_ {m} ^ {E} (y _ {0}, y, s) = \frac {1}{2} Q [ \delta (y - y _ {0}) - \delta (y + y _ {0}) ] \lambda (s).\tag{4.21}
$$

In problems with the symmetric driving charges (4.20), the tangential component of the magnetic field will be zero in the symmetry plane (the so called “magnetic” boundary condition). In problems with the antisymmetric driving charges (4.21) the tangential component of the electric field will be zero in the symmetry plane (the “electric” boundary condition). Thus, instead of solving the system of equations in the whole domain, one can solve two independent problems in half of the domain: one problem with the “magnetic” boundary condition at $y = 0$ and one problem with the “electric” boundary condition at $y = 0$ . This is true not only for the line-charge current distribution (4.1), but for any arbitrary three dimensional charge distribution $\rho ( x , y , z , t )$ . From solutions $W _ { m } ^ { H } ( y _ { 0 } , y , s )$ and $W _ { m } ^ { E } ( y _ { 0 } , y , s )$ of the two problems we can easily find the one dimensional modal functions in Eq. (4.11): 

$$
W _ {m} ^ {c c} (s) = W _ {m} ^ {H} (0, 0, s), \qquad W _ {m} ^ {s s} (s) = (k _ {x, m}) ^ {- 2} \frac {\partial^ {2}}{\partial y _ {0} \partial y} W _ {m} ^ {E} (y _ {0}, y, s) \big | _ {y, y _ {0} = 0}.\tag{4.22}
$$

The current version of ECHO2D allows to treat only rectangular structures with vertical plane of symmetry. 

## 4.2 Installation

The program ECHO2D is compiled for Windows. It can be downloaded as archive ECHO2D.zip from https://www.echo4d.de. Extract the archive keeping the stricture of folders and files. 

The archive contains the following folders. 

1. Docs. It contains this manual. 

2. Codes/ECHO2D. It contains the executables: console application ECHO2D.exe and GUI application ECHO2D_GUI.exe . 

3. Examples. It contains several examples. 

4. MatLib4ECHO. It contains Matlab functions for postprocessing. 

5. PostProcessor2D. It contains Matlab scripts for postprocessing. 

In the following we will describe usage of console application only. 

## 4.3 Input files

The program ECHO2D requires two input files: 

• a file with geometry description in ASCII format; it can have an arbitrary name, 

• a file with parameters of the simulation in ASCII format; it has a fixed name input_in.txt. Additionally some special directories and files can be present as explained in the following Sections. 

```txt
z1 r1 z2 r2 z3 r3 z4 r4 0 k2 
```

## 4.3.1 Geometry description

The geometry can be imported as a file in ASCII format with extension "*.txt". 

The geometry file is ASCII file with extension "*.txt". It has the following format: 

%Number of materials 

$$
N _ {m}
$$

% Number of elements in metal with conductive walls, permeability, permitivity, cond. $N ^ { 1 } ~ \varepsilon ^ { 1 } ~ \mu ^ { 1 } ~ \sigma ^ { 1 }$ 

% Segments of lines and elipses with wall conductivity 

$$
z _ {1, 1} ^ {1} r _ {1, 1} ^ {1} z _ {2, 1} ^ {1} r _ {2, 1} ^ {1} z _ {3, 1} ^ {1} r _ {3, 1} ^ {1} z _ {4, 1} ^ {1} r _ {4, 1} ^ {1} d _ {1} ^ {1} k _ {1} ^ {1}
$$

$$
z _ {1, N} ^ {1} r _ {1, N} ^ {1} z _ {2, N} ^ {1} r _ {2, N} ^ {1} z _ {3, N} ^ {1} r _ {3, N} ^ {1} z _ {4, N} ^ {1} r _ {4, N} ^ {1} d _ {N} ^ {1} k _ {N} ^ {1}
$$

% Number of elements in material $N _ { m }$ , permetivity, permeability, conductivity $N ^ { N _ { m } } ~ { \varepsilon } ^ { N _ { m } } ~ { \mu } ^ { N _ { m } } ~ { \sigma } ^ { N _ { m } }$ 

% Segments of lines and elipses 

$$
z _ {1, 1} ^ {N _ {m}} r _ {1, 1} ^ {N _ {m}} z _ {2, 1} ^ {N _ {m}} r _ {2, 1} ^ {N _ {m}} z _ {3, 1} ^ {N _ {m}} r _ {3, 1} ^ {N _ {m}} z _ {4, 1} ^ {N _ {m}} r _ {4, 1} ^ {N _ {m}} d _ {1} ^ {N _ {m}} 0
$$

![](images/9d798017158b65d169565f693e4b6eb1a5a7eb5c2f42f273e5e22295e5472689.jpg)


The parameters in the geometry file are: 

• $N _ { m }$ - number of materials. 

• ε<sup>j</sup>, µ <sup>j</sup>, σ<sup>j</sup> - relative permitivity, permeability and conductivity in S/m of material number j. 

• N<sup>j</sup> - total number of segments (lines or elliptical arcs) in material j. 

• z , r - coordinates in cm of start point for segment number i. 

• z , r - coordinates in cm of end point for segment number i. 

• z<sub>3,i</sub>, r<sub>3,i</sub>, z<sub>4,i</sub>, r<sub>4,i</sub> - - coordinates in cm of square in which the ellipse is inscribed (for lines these parameters should be zeros). 

• z<sub>3,i</sub>, r<sub>3,i</sub> - coordinates in cm of top left corner. 

• z , r - coordinates in cm of bottom right corner. 

• d - orientation (0-clock, 1-anticlock). 

• k - wall conductivity in S/m (only for the first material). 

In this listing the strings which begin with % are not comments. They are separators and are obligatory. For rectangular geometry the format is the same with replacing r → y. 

As example let us consider the geometry shown in Fig. 2.2. The corresponding file will have the following content 

%N b f l 

% Number of elements in metal with conductive walls, permeability, permitivity, cond. 3 1 1 0 

% Segments of lines and elipses with wall conductivity 

```txt
z2 r2 z5 r2 0 0 0 0 0 k3, 
```

where k1, k2, k3 are conductivities of the segments. 

## 4.3.2 Parameters of simulation

The parameters of simulation are listed in input command file with fixed name input_in.txt. This file has a following format. 

```ini
GeometryFile=*.txt
Units=m/cm/mm
GeometryType=round/recta
Width=W
SymmetryCondition=magn/elec
Convex=0/1

%/%/%/%/%/%/%/% beam %/%/%/%/%/%/%/%/%/%/%/%/%%
InPartFile=-/*.txt/*.bin
BunchSigma=σz
Offset=y0
InjectionTimeStep=tinj

%/%/%/%/%/%/%/% field %/%/%/%/%/%/%/%/%/%/%/%%
InFieldDir=-/string
PortDir=-/string
PortPosition=zp

%/%/%/%/%/%/%/% model %/%/%/%/%/%/%/%/%/%/%%
WakeIntMethod=dir/ind
Modes=m0 ...mN
ParticleMotion=0/1
ParticleField=0/1
CurrentFilter=nF
ParticleLoss=0/1

%/%/%/%/%/%/% mesh %/%/%/%/%/%/%/%/%/%%%
MeshLength=Nz
StartPosition=zs
TimeSteps=nt
StepY=hy
StepZ=hz
NStepsInConductive=Nc
AdjustMesh=0/1
MeshMotionFile=-/*.txt

%%%/%%%%/%% monitors %%%/%%%%/%%%%/%%%%%
WakeMonitor=M1 M2 M3
BeamMonitor=M1 M2 M3 M4
FieldMonitor=F tF z0 z1 y0 y1 s0 s1 N
DumpField=0/1
DumpParticles=0/1 
```

## DumpCurrent=0/1

DumpMesh=0/1 

The parameters in this command file are: 

• GeometryFile [string]. Name of ASCII file with extension ’*.txt’. It defines the name of file with the geometry description. 

• Units [string]. Units of the geometry description: ’m’/’cm’/’mm’. 

• GeometryType [string]. It defines type of geometry: ’round’/’recta’. 

• Width [float/m]. Width of rectangular geometry W in x direction in m. The parameter is obsolete for round geometry. 

• SymmetryCondition [string] It defines the boundary condition on axis for rectangular geometry: elec/magn. 

• Convex [boolean]. Use $\mathbf { \Omega } ^ { , } _ { 1 } \mathbf { \Omega } ^ { , }$ to accelerate the calculation for "convex" geometry. "Convex" means here a geometry that has only one connected vacuum region in each plane transverse to the symmetry axis. 

• InPartFile [string]. Input bunch as a particle file $\binom { \dag } { \ d t } . \mathrm { b i n } ^ { \dag } )$ or as a pencil beam profile $\rho \ast _ { \mathrm { . } \mathrm { t x t } ^ { \prime } ) }$ . If you would like to use the default Gaussian pencil bunch with rms length $\sigma _ { z }$ use here option $\ ' _ { - } \ ' .$ 

• BunchSigma [float/m] The Gaussian pencil bunch rms length $\sigma _ { z }$ in m. 

• Offset [integer]. It defines value of $y _ { 0 }$ for pencil beam in mesh lines. In metric units it can be found as $( y _ { 0 } + 0 . 5 ) \cdot h _ { y }$ for round geometry or as $y _ { 0 } \cdot h _ { y }$ for rectangular one. The value "-1" mens that we use y as large as possible. The last choice provides the best accuracy. 

• InjectionTimeStep [integer]. Time of particle distribution injection in time steps. In metric units it can be found as $t _ { i n j } \cdot h _ { z } / c$ , where c is the light velocity. 

• InFieldDir [string]. It defines the name of directory with files of initial filed. Use ’-’ if initial field should be calculated in the program itself. 

• PortDir [string]. It defines the name of directory with file of transverse mode in waveguide port. Use $\ ' . 3$ if it is absent. 

• PortPosition [integer]. It defines the position $z _ { p }$ of the waveguide port in mesh lines. Use ’-1’ if the port is absent. 

• WakeIntMethod [string]. Direct or indirect wake potential integration: ’dir’/’ind’. 

• Modes [integer list]. It defines Fourier modes $m _ { 0 } \ldots m _ { N }$ to be calculated. 

• ParticleMotion [boolean]. It defines whether equations of motion are used (’1’) or the particle distributian is frozen $( ^ { , } 0 ^ { , } )$ . 

• ParticleField [boolean]. It defines whether fields are calculated (’1’) or not (’0’). 

• CurrentFilter [integer]. It defines how many times $n _ { F }$ a simple 2-points low-pass filter will be applied longitudinally to the current profile. 

• ParticleLoss [boolean]. It defines whether particles are lost in materials (’1’) or not $( ^ { , } 0 ^ { , } )$ 

• MeshLength [integer]. It defines length of the moving mesh $N _ { z }$ in the mesh lines. In metric units the length is $N _ { z } \cdot h _ { z }$ 

• StartPosition [integer]. It defines the longitudinal start position of moving mesh in mesh lines. 

• TimeSteps [integer]. It defines the number of time steps in the calculation. Use $\ ' _ { - 1 } \cdot '$ to fly through the whole structure. 

• StepY [float/m]. It defines the transverse mesh step $h _ { y }$ in m. 

• StepZ [float/m]. It defines the longitudinal mesh step $h _ { z }$ in m. 

• NStepsInConductive [integer]. It should be set to $\overrightarrow { \mathbf { \nabla } } 0 ^ { \circ }$ if the structure is perfectly electric conductive. Otherwise it defines an one dimensional mesh length for tangential components of electromagnetic field in the conductive parts [6]. The default value is 10. Increase this value to obtain a better accuracy. 

• AdjustMesh [boolean]. It defines whether the transverse mesh step is adjusted to the outgoing waveguide size $( ^ { , } 1 ^ { , } )$ or not $( ^ { , } 0 ^ { , } )$ ). 

• MeshMotionFile [string]. Name of ASCII file with extension ’*.txt’. It defines mesh motion. $\mathrm { U s e } ^ { \mathbf { \theta } _ { - } , \mathbf { \phi } _ { - } }$ to fly in positive direction with the light velocity. 

• WakeMonitor [integer list: $M _ { 1 } \ M _ { 2 } \ M _ { 3 } ]$ . Defines save points of the wake potential: from time step $M _ { 1 }$ to time step M2 with step $M _ { 3 }$ 

• BeamMonitor [integer list: $M _ { 1 } \ M _ { 2 } \ M _ { 3 } \ M _ { 4 } ]$ . It defines beam monitor. The parameters are explained in Section... 

• FieldMonitor [string: F string: t<sub>F</sub> integer list: F t<sub>F</sub> z<sub>0</sub> z<sub>1</sub> y<sub>0</sub> y<sub>1</sub> s<sub>0</sub> $s _ { 1 } \ N ]$ . It defines field monitor for the field component $F \colon \mathrm { { ' E x ' } { ' E y ' } / \mathrm { { ' E z ' } / \mathrm { { ' H x ' } / \mathrm { { ' H y ' } / \mathrm { { ' H z } } } } } }$ ’. Parameter $t _ { F }$ defines type of the monitor: $\mathbf { \ ' } _ { \mathbf { Z } } \mathbf { \ ' } _ { \mathbf { S } } \mathbf { \ ' }$ . Other parameters are explained in Section... 

• DumpField [boolean]. It defines whether the filed is dumped (’1’) or not (’0’). 

• DumpParticles [boolean]. It defines whether the particles are dumped (’1’) or not (’0’). 

• DumpCurrent [boolean]. It defines whether the current is dumped (’1’) or not (’0’). 

• DumpMesh [boolean]. It defines whether the mesh is dumped (’1’) or not (’0’). 

## 4.3.3 Beam setup

The beam setup is done by parameter InPartFile [string] in the command file input_in.txt. The beam can be defined in three ways: (1) the default Gaussian pencil bunch; (2) a pencil beam with arbitrary longitudinal profile; (3) a three dimensional particle distribution. 

Option ’-’ defines the default Gaussian pencil bunch with rms length defined by parameter BunchSigma in the command file input_in.txt. 

A pencil beam with arbitrary longitudinal profile should be described in file with extension $" * _ { \mathrm { . } \mathrm { t x t " } }$ . This file has the following format: 

% s[m] charge [normalized] 

s<sub>0</sub> $\rho ( s _ { 0 } )$ 

s<sub>1</sub> $\rho ( s _ { 1 } )$ 

s<sub>N</sub> $\rho ( s _ { N } )$ 

The first line is a comment. The first column describes the bunch coordinate with uniform step. The second column defines the bunch shape in arbitrary units. The s-coordinate should be positive and it increases from the head to the tail of the bunch. This shape will be projected on the moving mesh with the longitudinal coordinates in interval [0, StepZ*MeshLength]. 

Directory Examples/ N14_WakeMonitor_ArbitraryBunchShape contains an example of a special bunch profile. 

Finally the last option to define the bunch shape is to create a file with extension "*.bin" which contains a particle distribution. This files has binary format: ... 

## 4.3.4 Initial field setup

## 4.3.5 Waveguide port setup

## 4.3.6 Field monitors setups

In code ECHO2D two types of fields monitors exists: s-time and z-time. 

The field monitor is described by line FieldMonitor = F t z z y y s s N. Here F defines the filed component: $\mathrm { ^ { 5 } E x ^ { 3 } / ^ { 3 } E y ^ { 3 } / ^ { 3 } E z ^ { 3 } / ^ { 3 } H x ^ { 3 } / ^ { 3 } H y ^ { 3 } / ^ { 3 } H z ^ { 3 } }$ . The second parameter $t _ { f }$ defines the type of the field monitor: $\ ' _ { \mathrm { { s } } } \prime ' _ { \mathrm { { Z } } } \prime$ . The parameters $y _ { 0 }$ and $y _ { 1 }$ define the transverse interval in meters in which field is saved (see Figs). The last parameter N defines sampling interval in timesteps $h _ { t } = h _ { z } / c$ where c is the light velocity. 

![](images/1ad1454bab261a0c0ded65668e9dd762f294024dfb54b18082a1255b22c38ae8.jpg)



Figure 4.2: Field monitor of type s-time.


The s-time monitor is a static monitor. The window is defined as static rectangle in the calculation domain with longitudinal coordinates $z _ { 0 } , z _ { 1 }$ in meters. The filed is saved from time $t _ { 0 } = s _ { 0 } / c$ to time $t _ { 1 } = s _ { 1 } / c$ with interval $h _ { z } / c / N$ .The principle of s-time monitor is explained in Fig. 4.2. 

The z-time monitor is a moving monitor. The window is defined as moving rectangle in the moving mesh with longitudinal coordinates $s _ { 0 } , s _ { 1 }$ in meters. The filed is saved from time $t _ { 0 } = z _ { 0 } / c$ to time $t _ { 1 } = z _ { 1 } / c$ with interval $h _ { z } / c / N$ .The principle of z-time monitor is explained in Fig. 4.3. 

The output formats and postprocessing are described below. An example can be found in the directory Examples/ N8_FlatTaperWithFieldMonitor. 

## 4.4 Wakefield Calculation

The local folder should contain three files: 

• geometry file, 

• command file input_in.txt, 

• command file run.bat, which starts ECHO2D.exe. 

The calculations starts by execution of run.bat. During the simulation the progress in percents is shown. All modes are calculated in parallel. 

## 4.5 Output files

After execution of ECHO2D.exe the folder "round"/"magn"/"elec" will be created. It contains $N _ { m }$ files with modal wakes. They have name pattern WakeL_XX.txt, where XX is the mode number m . Each file is text file with two columns and contains a longitudinal modal wake. 

% vertical mesh step h[m] ofset[mesh lines] 

1.990050e−04 48 

% rectangular width [m] bunch rms [m] 

$$
0. 0 0 0 0 0 0 \mathrm{e} + 0 0 \quad 1. 0 0 0 0 0 0 \mathrm{e} - 0 3
$$

```txt
% modal wake
% s[m] W(s)[m*V/nC]
1.000000e-04 -2.752929e-03 
```

![](images/44a10f7c2e6945ba0f6d6d6f8cce6a2bef8d0df280bd3c51895e74ddf0cb29db.jpg)



Figure 4.3: Field monitor of type z-time.


For round geometry the units are $V / n C .$ 

R The modal wakes are not normalized on the beam offset. It means, for example, that in order to obtain the same transverse dipole wake (mode m = 1, file wakeT.dat) as in ECHOz2 you need to integrate the wake from file wakeL_01.txt divided by the beam offset squared. See script PP_WakeDipole.m from the post-processor directory. 

If field monitors had been setup in file input_in.txt then they are saved in the same directory in ASCII files with name pattern Monitor_mXX_NYY.txt, where XX is the mode number and YY the ordinal number of the monitor. 

The s-type monitor file has the following format: 

$\%$ Field $= F$ time $=$ s width $= W$ $\%$ k_ct $= k_{ct}$ h_ct $= h_{ct}$ ct0 $= s_0$ $\%$ k_r $= k_r$ h_r $= h_r$ r0 $= r_0$ $\%$ k_z $= k_z$ h_z $= h_z$ z0 $= z_0$ $s_0$ $F(r_0,z_0)\ldots F(r_0,z_1)$ ... $F(r_1,z_0)\ldots F(r_1,z_1)$ $s_0 + h_{ct}$ $F(r_0,z_0)\ldots F(r_0,z_1)$ ... $F(r_1,z_0)\ldots F(r_1,z_1)$ ... 

$$
\begin{array}{l} s _ {1} \\ F (r _ {0}, z _ {0}) \dots F (r _ {0}, z _ {1}) \\ \dots \\ F (r _ {1}, z _ {0}) \dots F (r _ {1}, z _ {1}) \end{array}
$$

The z-type monitor file has the following format: 

$$
\begin{array}{l} \text {\% Field} = F \text {time} = s \text {width} = W \\ \text {\% k\_ct} = k _ {c t} \text {h\_ct} = h _ {c t} \text {ct0} = z _ {0} \\ \text {\% k\_r} = k _ {r} \text {h\_r} = h _ {r} \text {r0} = r _ {0} \\ \text {\% k\_s} = k _ {s} \text {h\_s} = h _ {z} \text {s0} = s _ {0} \\ z _ {0} \\ F (r _ {0}, s _ {0}) \dots F (r _ {0}, s _ {1}) \\ \dots \\ F (r _ {1}, s _ {0}) \dots F (r _ {1}, s _ {1}) \\ z _ {0} + h _ {c t} \\ F (r _ {0}, s _ {0}) \dots F (s _ {0}, z _ {1}) \\ \dots \\ F (r _ {1}, s _ {0}) \dots F (r _ {1}, s _ {1}) \\ \dots \\ z _ {1} \\ F (r _ {0}, s _ {0}) \dots F (r _ {0}, s _ {1}) \\ \dots \\ F (r _ {1}, s _ {0}) \dots F (r _ {1}, s _ {1}) \end{array}
$$

For rectangular geometry the harmonic fileds $E _ { x } , E _ { y } , E _ { z }$ are saved in $\mathrm { V } / \mathrm { m } ^ { 2 }$ . For round geometry the electric field components $E _ { r } , E _ { z }$ are saved in $\mathrm { V } / \mathrm { m } ^ { 2 k + 1 }$ , where k is the mode number. The azimuthal component $E _ { \varphi }$ is in the same units but multiplied yet by radial coordinate in meters. Magnetic field components are saved multiplied by velocity of light c as cB and hence the units are the same as for the electric field components . 

In order to obtain the total field use the malab scripts described in Section "Postprocessing". 

The folder "round"/"magn"/"elec" contains several files with initial beam currents: Iz0.tx, Ir0.txt. File Iz0.tx contains z-component of the current on mesh and has the following format: 

$$
\begin{array}{l} s _ {0} I _ {z} (s _ {0}, r _ {0}) / c I _ {z} (s _ {0}, r _ {1}) / c \ldots I _ {z} (s _ {0}, r _ {N _ {r}}) / c \\ \ldots \\ s _ {N _ {z}} I _ {z} (s _ {N _ {z}}, r _ {0}) / c I _ {z} (s _ {N _ {z}}, r _ {1}) / c \ldots I _ {z} (s _ {N _ {z}}, r _ {N _ {r}}) / c \end{array}
$$

Here the first column is a longitudinal bunch coordinate in meters. The current component $I _ { z } / c$ is given in Coulombs. File Ir0.tx contains r-component of the initial current in the same format. 

## 4.6 Postprocessing

The folder PostProcessor2D contains two subfolders: 

• Fields, 

• Wakes. 

to be continued... 

## 4.6.1 Wakes

The matlab scripts ... 

## 4.7 Examples

In this section we consider several examples included in the archive at the directory Examples. 

## 4.7.1 Example 1: Round collimator

The examples of round collimator can be found in directories Examples/ N1_RoundCollimatorLong, Examples/ N2_RoundCollimatorDipole, Examples/ N3_RoundCollimatorDipoleConductive. 

In order to calculate the longitudinal wake of monopole mode (m = 0) proceed as follows: 

• Go to directory Examples/ N1_RoundCollimatorLong/ ECHO2D and run run.but It calls the console executable from directory Codes/ECHO2D. 

• Alternatively you can use GUI application and file N1.echo2d. 

After the code execution a directory round is created. The monopole wake is saved in file wakeL_00.txt. Use the matlab script PostProcessor2D/ Round/ PP_Wake_Monopole.m to see the wake shown in Fig. 2.5. The transverse wake is zero for the monopole mode. 

In order to calculate the transverse wake of dipole mode (m = 1) proceed as follows: 

• Go to directory Examples/ N2_RoundCollimatorDipole/ ECHO2D and run run.but It calls the console executable from directory Codes/ ECHO2D. 

• Alternatively you can use GUI application and file N2.echo2d. 

After the code execution a directory round is created. The dipole wake is saved in file wakeL_01.txt. Use the matlab script PostProcessor2D/Round/ PP_Wake_Dipole.m to see the wake shown in Fig. 3.3. 

The last example is the same collimator but with conductive small pipe. The conductivity is equal to 1 S/m. In order to calculate the transverse wake of dipole mode (m = 1) for the conductive collimator proceed as follows: 

• Go to directory Examples/ N3_RoundCollimatorDipoleConductive/ ECHO2D and run run.but It calls the console executable from directory Codes/ ECHO2D. 

• Alternatively you can use GUI application and file N3.echo2d. 

After the code execution a directory round is created. The dipole wake is saved in file wakeL_01.txt. Use the matlab script PostProcessor2D/ Round/ PP_Wake_Dipole.m to see the wake shown in Fig. 3.4. 

## 4.7.2 Example 2: Resistive pillbox cavity

The example of pillbox cavity can be found in directory Examples/ N9_ResistivePillbox. The cavity walls have conductivity equal to 1000 S/m. 

• Go to directory Examples/ N9_ResistivePillbox/ ECHO2D and run run.but It calls the console executable from directory Codes/ ECHO2D. 

• Alternatively you can use GUI application and file N9.echo2d. 

After the code execution a directory round is created. The dipole wake is saved in file wakeL_01.txt. Use the matlab script PostProcessor2D/ Round/ PP_Wake_Dipole.m to see the wake shown in Fig. 3.6. The transverse wake is zero for the monopole mode. 

In order to calculate the monopole or the higher order modes change only "Modes" value in the input file. 

## 4.7.3 Example 3: TESLA cavity

The example of TESLA cavity can be found in directory Examples/ N10_TESLACavityLong. 

In order to calculate the longitudinal wake of monopole mode (m = 0) proceed as follows: 

• Go to directory Examples/ N10_TESLACavityLong/ ECHO2D and run run.but It calls the console executable from directory Codes/ECHO2D. 

• Alternatively you can use GUI application and file N10.echo2d. 

After the code execution a directory round is created. The monopole wake is saved in file wakeL_00.txt. Use the matlab script PostProcessor2D/ Round/ PP_Wake_Monopole.m to see the wake shown in Fig. 2.5. 

In order to calculate the dipole or the higher order modes change only "Modes" value in in the input file. 

## 4.7.4 Example 4: Flat absorber

![](images/ee5ca66b0e18b1ee9e019433743515b96b343fdaf5e97adc55a5c533a12930e3.jpg)



Figure 4.4: Geometry of flat absorber.


The example of a flat abosrber can be found in directories Examples/ N4_FlatAbsorberLongQuad and Examples/ N4_FlatAbsorberDipole. 

The absorber has geometry shown in Fig. 4.4 with $W i d t h = 0 . 0 7$ defined in file input_in.txt. The bunch flies in ZY symmetry plane $( x _ { 0 } = x = 0 )$ and we calculate only odd modes $M o d e s = I \ : 3 \ : 5 \ : 7$ 9 11 13 15. In order to calculate the longitudinal and quadrupole wakes we use SymmetryCondition = magn and proceed as follows: 

• Go to directory Codes/ ECHO2D and start ECHO2D_GUI.exe. 

• Go to menu "File/Open" and navigate to directory Examples/ N4_FlatAbsorberLongQuad/ ECHO2D. Open the input file N4.echo2d. You should see the geometry shown in Fig. 4.4. 

• Go to menu "Sover/ Start". The calculation starts. 

• Wait until message "Ready" appears and press $" \mathrm { O K " }$ . The calculations is done. 

• Go to menu "Stop". 

• Alternatively you can run the console application with command file run.bat. 

The results of calculation are placed in directory magn. It contains 8 modal wakes. Run matlab script PostProcessor2D/ Flat/ PP_Wcc.m to calculate coefficients $W _ { c c } ( k _ { x } , s )$ shown in Fig. 4.5. Finally run matlab script PostProcessor2D/ Flat/ PP_WakeLQ.m to calculate longitudinal and quadrupole transverse wakes shown in Fig. 4.6. 

In order to calculate the dipole wake we use SymmetryCondition = elec and proceed as follows: 

• Go to directory Codes/ECHO2D and start ECHO2D_GUI.exe. 

• Go to menu "File/Open" and navigate to directory Examples/ N5_FlatAbsorberLongQuad/ ECHO2D. Open the input file N5.echo2d. You should see the geometry shown in Fig. 4.4. 

• Go to menu "Sover/ Start". The calculation starts. 

• Wait until message "Ready" appears and press $" \mathrm { O K " }$ . The calculations is done. 


Modal wakes W(k.s)[V/pC*m] at offset=30.4 mm with magnetic BC


![](images/7a002c11ab89e49c850d389d52d935ce7eff299829852b32d3c6b8ea75cd731d.jpg)



1D modal functions W $\updownarrow e \updownarrow \updownarrow , \updownarrow \updownarrow / \updownarrow \updownarrow \updownarrow \updownarrow$


![](images/0aa31b3003d04fab4b984f55b16da8a8327287e2796d6efd23e0c7361ce56215.jpg)



Figure 4.5: Flat absorber. Coefficients.


• Go to menu "Stop". 

• Alternatively you can run the console application with command file run.bat. 

The results of calculation are placed in directory elec. It contains 8 modal wakes. Run matlab script PostProcessor2D/ Flat/ PP_Wss.m to calculate coefficients $W _ { s s } ( k _ { x } , s )$ shown in Fig. 4.7. 

Before to proceed copy there directory magn from the previous case (or calculate it by changing SymmetryCondition=magn). Run matlab script PostProcessor2D/ Flat/ PP_Wcc.m to calculate coefficients $W _ { c c } ( k _ { x } , s )$ . Finally run matlab script PostProcessor2D/ Flat/ PP_WakeLQD.m to calculate longitudinal, quadrupole transverse and dipole transcerse wakes shown in Fig. 4.8. 

Start Matlab and open PostProcessor/ Flat/ PP_WakeZY. Adjust $^ { 6 6 } \mathrm { y } ^ { \prime 3 } , \^ { 6 6 } \mathrm { y 0 } ^ { \prime }$ . Run this matlab file to create file WakeZY.txt with longitudinal and transverse wakes for the offsets $ { \mathrm { y } } ,  { \mathrm { y 0 } }$ . Matlab script bf PP_WakeZY.m creates 4 plots shown in Fig. 4.9. The longitudinal and transverse wakes are on the right side. 3D plot at the left side are for estimation of the number of modes. It can be seen that we need more than 8 modes in this example (near the boundary!). 

## 4.7.5 Example 5: Pohang Dechirper

The example of the dechirper can be found in directoriy Examples/ N6_PohangDechirper. 

The absorber has geometry shown in Fig. 4.10 with $W i d t h = 0 . 0 5$ m defined in file input_in.txt. The bunch flies in ZY symmetry plane $( x _ { 0 } = x = 0 )$ and we calculate only odd modes Modes = 1 3 5 7 9 11 13 15 17 19 21 23 25 27 29. In order to calculate the longitudinal and quadrupole wakes we use SymmetryCondition = magn and proceed as follows: 

• Check that parameter SymmetryCondition has value "magn" in file input_in.txt. 

• Go to directory Codes/ ECHO2D and start ECHO2D_GUI.exe. 

• Go to menu "File/Open" and navigate to directory Examples/ N6_PohangDechirper/ ECHO2D. Open the input file N6.echo2d. You should see the geometry shown in Fig. 4.10. 

• Go to menu "Sover/ Start". The calculation starts. 

• Wait until message "Ready" appears and press $" \mathrm { O K " }$ . The calculations is done. 

• Go to menu "Stop" and close the GUI program. 

• Alternatively you can run the console application with command file run.bat. 

![](images/cae50c6a102f85a1188f4876fecc11d8eab7cf0ea8f5b2302ea7fe4c1bab62ee.jpg)


![](images/2951de83006abb9c58c55dd3541d0fbe2e2007a14f76818336ae45b1400235c6.jpg)


![](images/26cb32e0e88608c72a8517cfbf1f934f934ee33cdee12cab6415fdbe1eac02c2.jpg)


![](images/1609a406b073690cc6506d41539d9110993a2909b8bbdc7d357b062a5cf616a2.jpg)



Figure 4.6: Flat absorber. Longitudinal and quadrupole transverse wakes.


The results of calculation are placed in directory magn. It contains 15 modal wakes. Run matlab script PostProcessor2D/ Flat/ PP_Wcc.m to calculate coefficients $W _ { c c } ( k _ { x } , s )$ shown in Fig. 4.11. Finally run matlab script PostProcessor2D/ Flat/ PP_WakeLQ.m to calculate longitudinal and quadrupole transverse wakes. 

In order to calculate the dipole wake we use SymmetryCondition = elec and proceed as follows: 

• Change the parameter SymmetryCondition to value "elec" in file input_in.txt. 

• Go to directory Codes/ECHO2D and start ECHO2D_GUI.exe. 

• Go to menu "File/Open" and navigate to directory Examples/ N6_PohangDechirper/ ECHO2D. Open the input file N6.echo2d. You should see the geometry shown in Fig. 4.10. 

• Go to menu "Sover/ Start". The calculation starts. 

• Wait until message "Ready" appears and press $" \mathrm { O K " }$ . The calculations is done. 

• Go to menu "Stop". 

• Alternatively you can run the console application with command file run.bat. 

The results of calculation are placed in directory elec. It contains 15 modal wakes. Run matlab script PostProcessor2D/ Flat/ PP_Wss.m to calculate coefficients $W _ { s s } ( k _ { x } , s )$ shown in Fig. 4.12. 

Finally run matlab script PostProcessor2D/ Flat/ PP_WakeLQD.m to calculate longitudinal, quadrupole transverse and dipole transcerse wakes shown in Fig. 4.13. 

## 4.7.6 Example 7: Flat tapered collimator with resistivity

The example of the flat tapered collimator with resistivity can be found in directory Examples/ N7_TaperedResistiveCollimator. 

The collimator has geometry shown in Fig. 4.14 with Width = 0.01m defined in file input_in.txt. The bunch flies in ZY symmetry plane $( x _ { 0 } = x = 0 )$ ) and we calculate only odd modes $M o d e s = I \ : 3 \ : 5$ 7 9 11 13 15. In order to calculate the longitudinal and quadrupole wakes we use SymmetryCondition = magn and proceed as follows: 

• Go to directory Codes/ ECHO2D and start ECHO2D_GUI.exe. 

• Go to menu "File/Open" and navigate to directory Examples/ N7_TaperedResistiveCollimator/ ECHO2D. Open the input file N7.echo2d. You should see the geometry shown in Fig. 4.14. 


Modal wakes W(k,s)[V/pC*m] at offset=30.4 mm with electric BC


![](images/68f8e01877f764e5825e1318c552feae34609d88bc530a23c1b4ccc703ccd356.jpg)



1D modal functions W $\mathfrak { s s } ^ { ( k _ { \mathrm { x } } , \mathsf { S } ) [ \mathsf { V } / \mathsf { p C } ^ { \ast } \mathsf { m } ] }$


![](images/92c9c4bcb9af31a5d346c8af970104917ebb1ba07307429a926b0431569aefe4.jpg)



Figure 4.7: Flat absorber. Coefficients.


• Go to menu "Sover/ Start". The calculation starts. 

• Wait until message "Ready" appears and press $" \mathrm { O K " }$ . The calculations is done. 

• Go to menu "Stop" and close the GUI program. 

• Alternatively you can run the console application with command file run.bat. 

The results of calculation are placed in directory magn. It contains 8 modal wakes. Run matlab script PostProcessor2D/ Flat/ PP_Wcc.m to calculate coefficients $W _ { c c } ( k _ { x } , s )$ . Finally run matlab script PostProcessor2D/ Flat/ PP_WakeLQ.m to calculate longitudinal and quadrupole transverse wakes shown in Fig. 4.15. 

## 4.7.7 Example 8: Field monitor for flat taper

The example of the flat taper can be found in directory Examples/ N8_FlatTaperWithFieldMonitor. 

$$
W i d t h = 0. 0 5 \mathrm{m}
$$

$$
(x _ {0} = x = 0)
$$

$$
M o d e s = 1 3
$$

5 7. The bunch flies on axis and we use SymmetryCondition = magn and proceed as follows: 

• Go to directory Codes/ ECHO2D and start ECHO2D_GUI.exe. 

• Go to menu "File/Open" and navigate to directory Examples/ N8_FlatTaperWithFieldMonitor/ ECHO2D. Open the input file N8.echo2d. You should see the geometry shown in Fig. 4.16. 

• Go to menu "Sover/ Start". The calculation starts. 

• Wait until message "Ready" appears and press $" \mathrm { O K " }$ . The calculations is done. 

• Go to menu "Stop" and close the GUI program. 

• Alternatively you can run the console application with command file run.bat. 

The results of calculation are placed in directory magn. It contains 4 modal wakes. Run matlab script PostProcessor2D/ Fields/ Flat/ PP_CreateTotalField_EzEyHx.m to create the full field from monitor defined by string MonitorNumber=2 in the script. Then run script PP_FieldMonitor to see the total field shown in Fig. 4.17. 

## 4.7.8 Example 9: Round dielectric pipe

The example of the round dielectric pipe can be found in directory Examples/ N11_Round_Dielectric. 

![](images/e84a802029f56f35c765ea3372eb4b828552da23320af15c97a22b0a9a3419d2.jpg)



Figure 4.8: Flat absorber. Longitudinal, quadrupole and dipole transverse wakes.


The pipe has geometry shown in Fig. 6.3. In order to estimate the steady state solution we will calculate wakes for pipe of length 1.1m and for pipe of length 1m. Then we subtract the second wake from the first one. We proceed as follows: 

• Open file input_in.txt and set GeometryFile = PipeCondLayer_110cm.txt. 

• Go to directory Codes/ ECHO2D and start ECHO2D_GUI.exe. 

• Go to menu "File/Open" and navigate to directory Examples/ N8_FlatTaperWithFieldMonitor/ ECHO2D. Open the input file N11.echo2d. You should see the geometry shown in Fig. 6.6. 

• Go to menu "Sover/ Start". The calculation starts. 

• Wait until message "Ready" appears and press "OK" . The calculations is done. 

• Go to menu "Stop" and close the GUI program. 

• Alternatively you can run the console application with command file run.bat. 

The results of calculation are placed in directory round. Run matlab scripts PostProcessor2D/ round/ PP_Wake_Monopole.m and PP_Wake_Dipole.m . Rename the directory round in round_1m10. In file input_in.txt set GeometryFile = PipeCondLayer_100cm.txt and repeat the calculations together with execution of the matlab scripts. Rename the directory round in round_1m. The comparison of the results from ECHO2D with ECHO1D can be seen by running the script Compare_2D_vs_1D.m in Matlab. The result is shown in Fig. 6.7. 

## 4.7.9 Example 10: Flat dielectric pipe

The example of the flat dielectric pipe can be found in directory Examples/ N11_Flat_Dielectric. Proceed as in the previous example and see the corresponding section in ECHO1D. 

## 4.7.10 Example 11: TESLA cavity with restart procedure, wake monitors and arbitrary bunch shape

The examples can be found in directory Examples/ N14_WakeMonitor_ArbitraryBunchShape and Examples/ N13_Restart. As manual use the PPTX file in directory Docs of these examples. 

![](images/dc4ae06938881c0b3d974f8e85d1bc9b9397b7ee5108bf337bb8b938350244ba.jpg)


![](images/cdc10e353a8d14928dfec22fce096eb1ccccae69cccf92cbe964f8eafc3d0165.jpg)


![](images/9fe10b9eff4b2f0f58b83c323085c85beb68497973e2e07e928f26de0465b5e3.jpg)


![](images/3bb9805242a6fabeec082cbd68d09cfd26e43a1914d5b1a1260fda1f729fd2ca.jpg)



Figure 4.9: Flat absorber. Longitudinal and transverse wakes for offsets $y _ { 0 } = y = 3 0$ mm.


## 4.7.11 Example 12: Particle tracking in dielectric pipe

The examples can be found in directory Examples/ N15_ParticleTracking and Examples/ N13_Restart. As manual use the PPTX file in directory Docs of these examples. 

![](images/bd9dddf673613b5ec61ee4315acd9f9e45f44cfbf2687e92784a9e8c4c942b1f.jpg)



Figure 4.10: Geometry of the dechirper.



Modal wakes W(k,s)[V/pC*m] at offset=2.8 mm with magnetic BC


![](images/4de8453a1a09ba15a03dce95bc8811fb9bc58ed2dff966d518c99e6a73a2b0c1.jpg)



1D modal functions ${ \pmb w } _ { \mathrm { c c } } ( { \pmb k } _ { \mathbf { x } ^ { \prime } }$ s)[V/pC*m]


![](images/e0679ec004cc615c57d3aa44e824b8a833b4e9afeaf08a5fe98aee5fac2d735d.jpg)



Figure 4.11: Dechirper. Coefficients.



Modal wakes W(k,s)[V/pC*m] at offset=2.8 mm with electric BC


![](images/e2506d61d35f510ed8a7712a2991f34b47659553b5fcc18cab7fbbe95f17d16f.jpg)



1D modal functions ${ \pmb w } _ { { \sf s s } } ( { \bf k } _ { \bf x } )$ s)[V/pC*m]


![](images/d49327246409be9bb9f303ea8aec6e6ef78d4f14de007cc65f57e62b4ec8a6e0.jpg)



Figure 4.12: Dechirper Coefficients.


![](images/7a24e988620b583170e87f6fcfc0747ea937b52e2dc59ff35b7205b7e09a6743.jpg)


![](images/c695bc581d8c2d3abbf4f83a73363f19305fca7208959cb5f24108bc9683cf27.jpg)


![](images/dd382d2a4134834d2a3783b3fa3ea1fd08520ee8b3be0b95569d81041992b82b.jpg)


![](images/8313421a9f4a86debda831ce2623e6962947b382a486ae60f2c14c523fad8213.jpg)


![](images/54df907fcaaf717f3a91683a8dddbc5945eca46add23cd2078ab9d2a6273d793.jpg)


![](images/0783871f4754c5cc06b3978f2c6969387171a19e958f34b080f386877f7eb6af.jpg)



Figure 4.13: Dechirper. Wakes.


![](images/6c1ce4a61a886cb5779dad0525daf3a293c90158945d9e3430ba44e3e2935372.jpg)



Figure 4.14: Geometry of flat tapered collimator with resistivity.


![](images/10627b10bf7247ffbc8a17a8bb50f0ba0a8b31ee5f0e9d7efc1f55086f749cf9.jpg)


![](images/1059e5fbf4fc0460ef3e7c06fdf54e5f30e140ed5899fa66dc97f1ea75b519d7.jpg)


![](images/d4927c83ce42bbf461b5c5e688e9478e0d3c8ff15b03045759e1633ebfecd8a5.jpg)


![](images/f9106c4ff6d9f57f5cfd3b444744c05faec8dbf4eaa38185727e18fedc07d969.jpg)



Figure 4.15: Tapered collimator. Wakes.


![](images/03e41beb22ddc52ab056164403ea93020fac87b2c613a5778ce7c5a4ad3f73fc.jpg)



Figure 4.16: Geometry of flat taper.


![](images/071e5f1d0e9455edd7a4de938ff56dfad17c53c0167445db26ef1b2569aff036.jpg)


![](images/e130b49d9043d0a1a6c01ef78ee0f65bfad751a39c520026f75278f0f2c2b376.jpg)



Figure 4.17: Flat taper. Field monitor.


## 5. ECHO3D: Three Dimensional Geometry

ECHO3D allows to calculate wakefields in three dimensional structures. The version 3.2 of the code is thread parallelized and allows to use different materials. The volume and wall conductivities are not implemented and will be available in the next releases. 

## 5.1 Introduction

Code ECHO3D calculates in time domain the electromagnetic fields generated by an electron bunch passing through arbitrary three dimensional chamber. The structure can consist of several materials with different permeabilities and permitivities. The volume and wall conductivity model for metals are not available. The bunch form is a Gaussian pencil bunch. The arbitrary bunch form is possible but this option is not described here. 

For the time being the beam can fly only along x-axis. Hence the notation below is different from the previous sections. 

Let us consider a line-charge beam with vanishing transverse dimensions, 

$$
\begin{array}{l} \rho (y _ {0}, z _ {0}, y, z, s) = Q \delta (z - z _ {0}) \delta (y - y _ {0}) \lambda (s), \\ j _ {z} (y _ {0}, z _ {0}, y, z, s) = c \rho (y _ {0}, z _ {0}, y, z, s), \end{array}\tag{5.1}
$$

where $y _ { 0 } , z _ { 0 } ,$ , define the transverse offset of the beam, $s = x - c t$ is the local longitudinal coordinate in the bunch, Q is the bunch charge and $\lambda ( s )$ is the longitudinal bunch profile [for a point charge, $\lambda ( s ) = \delta ( s ) ]$ . The longitudinal wake potential $W _ { \parallel }$ at point $( x , y , s )$ is defined as [1] 

$$
W _ {\parallel} (x _ {0}, y _ {0}, x, y, s) = Q ^ {- 1} \int_ {- \infty} ^ {\infty} [ E _ {x} (x, y, z, t) ] _ {t = (x - s) / c} d x,\tag{5.2}
$$

where the electric field on the right-hand side is the solution to Maxwell’s equation with the sources of Eqs. 5.1 (this field, of course, is also a function of $y _ { 0 }$ and $z _ { 0 }$ omitted in the arguments of $E _ { x }$ for brevity). 

With a knowledge of the longitudinal wake we can calculate the transverse wakes as usually. 

## 5.2 Installation and work-flow

The program ECHO3D is compiled for Windows. It can be downloaded as archive ECHO3D.zip from https://www.echo4d.de. Extract the archive keeping the stricture of folders and files. 

The archive contains the following folders. 

1. Docs. It contains this manual. 

2. Codes. It contains the executables: console application ECHO3D.exe, GUI application ECHO3D_GUI.exe. Additionally the folder contains three executables: for meshing (Mesher.exe), initial field/current creation (InitField.exe) and indirect wake potential calculation (IndirectIntegration.exe). 

3. Examples. It contains several examples. 

4. Matlab4ECHO. It contains Matlab functions for postprocessing. 

5. PostProcessor3D. It contains Matlab scripts for postprocessing. 

As can be seen from Fig. 5.1 we will use not one but several programs. 

![](images/ceb7dacdfcafa5eae6363a3ce9c6b8a4baa2089baa05e043e0c91f0927d369b7.jpg)



Figure 5.1: Work-flow diagram for 3D calculations.


The program package does not provide any tool for modeling of geometry. It is suggested that each material is described by file in format STL. The reader can use an arbitrary CAD program for it. In our examples we use non-commercial code FreeCAD. It can be installed from web site https://www.freecadweb.org. 

## 5.3 Input files

The program ECHO3D requires two input files: 

• a file with geometry description in ASCII format; it can have an arbitrary name, 

• a file with parameters of the simulation in ASCII format; it has a fixed name input.txt. The geometry itself is a collection of STL files placed in folder Geometry.The geometry should be created in millimeters. Additionally some special directories and files could be present as explained in the following Sections. 

## 5.3.1 Geometry description

The geometry file is ASCII file with extension "*.txt". It has the following format: 

%%%%%%%%%%% Materials %%%%%%%%%%%%%%%%%% 

MaterialsNumber = N<sub>m</sub> 

Material .stl 1 1 0 

Material .stl ε µ 0 

Material<sub>N</sub> .stl ε<sub>N</sub> µ<sub>N</sub> 0 

%%%%%%%%%%% Meshing parts %%%%%%%%%%%%%% 

MeshParts = $N_{p}$ $part_{1}$ $x_{1}^{min}$ $x_{1}^{max}$ $part_{2}$ $x_{2}^{min}$ $x_{2}^{max}$ ... $part_{N_{p}}$ $x_{N_{p}}^{min}$ $x_{N_{p}}^{max}$ %%%%%%%%%% Geometry list %%%%%%%%%%% 

GeometryParts = $N_{g}$ meshpart $_{1}$ iter $_{1}$ meshpart $_{2}$ iter $_{2}$ ...
meshpart $_{N_{g}}$ iter $_{N_{g}}$ 

The geometry file contains three sections. The first section is a list of materials from folder Geometry. The parameters here are: 

$N _ { m }$ [integer] - number of materials. 

• Material<sub>i</sub>.stl [string]- name of the STL file from directory Geometry which describes the geometry of the material number i . 

• ε<sup>i</sup>, µ<sup>i</sup> [float]- relative permitivity, permeability of material number i. 

The second section is a list of the geometry parts which will be meshed by the mesher Mesher.exe and placed in a new folder Mesh. The parameters here are: 

• $N _ { p }$ [integer]- number of geometry parts for the meshing. 

• part<sub>i</sub>.stl [string]- an arbitrary but unique name of meshing part number i. 

$x _ { i } ^ { m i n } , x _ { i } ^ { m a x }$ [float/mm] - the minimal and the maximal longitudinal coordinates in mm of the geometry part number i. 

Finally the third section is a list of the geometry parts from the second section which compose the structure. The parameters here are: 

• $N _ { g }$ [integer] - number of geometry parts in the list. 

• meshpart .stl [string] - an arbitrary geometry part from the second section. 

• iter [integer] - the number of copies of geometry part number i in the list. 

As example let us consider the geometry of dielectric pipe shown in Fig. ??. The corresponding file will have the following content 

%%%%%%%%%%% Materials %%%%%%%%%%%%%%%%%% 

%%%%%%%%%%% Meshing parts %%%%%%%%%%%%%% 

```txt
MeshParts = 2
pipe 1 3
diel 7 9 
```

%%%%%%%%%%% Geometry list %%%%%%%%%%%%%% 

```txt
GeometryParts = 3
pipe 1
diel 50
pipe 1. 
```

The two STL files PEC.stl and Dielectric.stl are created with program FreeCAD and can be found in directory Examples/ N9_Round_Dielectric/ ECHO3D/ Geometry. 

## 5.3.2 Parameters of simulation

The parameters of simulation are listed in input command file with fixed name input.txt. This file has a following format. 

%%%%%%%%%%%%%% geometry %%%%%%%%%%%%%%%%%%%% 

```toml
GeometryFile = '*.txt'
Units = 'mm'
BoundaryConditionsX = [BCx0 BCx1]
BoundaryConditionsY = [BCy0 BCy1]
BoundaryConditionsZ = [BCz0 BCz1] 
```

%%%%%%%%%%%%%%% beam %%%%%%%%%%%%%%%%%%%%%%% 

$\mathrm{BunchSigma} = \sigma_x$ $\mathrm{BunchPosition} = [y_0 z_0]$ 

%%%%%%%%%%%%%%% mesh %%%%%%%%%%%%%%%%%%%%%%% 

MeshLength = $N_{x}$ dY = $[y_{min} y_{max}]$ dZ = $[z_{min} z_{max}]$ Steps = $[h_{x} h_{y} h_{z}]$ Tolerance = tol 

%%%%%%%%%%%%%%% solver %%%%%%%%%%%%%%%%%%%%%%% 

```ini
SolverType = 'adi'/'ati'
Conformal = 0/1/2
Iterations = iter
InitialIterations = iter₀
Damping = k_damp
ThreadsNumber = N_threads. 
```

The parameters in this command file are: 

• GeometryFile [string]. Name of ASCII file with extension ’*.txt’. It defines the name of file with the geometry description. 

• Units [string]. Units of the geometry description. In current version only ’mm’ can be used. Hence the geometry in the STL files should be in millimeters. 

• BoundaryConditionsX [boolean list: BCx BCx ]. It defines boundary conditions of the global mesh domain in x-direction: ’0’ defines the magnetic boundary condition (tangential component of the magnetic filed is zero),’1’ defines the electric boundary condition (tangential component of the electric filed is zero). 

• BoundaryConditionsY [boolean list: $B C y _ { 0 } B C y _ { 1 } ]$ . It defines boundary conditions of the global mesh domain in y-direction. 

• BoundaryConditionsZ [boolean list: $B C z _ { 0 } B C z _ { 1 } ]$ . It defines boundary conditions of the global mesh domain in z-direction. 

• BunchSigma [float/mm] The Gaussian pencil bunch rms length $\sigma _ { x }$ in mm. 

• BunchPosition [integer list: $y _ { 0 } z _ { 0 } ]$ . It defines values of y , z for pencil beam in mesh lines. In metric units they can be found as $y _ { m i n } + y _ { 0 } \cdot h _ { y } , z _ { m i n } + z _ { 0 } \cdot h _ { y }$ 

• MeshLength [integer]. It defines length of the moving mesh $N _ { x }$ in the mesh lines. In metric units the length is $N _ { x } \cdot h _ { x }$ 

• dY [float list:y<sub>min</sub> y<sub>max</sub> /mm]. It defines the transverse mesh dimension in y-direction in mm. 

• dZ [float $\operatorname* { l i s t } { : z _ { m i n } z _ { m a x } / \mathrm { m m } } ]$ . It defines the transverse mesh dimension in z direction in mm. 

• Steps [float list: $h _ { x } h _ { y } h _ { z } / \mathrm { m m } ]$ . It defines the mesh steps in mm. 

• Tolerance [double]. It should be a positive value smaller than 1. The mesh facets whose material fraction is less than tol are considered as fully metallic ones. The default value is 0.01. Increase this value if any instability appears. 

• SolverType [string]. This parameter can have two values: ’adi’ - alternative-direction solver,’ati’ - alternative-triangular solver. In most cases ’adi’ should be used. Solver ’ati’ can be used if the transverse mesh steps are smaller trhan the longitudinal one. 

• Conformal [integer]. This parameter can have three values: $\mathbf { \overrightarrow { \mathbf { \nabla } } } _ { 0 } ,$ - staircase mesh, $\mathbf { \bar { \rho } } _ { 1 } , \mathbf { \Phi } _ { 1 }$ - simple conformal method, ’2’ - uniformly stable conformal method. In most cases ’1’ should be used. 

• Iterations [integer]. This parameter defines number of additional iterations to improve accuracy and stability of the solvers. Usually no iterations are required. 

• InitialIterations [integer]. This parameter defines number of additional iterations to improve accuracy of the initial field. Usually no iterations are required. 

• Damping [float]. This value could be between 0 and 0.5. Usually we do not need any damping and it should be ’0’. 

• ThreadsNumber [integer]. The parameter defines how many threads will be used. Usually it should be equal to the number of cores in your computer, but check the efficiency of parallelism experimentally. 

## 5.4 Wakefield Calculation

The local folder should contain three files: 

• geometry file, 

• command file input.txt, 

• command file run.bat, which uses ECHO3D.exe or command file run_GUI.bat, which uses ECHO3D_GUI.exe. 

The geometry itself as a collection of STL files should be placed in folder Geometry. 

The calculations starts by execution of run.bat. During the simulation the progress is shown. The script starts the programms in the following order: 

• Mesher.exe creates directory Mesh and subdirectories with parts of the geometry meshed, 

• InitField.exe creates directories Bunch and Fields and places their the corresponding files, 

• ECHO3D.exe creates directory Results, makes the wakefield calculation and saves the results, IndirectIntegration.exe calculates wake potential taking into account field propagation in the outgoing waveguide. 

## 5.5 Output files

After execution of run.bat the folder Results is created. It contains file Wake3Dindirect.bin in binary format which should be post-processed with the matlab scripts from directory PostProcessor3D. 

## 5.6 Postprocessing

The folder PostProcessor3D contains several scripts. Their usage is clarified in the examples. 

## 5.7 Examples

The example manual can be found in directory Docs. 

## 6. ECHO1D: Anisotropic Waveguides

## 6.1 Introduction

Code ECHO1D calculates in frequency domain the electromagnetic fields generated by an electron bunch passing through an anisotropic transversally non-homogeneous vacuum chamber of round or rectangular cross-section with translational symmetry in the beam direction [5]. 

![](images/186a918d71f75d4f0ee1ff2a9044174bff79978b2bc7f71b4c6c5fa8e03593f7.jpg)



Figure 6.1: Examples of "round" and "rectangular" geometry.


We consider a point-charge q moving with constant velocity v through a structure with round or rectangular cross-section. In the following we call the structure "round" if it is axially symmetric. If the structure has a constant width between two perfectly conducting planes and has rectangular cross-sections then we call such structure "rectangular". Fig. 6.1 shows examples of round and rectangular structures. In the following we consider only an anisotropic materials with diagonal material permittivity and permeability tensors, where the optical axes coincide with coordinate ones. Hence their diagonals are given by complex vectors $\vec { \varepsilon } , \vec { \mu }$ 

We assume that the charge is moving along a straight line parallel to the longitudinal axis of the system, and we neglect the influence of the wakefields on the charge motion. For round structures we will use cylindrical coordinates $r , \varphi , z .$ The charge density in the frequency domain can be 

expanded in Fourier series 

$$
\rho (r, \varphi , z, k) = e ^ {- i k z / \beta} \sum_ {m = 0} ^ {\infty} \rho_ {m} (r) \cos (m (\varphi - \varphi_ {0})), \quad \rho_ {m} (r) = \frac {q \delta (r - r _ {0})}{\pi v r _ {0} (1 + \delta_ {m 0})},\tag{6.1}
$$

where $r _ { 0 } , \varphi _ { 0 }$ are coordinates of the point charge $q , \beta = \nu / c , \mathfrak { c }$ c is velocity of light in vacuum, and $\delta _ { m 0 } = 1$ if $m = 1$ , 0 otherwise. 

From the linearity of Maxwell’s equations the components of the electromagnetic field can be represented by infinite sums: 

$$
\begin{array}{l} \left( \begin{array}{c} H _ {\varphi} (r, \varphi , z, k) \\ E _ {r} (r, \varphi , z, k) \\ E _ {z} (r, \varphi , z, k) \end{array} \right) = e ^ {- i k z / \beta} \sum_ {m = 0} ^ {\infty} \left( \begin{array}{c} H _ {\varphi , m} (r, k) \\ E _ {r, m} (r, k) \\ E _ {z, m} (r, k) \end{array} \right) \sin (m \varphi), \\ \left( \begin{array}{c} E _ {\varphi} (r, \varphi , z, k) \\ H _ {r} (r, \varphi , z, k) \\ H _ {z} (r, \varphi , z, k) \end{array} \right) = e ^ {- i k z / \beta} \sum_ {m = 0} ^ {\infty} \left( \begin{array}{c} E _ {\varphi , m} (r, k) \\ H _ {r, m} (r, k) \\ H _ {z, m} (r, k) \end{array} \right) \cos (m \varphi). \end{array}\tag{6.2}
$$

The electric displacement $\vec { D }$ and the magnetic induction $\vec { B }$ are defined using complex permittivity and permeability diagonal tensors 

$$
\vec {D} = \left( \begin{array}{c c c} \varepsilon_ {r} (r, k) & 0 & 0 \\ 0 & \varepsilon_ {\varphi} (r, k) & 0 \\ 0 & 0 & \varepsilon_ {z} (r, k) \end{array} \right) \vec {E}, \quad \vec {B} = \left( \begin{array}{c c c} \mu_ {r} (r, k) & 0 & 0 \\ 0 & \mu_ {\varphi} (r, k) & 0 \\ 0 & 0 & \mu_ {z} (r, k) \end{array} \right) \vec {H}.
$$

We do not have to assume any particular frequency dependence. In order to include conductivity and other losses in our code ECHO1D we use the following expressions (here we consider as example r-component): 

$$
\varepsilon_ {r} (r, k) = \varepsilon_ {0} \hat {\varepsilon} _ {r} (r, k) + i \frac {\kappa_ {r} (r)}{\omega (1 + i \omega \tau_ {r} (r))}, \quad \mu_ {r} (r, k) = \mu_ {0} \hat {\mu} _ {r} (r, k), \quad \omega = k c,
$$

where $\varepsilon _ { 0 } , \mu _ { 0 }$ are permettivity and permeability of vacuum, and the loss can be introduced with the help of dielectric loss tangent $\begin{array} { r } { \delta _ { r } ^ { \varepsilon } = \frac { 3 \hat { \varepsilon } _ { r } } { \mathcal { R } \hat { \varepsilon } _ { r } } } \end{array}$ , magnetic loss tangent $\begin{array} { r } { \delta _ { r } ^ { \mu } = \frac { \Im \hat { \mu _ { r } } } { \Re \hat { \mu _ { r } } } } \end{array}$ or/and with $\mathbf { A C }$ conductivity following the Drude model [2], where $\kappa _ { r }$ is the DC conductivity of the material and $\tau _ { r }$ its relaxation time. We use similar expressions for $\varphi \mathrm { - }$ and $z -$ components of the permittivity and the permeability tensors. 

For each mode number m we can write an independent system of equations 

$$
\begin{array}{l} \frac {m}{r} H _ {z, m} + i \frac {k}{\beta} H _ {\varphi , m} = i \omega \varepsilon_ {r} E _ {r, m}, \\ - i \frac {k}{\beta} H _ {r, m} - \frac {\partial}{\partial r} H _ {z, m} = i \omega \varepsilon_ {\varphi} E _ {\varphi , m}, \\ \frac {1}{r} \frac {\partial}{\partial r} (r H _ {\varphi , m}) - \frac {m}{r} H _ {r, m} = i \omega \varepsilon_ {z} E _ {z, m} + v \rho_ {m}, \\ - \frac {m}{r} E _ {z, m} + i \frac {k}{\beta} E _ {\varphi , m} = - i \omega \mu_ {r} H _ {r, m}, \\ - i \frac {k}{\beta} E _ {r, m} - \frac {\partial}{\partial r} E _ {z, m} = - i \omega \mu_ {\varphi} H _ {\varphi , m}, \\ \frac {1}{r} \frac {\partial}{\partial r} (r E _ {\varphi , m}) + \frac {m}{r} E _ {r, m} = - i \omega \mu_ {z} H _ {z, m}, \\ \frac {1}{r} \frac {\partial}{\partial r} (r H _ {r, m} \mu_ {r}) - \frac {m}{r} H _ {\varphi , m} \mu_ {\varphi} - i k H _ {z, m} \mu_ {z} = 0, \\ \frac {1}{r} \frac {\partial}{\partial r} (r E _ {r, m} \varepsilon_ {r}) + \frac {m}{r} E _ {\varphi , m} \varepsilon_ {\varphi} - i k E _ {z, m} \varepsilon_ {z} = \rho_ {m}. \end{array}\tag{6.3}
$$

We have reduced the initial three-dimensional problem to an infinite set of independent dimensional problems, Eqs. (6.3), for the Fourier componets of the field. 

In rectangular case we choose a coordinate system with y in the vertical and x in the horizontal directions; the z coordinate is directed along the beam direction. The structures considered in this paper have constant width 2w in x-direction between two perfectly conducting side walls. 

The charge density can be expanded in Fourier series 

$$
\rho (x, y, z, k) = \frac {e ^ {- i k z / \beta}}{w} \sum_ {m = 1} ^ {\infty} \rho_ {m} (y) \sin (k _ {x, m} x _ {0}) \sin (k _ {x, m} x), \quad k _ {x, m} = \frac {\pi m}{2 w}, \quad \rho_ {m} (y) = \frac {q \delta (y - y _ {0})}{v},
$$

where $x _ { 0 } , y _ { 0 }$ are coordinates of the point charge. Again it follows from the linearity of Maxwell’s equations that the components of electromagnetic field can be represented by infinite sums: 

$$
\begin{array}{l} \left( \begin{array}{c} H _ {x} (x, y, z, k) \\ E _ {y} (x, y, z, k) \\ E _ {z} (x, y, z, k) \end{array} \right) = \frac {e ^ {- i k z / \beta}}{w} \sum_ {m = 1} ^ {\infty} \left( \begin{array}{c} H _ {x, m} (y, k) \\ E _ {y, m} (y, k) \\ E _ {z, m} (y, k) \end{array} \right) \sin (k _ {x, m} x), \\ \left( \begin{array}{c} E _ {x} (x, y, z, k) \\ H _ {y} (x, y, z, k) \\ H _ {z} (x, y, z, k) \end{array} \right) = \frac {e ^ {- i k z / \beta}}{w} \sum_ {m = 1} ^ {\infty} \left( \begin{array}{c} E _ {x, m} (y, k) \\ H _ {y, m} (y, k) \\ H _ {z, m} (y, k) \end{array} \right) \cos (k _ {x, m} x). \end{array}
$$

For each mode number m we can write an independent system of equations 

$$
\begin{array}{l} - k _ {x, m} H _ {z, m} + i \frac {k}{\beta} H _ {x, m} = i \omega \varepsilon_ {y} E _ {y, m}, \\ - i \frac {k}{\beta} H _ {y, m} - \frac {\partial}{\partial y} H _ {z, m} = i \omega \varepsilon_ {x} E _ {x, m}, \\ \frac {\partial}{\partial y} H _ {x, m} + k _ {x, m} H _ {y, m} = i \omega \varepsilon_ {z} E _ {z, m} + v \rho_ {m}, \\ k _ {x, m} E _ {z, m} + i \frac {k}{\beta} E _ {x, m} = - i \omega \mu_ {y} H _ {y, m}, \\ - i \frac {k}{\beta} E _ {y, m} - \frac {\partial}{\partial y} E _ {z, m} = - i \omega \mu_ {x} H _ {x, m}, \\ \frac {\partial}{\partial y} (E _ {x, m}) - k _ {x, m} E _ {y, m} = - i \omega \mu_ {z} H _ {z, m}, \\ \frac {\partial}{\partial y} (H _ {y, m} \mu_ {y}) + k _ {x, m} H _ {x, m} \mu_ {x} - i k H _ {z, m} \mu_ {z} = 0, \\ \frac {\partial}{\partial y} (E _ {y, m} \varepsilon_ {y}) - k _ {x, m} E _ {x, m} \varepsilon_ {x} - i k E _ {z, m} \varepsilon_ {z} = \rho_ {m}. \end{array}\tag{6.4}
$$

We are interested in coupling impedances as defined in [1, 3]. For round pipe the coupling impedance can be written as 

$$
\begin{array}{l} Z _ {\parallel} (r _ {0}, \varphi_ {0}, r, \varphi , k, \gamma) = \sum_ {m = 0} ^ {\infty} Z _ {m} (k, \gamma) I _ {m} \left(\frac {k r _ {0}}{\gamma \beta}\right) I _ {m} \left(\frac {k r}{\gamma \beta}\right) \cos (m (\varphi - \varphi_ {0})) + Z _ {s c} (r _ {0}, \varphi_ {0}, r, \varphi , k, \gamma), \\ Z _ {s c} (r _ {0}, \varphi_ {0}, r, \varphi , k, \gamma) = - \frac {k Z _ {0}}{2 \pi (\gamma^ {2} - 1)} K _ {0} \left(\frac {k \sqrt {r _ {0} ^ {2} + r ^ {2} - 2 r _ {0} r c o s (\varphi - \varphi_ {0})}}{\gamma \beta}\right), \end{array} \tag {6.5}
$$

where $\gamma$ is the relative relativistic energy and we have written explicitly the space charge contribution $Z _ { s c }$ 

For a rectangular pipe the impedance reads 

$$
\begin{array}{c} Z _ {\parallel} (x _ {0}, y _ {0}, x, y, k) = \frac {1}{w} \sum_ {m = 1} ^ {\infty} Z _ {m} (y _ {0}, y, k, \gamma) \sin (k _ {x, m} x _ {0}) \sin (k _ {x, m} x) + Z _ {s c} (x _ {0}, y _ {0}, x, y, k, \gamma), \\ Z _ {s c} (x _ {0}, y _ {0}, x, y, k, \gamma) = - \frac {k Z _ {0}}{2 \pi (\gamma^ {2} - 1)} K _ {0} \left(\frac {k \sqrt {(x - x _ {0}) ^ {2} + (y - y _ {0}) ^ {2}}}{\gamma \beta}\right), \end{array}\tag{6.6}
$$

where 

$$
\begin{array}{c} Z _ {m} (y _ {0}, y, k, \gamma) = [ Z _ {m} ^ {c c} (k, \gamma) \cosh (k _ {y, m} y _ {0}) + Z _ {m} ^ {s c} (k, \gamma) \sinh (k _ {y, m} y _ {0}) ] \cosh (k _ {y, m} y) \\ + [ Z _ {m} ^ {c s} (k, \gamma) \cosh (k _ {y, m} y _ {0}) + Z _ {m} ^ {s s} (k, \gamma) \sinh (k _ {y, m} y _ {0}) ] \sinh (k _ {y, m} y), \\ k _ {y, m} = \sqrt {k _ {x , m} ^ {2} + \frac {k ^ {2}}{\gamma^ {2} \beta^ {2}}}. \end{array}
$$

In Eqs.(6.5, 6.6) the infinite sum defines a so-called wall impedance. The longitudinal and the transverse impedances are connected by Panofsky-Wentzel theorem (see [3] for a detailed discussion): 

$$
\vec {Z} _ {\perp} = \frac {\beta}{k} \nabla Z _ {\parallel},\tag{6.7}
$$

where the gradient is taken on coordinates of the witness particle. 

The wake field effect in time domain is described by a longitudinal wake function which can be obtained by the Fourier transform of the longitudinal impedance 

$$
w _ {| |} (s) = \frac {c}{2 \pi} \int_ {- \infty} ^ {\infty} Z _ {| |} (k) e ^ {i k s / \beta} d k,
$$

where s is the distance between the source and the test particles [1]. 

## 6.2 Installation

The program ECHO1D can be downloaded as archive ECHO1D.zip from https://www.echo4d. de. Extract the archive keeping the stricture of folders and files. 

The archive contains the following folders. 

1. Docs. It contains this manual. 

2. Codes. It contains executables ECHO1D.exe and ECHO2D_GUI.exe. 

3. Examples. It contains several examples. 

4. MatLib4ECHO. It contains Matlab functions for postprocessing. 

5. PostProcessor1D. It contains Matlab scripts for postprocessing. 

## 6.3 Input files

The program ECHO1D requires two input files: 

• a file with geometry description in ASCII format; it can have an arbitrary name, 

• a file with parameters of the simulation in ASCII format; it has a fixed name input_in.txt. 

## 6.3.1 Geometry description

The geometry file describes the layered structure shown in Fig. 6.2. It is a text file with arbitrary name. In the examples considered below the geometry files have names with pattern ExampleXX.txt, where XX is the example number. 

The geometry file has the following format. 

![](images/eae825ae0a618ffdcf9d7b2581f7cd4eb65a2bfe0523d4794843dc30697c6b16.jpg)



Figure 6.2: Examples of "round" and "rectangular" layered geometry.


% N — Number of layers
N
% boundaries $a_{0}$ $a_{1}$ ... $a_{N-1}$ $a_{N}$ % Re(EpsR[i]) Im(EpsR[i]) Re(EpsFi[i]) Im(EpsFI[i]) Re(EpsZ[i]) Im(EpsZ[i]), i=1,N $\Re\hat{\varepsilon}_{r,1}$ $\Im\hat{\varepsilon}_{r,1}$ $\Re\hat{\varepsilon}_{\varphi,1}$ $\Im\hat{\varepsilon}_{\varphi,1}$ $\Re\hat{\varepsilon}_{z,1}$ $\Im\hat{\varepsilon}_{z,1}$ $\Re\hat{\varepsilon}_{r,2}$ $\Im\hat{\varepsilon}_{r,2}$ $\Re\hat{\varepsilon}_{\varphi,2}$ $\Im\hat{\varepsilon}_{\varphi,2}$ $\Re\hat{\varepsilon}_{z,2}$ $\Im\hat{\varepsilon}_{z,2}$ ... $\Re\hat{\varepsilon}_{r,N}$ $\Im\hat{\varepsilon}_{r,N}$ $\Re\hat{\varepsilon}_{\varphi,N}$ $\Im\hat{\varepsilon}_{\varphi,N}$ $\Re\hat{\varepsilon}_{z,N}$ $\Im\hat{\varepsilon}_{z,N}$ % Re(MueR[i]) Im(MueR[i]) Re(MueFi[i]) Im(MueFI[i]) Re(MueZ[i]) Im(MueZ[i]), i=1,N $\Re\hat{\mu}_{r,1}$ $\Im\hat{\mu}_{r,1}$ $\Re\hat{\mu}_{\varphi,1}$ $\Im\hat{\mu}_{\varphi,1}$ $\Re\hat{\mu}_{z,1}$ $\Im\hat{\mu}_{z,1}$ $\Re\hat{\mu}_{r,2}$ $\Im\hat{\mu}_{r,2}$ $\Re\hat{\mu}_{\varphi,2}$ $\Im\hat{\mu}_{\varphi,2}$ $\Re\hat{\mu}_{z,2}$ $\Im\hat{\mu}_{z,2}$ ... $\Re\hat{\mu}_{r,N}$ $\Im\hat{\mu}_{r,N}$ $\Re\hat{\mu}_{\varphi,N}$ $\Im\hat{\mu}_{\varphi,N}$ $\Re\hat{\mu}_{z,N}$ $\Im\hat{\mu}_{z,N}$ % Conductivity[i], Relaxation Time[i], i=1,N $\kappa_{1}$ $\tau_{1}$ $\kappa_{2}$ $\tau_{2}$ ... $\kappa_{N}$ $\tau_{N}$ 

In this listing the strings which begin with % are comments. For rectangular geometry the format is the same with replacing $r  y , \varphi  x$ 

## 6.3.2 Parameters of simulation

The parameters of simulation are listed in input command file with fixed name input_in.txt. This file has a following format. 

```erlang
%%%%%%%%%% geometry %%%%%%%%%Geometry_File = ExampleXX.txt
Boundary_Condition = Open/PEC
Geometry_Width = W

%%%%%%%% % beam % % % % % % % % % % % % % % % % % % % % Gamma = γ

%%%% % % % % % % % % Model % % % % % % % % % % % % % % % Method = FM/FD/Mix 
```

Wavenumbers = $k_{min}$ $k_{max}$ $\Delta k$ 

Modes = $m_{0}$ $m_{1}$ ... $m_{N_{m}}$ 

Steps_on_Wavelength = $N_{\lambda}$ 

%%%%%%%%%%%%%% output %%%%%%%%%%%%%%%%%%%% 

The parameters in this command file are: 

• Geometry_File [string]. It defines the name of file with the geometry description. 

• Boundary_Condition [string]. It defines the boundary condition at $a _ { N }$ (see Fig. 6.2). The boundary condition could be ’PEC’ or ’Open’. ’PEC’ means perfectly electrically conducting material. ’Open’ can be used if the last material with parameters $\vec { \varepsilon } _ { N } , \vec { \mu } _ { N }$ is infinite and has uniaxial anisotropy: $\varepsilon _ { r , N } = \varepsilon _ { \varphi , N } , \mu _ { r , N } = \mu _ { \varphi , N } $ 

• Geometry_Width [float/m]. It could be $\mathbf { \overrightarrow { \mathbf { \nabla } } } 0 \mathbf { \overrightarrow { \mathbf { \Gamma } } }$ or a positive number $W > 0 . \quad \ ' 0 \ '$ defines rotationally symmetric geometry. A positive W defines in meters the width of the rectangular structure in x direction. 

• Gamma [float/m]. It defines the relative energy $\begin{array} { r } { \gamma = \frac { E } { m c ^ { 2 } } } \end{array}$ of the charged particle. 

• Method [string]. It could be ’FM’, ’FD’ or ’Mix’. ’FM’ defines the field matching method and can be used if the all materials have the uniaxial anisotropy: $\varepsilon _ { r , i } = \varepsilon _ { \varphi , i } , \mu _ { r , i } = \mu _ { \varphi , i } , i =$ $1 , . . , N . \ \mathrm { ^ { \circ } F D ^ { \circ } }$ defines finite-difference method and can be used for full anisotropy. ’Mix defines a mixed method which should be used if the anisotropic layers are thin. 

• Steps_on_Wavelength [integer]. It defines the number of mesh lines $N _ { \lambda }$ on wavelength in vacuum. This parameter has no impact on field matching method (Method=FM). 

$\mathbf { \nabla } \cdot \mathbf { \nabla } \mathbf { M } \mathbf { o } \mathbf { d e s } = m _ { 0 } \mathbf { \nabla } m _ { 1 } \dotsm m _ { N _ { m } }$ [integer list]. It defines the modes which are calculated. 

• Wavenumbers $: = k _ { m i n } \ : k _ { m a x } \ : \Delta k$ [float list]. The impedance is calculated from $k _ { m i n }$ to $k _ { m a x }$ with step ∆k. The units are 1/meter. 

## 6.4 Impedance Calculation

The local folder should contain three files: 

• geometry file, 

• command file input_in.txt, 

• command file run.bat, which starts ECHO1D.exe. 

The calculations starts by execution of run.bat. During the simulation the progress in percents is shown. All modes are calculated in parallel. 

## 6.5 Output files

After execution of ECHO1D.exe the folder will contain $N _ { m }$ files with modal impedances. They have name pattern Impedance_MXXX.txt, where XXX is the mode number $m _ { i }$ . Each file is text file with four columns. The contents of the files is different for round and rectangular geometry 

For round geometry each file contains "longitudinal" and "transverse wakes" for each mode. 

% ECHO1D output 

$$
1. 0 0 0 0 0 0 0 \mathrm{e} + 0 0 2. 6 1 1 2 0 0 7 \mathrm{e} + 1 1 5. 9 5 3 8 0 4 1 \mathrm{e} + 1 2 1. 3 0 5 6 0 1 0 \mathrm{e} + 0 5 2. 9 7 6 9 0 3 6 \mathrm{e} + 0 6
$$

Here $Z l o n g = Z _ { m } ( k , \gamma )$ from Eq.(6.5), and $\begin{array} { r } { Z t r a n s = \frac { Z _ { m } k } { 2 \gamma ^ { 2 } \beta } } \end{array}$ is an auxiliary scaled function for nonrelativistic case. 

For rectangular geometry each file contains $Z _ { c c }$ and $Z _ { s s }$ modal impedances from Eq.(??). 

## 6.6 Postprocessing

% ECHO1D output 

% k[m^−1] Re(Zcc)[Omm/m] Im(Zcc)[Omm/m] 

% Re(Zss)[Omm/m] Im(Zss)[Omm/m] 

1.0000000e+00 3.5376930e−03 7.7756244e−02 2.1169888e−02 3.1981001e−01 

## 6.6 Postprocessing

The folder PostProcessor1D contains two subfolders: 

• round, 

• flat. 

## 6.6.1 Impedances

For round structure the longitudinal wall impedance of beam near the axis can be approximated as 

$$
Z _ {\parallel} ^ {w a l l} (r _ {0}, \varphi_ {0}, r, \varphi , k, \gamma) \approx Z _ {l o n g} (k, \gamma) = Z _ {0} (k, \gamma).\tag{6.8}
$$

The transverse wall impedance near the axis can be approximated as 

$$
Z _ {r} ^ {w a l l} (r _ {0}, \varphi_ {0}, r, \varphi , k, \gamma) \approx Z _ {d i p} (k, \gamma) r _ {0} c o s (\varphi_ {0} - \varphi) + Z _ {q u a d} (k, \gamma) r,\tag{6.9}
$$

$$
Z _ {\varphi} ^ {w a l l} (r _ {0}, \varphi_ {0}, r, \varphi , k, \gamma) \approx Z _ {d i p} (k, \gamma) r _ {0} s i n (\varphi_ {0} - \varphi),\tag{6.10}
$$

where 

$$
Z _ {d i p} (k, \gamma) = Z _ {1} (k, \gamma) \frac {k}{4 \beta \gamma^ {2}}, \qquad Z _ {q u a d} (k, \gamma) = Z _ {0} (k, \gamma) \frac {k}{2 \beta \gamma^ {2}}.\tag{6.11}
$$

The matlab script Impedance_round.m plots graphically the terms $Z _ { l o n g } ( k , \gamma ) , Z _ { d i p } ( k , \gamma )$ and $Z _ { q u a d } ( k , \gamma )$ . Additionally it saves these terms in file ImpedanceLQD.txt. 

For rectangular structure the longitudinal wall impedance of beam near the axis can be approximated as 

$$
Z _ {\parallel} ^ {w a l l} (x _ {0}, y _ {0}, x, y, k, \gamma) \approx Z _ {l o n g} (k, \gamma) = \frac {1}{w} \sum_ {m = 1} ^ {\infty} Z _ {2 m - 1} ^ {c c} (k, \gamma).\tag{6.12}
$$

The transverse wall impedance near the axis can be approximated as 

$$
Z _ {y} ^ {w a l l} (x _ {0}, y _ {0}, x, y, k, \gamma) \approx Z _ {d i p} ^ {y} (k, \gamma) y _ {0} + Z _ {q u a d} ^ {y} (k, \gamma) y,\tag{6.13}
$$

$$
Z _ {x} ^ {w a l l} (x _ {0}, y _ {0}, x, y, k, \gamma) \approx Z _ {d i p} ^ {x} (k, \gamma) x _ {0} - Z _ {q u a d} ^ {x} (k, \gamma) x,\tag{6.14}
$$

where 

$$
Z _ {d i p} ^ {y} (k, \gamma) = \frac {\beta}{k w} \sum_ {m = 1} ^ {\infty} k _ {y, 2 m - 1} ^ {2} Z _ {2 m - 1} ^ {c c} (k, \gamma),\tag{6.15}
$$

$$
Z _ {q u a d} ^ {y} (k, \gamma) = \frac {\beta}{k w} \sum_ {m = 1} ^ {\infty} k _ {y, 2 m - 1} ^ {2} Z _ {2 m - 1} ^ {s s} (k, \gamma),\tag{6.16}
$$

$$
Z _ {d i p} ^ {x} (k, \gamma) = \frac {\beta}{k w} \sum_ {m = 1} ^ {\infty} k _ {x, 2 m} ^ {2} Z _ {2 m} ^ {c c} (k, \gamma),\tag{6.17}
$$

$$
Z _ {q u a d} ^ {x} (k, \gamma) = \frac {\beta}{k w} \sum_ {m = 1} ^ {\infty} k _ {x, 2 m - 1} ^ {2} Z _ {2 m - 1} ^ {s s} (k, \gamma).\tag{6.18}
$$

The matlab script Impedance_flat.m plots graphically the terms $Z _ { l o n g } ( k , \gamma ) , Z _ { d i p } ^ { y } ( k , \gamma )$ and $Z _ { q u a d } ^ { y } ( k , \gamma )$ . Additionally it saves these terms in file ImpedanceLQD.txt. 

## 6.6.2 Wakes

The matlab scripts Wake_round.m and Wake_flat.m plot graphically the corresponding wake potentials for a Gaussian bunch with rms width defined at the beginning of the scripts by line sigma=.... The wakes are saved in file wakeLQD.txt. 

## 6.7 Examples

In this section we consider several examples included in the archive at the directory Examples. 

## 6.7.1 Example 1: Round dielectric pipe

The first example can be found in directory Examples/ N1_Round_Dielectric. We consider a dielectric pipe with interrior radius $a _ { 0 } { = } 5 \mathrm { m m } .$ , exterior radius $a _ { 1 } { = } 1 0 \mathrm { m m }$ with relative permeability $\hat { \boldsymbol { \varepsilon } } = 1 1$ . The pipe is closed by perfectly conducting metal. The geometry is shown in Fig. 6.3. 

![](images/58ac5abba8f1ffc11e3000427994ea71f104093ddfbd396370c4414a351f15b4.jpg)



Figure 6.3: The geometry of round dielectric pipe inside of perfectly conducting pipe.


![](images/4ebc70122145a2ec6dbb8222ce8be122e5fc4d34a39b1051a98c291215fbc6ff.jpg)



Figure 6.4: Impedances of the round dielectric pipe. The real part is shown in blue. The imaginary part is presented by the green curve.


In order to model the perfectly conducting material we set Boundary_ $C o n d i t i o n = P E C$ in the command file input_in.txt. The geometry is isotropic and we set $M e t h o d = F M$ to choose the fastest method: field matching. For beam near to the axis we calculate only two lowest modes of the azimuthal expansion: $M o d e s = O I$ . Without losses the real part of impedance is a sum of deltafunctions. It can be reconstructed from imaginary part of the impedance. However we are interested here only in short range wakes and use a simpler approach: we introduce a small conductivity 1 S/m in the last row of geometry file Example01.txt. The obtained impedances can be seen with the matlab script N1_Round_Dielectric/ PostProcessor1D/ round/ Impedance_round.m. They are shown in Fig. 6.4. 

![](images/746506b5c7b3f66051c9d8e2717c9ef027d468daf9e82164446d11676887121b.jpg)



Figure 6.5: Wake potentials of the Gaussian bunch with rms width 0.25 mm in the round dielectric pipe.


![](images/c6ee3940cda3e12b5be0760c40f9173ed9780b23975e878ccc55fc9e742239df.jpg)



Figure 6.6: Windows GUI interface of ECHO2D code shows the $E _ { z }$ component of the field in time-domain in the round dielectric pipe.


We are looking for short range longitudinal and transverse wake potentials for a Gaussian bunch with rms width 0.25mm. They can be obtained with matlab script N1_Round_Dielectric/ Postprocessor1D/ round/ Wake_round.m and are shown in Fig. 6.5. 

The results are cross-checked with ECHO2D. The simulations are done for 1 meters and 1.1 meters and subtracted to obtain the “steady-state” wake. The setup to run code ECHO2D can be found in folders ECHO2D and PostProcessor2D. The instructions how to use code ECHO2D are given in corresponding section of this manual. Fig. 6.6 presents the GUI interface during time-domain calculations with ECHO2D. 

![](images/8544c5231204ab66b9416dcc815e15aa6a322649c7834f3200b5ca63c07a047d.jpg)


![](images/95384ab4e0f7526c8a0ec1052e01fc6c4339b3a7bef52c7aed2dc2a84c7ee425.jpg)



Figure 6.7: Comparison the wake potentials of the round dielectric pipe obtained by ECHO1D (blue curves) with the ones obtained by ECHO2D (green curves)


The comparison of the results from ECHO1D with ECHO2D can be seen by running the script Compare_2D_vs_1D.m in Matlab. The result is shown in Fig. 6.7. 

## 6.7.2 Example 2: Flat dielectric pipe

The second example can be found in directory Examples/ N2_Flat_Dielectric. We consider a rectangular perfectly conducting pipe of width 160 mm and half hight $a _ { 1 } { = } 1 0 \mathrm { m m }$ . The pipe has a dielectric layer vertically from $a _ { 0 } { = } 5 \mathrm { m m }$ to $a _ { 1 } { = } 1 0 \mathrm { m m }$ with relative permeability $\hat { \boldsymbol { \varepsilon } } = 1 1$ . The geometry is shown in Fig. 6.8. 

![](images/31b2bca4c3de312f61bf65a3e4f8cd6fec00d700733b140e348114252f29aabc.jpg)



Figure 6.8: The geometry of flat dielectric pipe inside of perfectly conducting pipe.


In order to model the perfectly conducting material we set Boundary_ $C o n d i t i o n = P E C$ in the command file input_in.txt. The geometry is isotropic and we set $M e t h o d = F M$ to choose the fastest method: field matching. For beam near to the axis we calculate only odd modes: $M o d e s = I$ $3 5 7 9 I I$ 13 15 17 19 21 23 25 27 29 31 33 35 37 39 41 43 45 47 49 51 53 55 57 59. Again we introduce a small conductivity 1 S/m in the last row of geometry file Example02.txt. The obtained impedances can be seen with the matlab script PostProcessing1D/ flat/ Impedance_flat.m. They are shown in Fig. 6.9. 

We are looking for short range longitudinal and transverse wake potentials for a Gaussian bunch with rms width 0.25mm. They can be obtained with matlab script PostProcessing1D/ flat/ Wake_flat.m and are shown in Fig. 6.10. 

![](images/d1e89f6016e7f723bb4466c50df5ef4db01ae9368b843f371a76fe0c444cf841.jpg)



Figure 6.9: Impedances of the flat dielectric pipe. The real part is shown in blue. The imaginary part is presented by the green curve.


The results are cross-checked with ECHO2D. The simulations are done for 1 meters and 1.1 meters and subtracted to obtain “steady-state” wake. The setup to run ECHO2D code can be found in folders ECHO2D and PostProcessor2D. The instructions how to use ECHO2D code are given in corresponding section of this manual. 

The comparison of the results from ECHO1D with ECHO2D can be seen by running the script Compare_2D_vs_1D.m in Matlab. The result is shown in Fig. 6.11. 

## 6.7.3 Example 3: Flat anisotropic pipe

The third example can be found in directory Examples/ N3_Flat_Anisotropic_Argonne. We consider a rectangular perfectly conducting pipe of width 11 mm and half hight $a _ { 1 } { = } 2 . 3 9 \mathrm { m m }$ . The pipe has an anisotropic dielectric layer vertically from $a _ { 0 } { = } 1 . 5 \mathrm { m m }$ to $a _ { 1 } = 2$ .39mm with relative permeabilities $\hat { \varepsilon } _ { y } = 1 1 . 5 , \hat { \varepsilon } _ { x } = \hat { \varepsilon } _ { z } = 9 . 4$ . The geometry is shown in Fig. 6.12. 

In order to model the perfectly conducting material we set Boundary_Condition = PEC in the command file input_in.txt. The geometry is anisotropic and we set Method = Mix to choose the finite difference method only in the anisotropic layer. For beam near to the axis we calculate only odd modes: $M o d e s = I \ 3 \ 5 \ 7 \ : 9 .$ . Again we introduce a small conductivity 0.05 S/m in the last row of geometry file Example03.txt. The obtained impedances can be seen with the matlab script PostProcessing1D/ flat/ Impedance_flat.m. They are shown in Fig. 6.13. 

We are looking for short range longitudinal and transverse wake potentials for a Gaussian bunch with rms width 1.5mm. They can be obtained with matlab script PostProcessing1D/ flat/ Wake_flat.m and are shown in Fig. 6.14. 

## 6.7.4 Example 4: Round pipe with two layers

The last example can be found in directory Examples/N4_Round_kicker_SLAC. We consider a round pipe. The pipe has two layers: a dielectric layer from $a _ { 0 } = 5$ mm to $a _ { 1 } = 9$ mm with relative permeability $\hat { \boldsymbol { \varepsilon } } = 1 1$ and a ferromagnetic layer from $a _ { 1 } = 9$ mm to $a _ { 2 } { = } { \infty }$ with relative permittivity 

![](images/4829442b858fca1e05414ab5cace1d06bd13e336eced244c0d515b7df893b757.jpg)



Figure 6.10: Wake potentials of the Gaussian bunch with rms width 0.25 mm in the flat dielectric pipe.


µˆ = 10. The geometry is shown in Fig. 6.15. 

In order to model the infinite layer we set Boundary_Condition = Open in the command file input_in.txt. The geometry is isotropic and we set Method = FM to choose the fastest method: field matching. For beam near to the axis we calculate only two modes: Modes = 0 1. Again we introduce a small conductivity 0.1 S/m in the last rows of geometry file Example04.txt. The obtained impedances can be seen with the matlab script PostProcessing1D/ round/ Impedance_round.m. They are shown in Fig. 6.16. 

We are looking for short range longitudinal and transverse wake potentials for a Gaussian bunch with rms width 0.25 mm. They can be obtained with matlab script PostProcessing1D/ round Wake_round.m and are shown in Fig. 6.17. 

The results are cross-checked with ECHO2D. The simulations are done for 1 meters and 1.1 meters and subtracted to obtain the “steady-state” wake. We place perfectly conducting pipe at r = 15 mm. The setup to run code ECHO2D can be found in folders ECHO2D and PostProcessor2D. The instructions how to use ECHO2D code are given in corresponding section of this manual. 

The comparison of the results from ECHO1D with ECHO2D can be seen by running the script Compare_2D_vs_1D.m in Matlab. The result is shown in Fig. 6.18. 

![](images/adb10adfcf6deee4e0233884df23c7df5d2e6ec36256553e1761da51fcca485b.jpg)


![](images/6e29dfaefdb133040588d6e28da8551cf1bafa861d6abf75d5e48a9886333ffe.jpg)


![](images/1e5c9e67ceb31a59c0c9c23cc224c6a5c024a2aab86609d93c42f66c2edc4ebd.jpg)



Figure 6.11: Comparison the wake potentials of the flat dielectric pipe obtained by ECHO1D (blue curves) with the ones obtained by ECHO2D (green curves)


![](images/cd97366354a7351ea35376a9a830081003bb99e866687289d45ad89f43db6768.jpg)



Figure 6.12: The geometry of flat anisotropic dielectric pipe inside of perfectly conducting pipe.


![](images/4c9d25291d7c2b5bd1e3f4a27bfb040d6d5c04f2b00f0a07b47eeb488fcab2bd.jpg)



Figure 6.13: Impedances of the flat anisotropic dielectric pipe. The real part is shown in blue. The imaginary part is presented by the green curve.


![](images/38439bf7e59e8f302b1b39b856c1690b187d77a3abadff3af0fdb725f4cb501a.jpg)



Figure 6.14: Wake potentials of the Gaussian bunch with rms width 1.5 mm in the flat anisotropic dielectric pipe.


![](images/1ec979c939302495151c598bffe57b19f770e5642ba0ce0d076aea6e2a9258ca.jpg)



Figure 6.15: The geometry of round pipe with two layers.


![](images/f42dbd277988bb9c7f550c1af3012cba52c0f358992ad825ff4a7c13306697ba.jpg)


![](images/9bc7f7aeb223fe3d6f322707d83a9e93042832f2c32d7e963558b7adacd24d47.jpg)


![](images/5b07fd113f1dc04ee9aaa8da23ecf8c95c5d9ed08c95d8b5c906b4a4745bf0c0.jpg)



Figure 6.16: Impedances of the round two-layered pipe. The real part is shown in blue. The imaginary part is presented by the green curve.


![](images/a547ca799fc44640dcccd6c6c8a83d30991e8a305fbc8ae5d351a0d05a80d119.jpg)



Figure 6.17: Wake potentials of the Gaussian bunch with rms width 0.25 mm in the two-layered pipe.


![](images/c35766f58196da2c2909961d70aba693ec778906c503ae68401c077e04501dd9.jpg)


![](images/62d5b7cb1319433d7865930eeb2e66ab5717c994b14bf604873bb4c80c4cef03.jpg)



Figure 6.18: Comparison the wake potentials of the two-layered pipe obtained by ECHO1D (blue curves) with the ones obtained by ECHO2D (green curves)


## Bibliography

## Books



[1] A.W. Chao. Physics ofCollective Beam Instabilities in High Energy Accelerators. New York: John Wiley and Sons, 1993 (cited on pages 9, 23, 45, 53, 54). 





[2] J.D. Jackson. Classical Electrodynamics. 3rd edition. John Wiley and Sons, 1998 (cited on page 52). 





[3] N. Mounet. The LHC Transverse Coupled-Bunch Instability. PhD Thesis. EPFL, Lausanne: CERN, 2012 (cited on pages 53, 54). 



## Articles



[4] T. Weiland and I. Zagorodnov. “Maxwell equations in structures with symmetries”. In: Journal ofComputational Physics 180 (2002), page 297 (cited on page 26). 





[5] I. Zagorodnov. “Impedances of anisotropic round and rectangular chambers”. In: Physical Review Accelerators and Beams 21 (2018), page 064601 (cited on page 51). 





[6] I. Zagorodnov, K.L.F. Bane, and G. Stupakov. “Calculation of wakefields in 2D rectangular structures”. In: Physical Review Accelerators and Beams 18 (2015), page 104401 (cited on pages 15, 17, 23, 29). 





[7] I. Zagorodnov, R. Schuhmann, and T. Weiland. “A uniformly stable conformal FDTD-method in Cartesian grids”. In: International Journal ofNumerical Modeling 16.2 (2003), page 127 (cited on page 18). 





[8] I. Zagorodnov, R. Schuhmann, and T. Weiland. “Long-time numerical computation of electromagnetic fields in the vicinity of a relativistic source”. In: Journal ofComputational Physics 191 (2003), pages 525–141 (cited on page 9). 





[9] I. Zagorodnov and T Weiland. “TE/TM field solver for particle beam simulations without numerical Cherenkov radiation”. In: Physical Review Accelerators and Beams 8 (2005), page 042001 (cited on pages 15, 23). 



## Index

Examples Field monitor for flat taper, 53 Flat absorber, 50 Flat anisotropic pipe, 19 Flat dielectric pipe, 55 Flat tapered collimator with resistivity, 53 Resistive pillbox cavity, 37, 49 Round collimator, 28, 35, 49 Round dielectric pipe, 54 Round pipe with two layers, 19 TESLA cavity, 30, 37, 50, 55 Flat dielectric pipe, 18 Round dielectric pipe, 16 