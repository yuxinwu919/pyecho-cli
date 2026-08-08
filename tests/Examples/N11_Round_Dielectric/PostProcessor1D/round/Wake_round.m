clear all; hold off;
path('../../../../MatLib4ECHO',path);
PhysConsts;
% bunch shape 
gamma=1000; 
sigma=250e-6; %m 
dir_in='../../ECHO1D/';
dir_out=dir_in;

filename_impedance=[dir_in 'ImpedanceLQD.txt'];
beta=sqrt(1-1/gamma^2);
Nsig=10;
dx=0.1;xb(:,1)=[-Nsig:dx:Nsig]*sigma; yb(:,1)=gauss(xb,sigma);
Nadd=200000;
n=length(xb);ds=xb(2)-xb(1);
xb=[xb' [1:Nadd]*ds+xb(n)]';yb=[yb' [1:Nadd]*0]';

 
% wake in V/C/m
Za0=load(filename_impedance);
Za0(1)=Za0(1)*beta;
WL_imp=ZaZb(xb,yb,Za0); 
Za0(:,2)=Za0(:,5);Za0(:,3)=-Za0(:,4); %i*Zt
WQ_imp=-ZaZb(xb,yb,Za0); 
Za0(:,2)=Za0(:,7);Za0(:,3)=-Za0(:,6); %i*Zt
WD_imp=-ZaZb(xb,yb,Za0); 

n=length(xb);out(1:n,1:4)=0;
out(:,1)=xb;
out(:,2)=WL_imp;
out(:,3)=WQ_imp;
out(:,4)=WD_imp;
filename=[dir_out 'wakeLQD.txt'];
save(filename,'out','-ascii');

subplot(3,1,1);
plot(xb,WL_imp*1e-12); xlim([-10*sigma 100*sigma]);
xlabel('s[cm]');ylabel('Wlong[V/pC]');
[L S P]=LossShape([xb yb],[xb WL_imp*1e-12]);
title(['Loss=' num2str(L) '[V/pC]']);

subplot(3,1,2);
plot(xb,WQ_imp*1e-15); xlim([-10*sigma 100*sigma]);
xlabel('s[m]');ylabel('Wquad[V/pC/mm]');
[L S P]=LossShape([xb yb],[xb WQ_imp*1e-15]);
title(['KickQ=' num2str(L) '[V/pC/mm]']);
subplot(3,1,3);
plot(xb,WD_imp*1e-15); xlim([-10*sigma 100*sigma]);
xlabel('s[m]');ylabel('Wdip[V/pC/mm]');
[L S P]=LossShape([xb yb],[xb -WD_imp*1e-15]);
title(['KickD=' num2str(L) '[V/pC/mm]'])

