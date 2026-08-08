%Wcc assembling
% ECHO options: SymmetryCondition= magn  
clear all;close all;
Nm=8;
dir_in='../../ECHO2D/magn/';
dir_out='../../ECHO2D/magn/';
filename_format='wakeL_%02i.txt';
filename=[dir_in sprintf(filename_format,1)];
w=load(filename);
dy=w(1,1)*w(1,2);
step=w(1,2);
D=w(2,1); 
sigma=w(2,2);
w(1:2,:)=[];

s=w(:,1);ns=length(s);
W(1:Nm+1,1:ns+1)=0;
W(1,2:ns+1)=s;
W(1,1)=D;
WD(1:Nm,1:ns)=0;
for i=1:Nm,
    m=2*i-1;
    f=pi/D*m;
    W(i+1,1)=f;
    filename=[dir_in sprintf(filename_format,m)];
    w=load(filename);
    w(1:2,:)=[];
    W(i+1,2:ns+1)=w(:,2)/cosh(dy*f)^2;
    WD(i,:)=w(:,2);
end;

filename=[dir_out 'Wcc_odd.txt'];
save(filename,'W','-ascii');

subplot(2,1,1)
mesh(W(1,2:end)*1e3,W(2:end,1)*1e-3,WD*1e-3);
title(['Modal wakes W(k_x,s)[V/pC*m] at offset=' num2str(dy*1e3) ' mm  with magnetic BC']);
xlabel('s[mm]');ylabel('k_x[1/mm]');
subplot(2,1,2)
mesh(W(1,2:end)*1e3,W(2:end,1)*1e-3,W(2:end,2:end)*1e-3);
title('1D modal functions W_c_c(k_x,s)[V/pC*m]');
xlabel('s[mm]');ylabel('k_x[1/mm]');


