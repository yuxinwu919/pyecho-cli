clear all; close all;
w1=load('../ECHO2D/round_1/wakeL_monopole.dat');
w2=load('../ECHO2D/round_2/wakeL_monopole.dat');
w3=load('../ECHO2D/round_all/wakeL_monopole.dat');
plot(w1(:,1),w1(:,2)+w2(:,2),w3(:,1),w3(:,2));