clear all; hold off;
path('../../MatLib4ECHO',path);

sigma=250e-6; %m 
out=load('./ECHO1D/wakeLQD.txt');
xb=out(:,1);
WL_imp=out(:,2);
WQ_imp=out(:,3);
WD_imp=out(:,4);
yb(:,1)=gauss(xb,sigma);

w10=load('ECHO2D/round_1m/wakeL_monopole.dat');
w20=load('ECHO2D/round_1m10/wakeL_monopole.dat');
rez(1:length(w10(:,1)),1:4)=0;
rez(:,1)=w10(:,1)*10;
rez(:,2)=(w20(:,2)-w10(:,2))*10;
w10=load('ECHO2D/round_1m/wakeT_dipole.dat');
w20=load('ECHO2D/round_1m10/wakeT_dipole.dat');
rez(:,4)=(w20(:,2)-w10(:,2))*10;

subplot(2,1,1);
s_ECHO=rez(:,1)*1e-3; WL_ECHO=rez(:,2)*1e12;
plot(xb,WL_imp*1e-12,s_ECHO,WL_ECHO*1e-12); xlim([-10*sigma 100*sigma]);
xlabel('s[mm]');ylabel('Wlong[V/pC]');
[L S P]=LossShape([xb yb],[xb WL_imp*1e-12]);
title(['Loss=' num2str(L) '[V/pC]']);

subplot(2,1,2);
WD_ECHO=rez(:,4)*1e15*1e-3;
plot(xb,WD_imp*1e-15,s_ECHO,WD_ECHO*1e-15); xlim([-10*sigma 100*sigma]);
xlabel('s[mm]');ylabel('Wdip[V/pC/mm]');
[L S P]=LossShape([xb yb],[xb -WD_imp*1e-15]);
title(['KickD=' num2str(L) '[V/pC/mm]']);
