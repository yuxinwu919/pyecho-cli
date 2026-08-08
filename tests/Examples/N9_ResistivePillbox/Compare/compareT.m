clear all; close all;
 w1=load('../ECHO2D/round/wakeT_dipole.dat');
 w2=load('../ECHOz2/wakeT.dat');
 plot(w1(:,1),w1(:,2),w2(2:end,1),w2(2:end,2))

 