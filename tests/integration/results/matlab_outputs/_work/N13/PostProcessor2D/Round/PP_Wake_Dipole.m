%Kick Calculation
clear all;close all;
dir='../../ECHO2D/round_2/';
filename='wakeL_01.txt';
path('../../../../MatlabLibrary',path);
w=load([dir filename]);
Iz=load([dir 'Iz0.txt']); % Iz/c
hr=w(1,1);
offset=w(1,2);
sigma=w(2,2);
dy=(offset+0.5)*hr;

W=w(3:end,2)*1e-3/dy^2;
s=w(3:end,1);ns=length(s);

bunch(:,1)=Iz(:,1);
bunch(:,2)=Iz(:,offset+3)*1e9; % -> ro
B=interp1(bunch(:,1),bunch(:,2),s,'linear',0);

out(1:ns,1:2)=0;shift=5*sigma-0.5*(s(2)-s(1));
out(:,1)=(s-shift)*100; out(:,2)=W;
[loss,spread]=LossShape([s B],[s W])
filename=[dir 'wakeL_dipole.dat'];
save(filename,'out','-ascii');

h=s(2)-s(1);
Wt=IntegrTr(h,W)';
out(:,2)=-Wt;
[kick,rms_kick]=LossShape([s B],[s Wt])
filename=[dir 'wakeT_dipole.dat'];
save(filename,'out', '-ascii');
subplot(2,1,1);
plot(s,W);
title('Longitudinal wake');
xlabel('s[m]');ylabel('W_|_|[V/pC/m^2]');
subplot(2,1,2);
plot(s,-Wt);
title('Transverse wake');
xlabel('s[m]');ylabel('W_|_|[V/pC/m]');

