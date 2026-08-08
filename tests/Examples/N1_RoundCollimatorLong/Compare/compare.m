clear all; close all;
w1=load('../ECHOz1/wake.dat');
w2=load('../ECHOz2/wakeL.dat');
w3=load('../ECHO2D/round/wakeL_monopole.dat');
plot(w1(2:end,1),w1(2:end,2),'b',w2(2:end,1),w2(2:end,2),'k',w3(:,1),w3(:,2),'r');
title('Longitudinal wake');
legend('ECHOz1','ECHOz2','ECHO2D','Location','SouthWest');
xlabel('s[cm]');ylabel('W_|_|[V/pC]');