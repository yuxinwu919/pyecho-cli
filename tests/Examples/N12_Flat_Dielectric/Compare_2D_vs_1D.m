clear all; hold off;
path('../../MatLib4ECHO',path);
sigma=250e-6; %m 

out=load('./ECHO1D/wakeLQD.txt');
xb=out(:,1);
WL_imp=out(:,2);
WQ_imp=out(:,3);
WD_imp=out(:,4);
yb(:,1)=gauss(xb,sigma);

w10=load('ECHO2D/magn_1m/wakeLQD.txt');rez=w10;
w20=load('ECHO2D/magn_1m10/wakeLQD.txt');
rez(:,2)=(w20(:,2)-w10(:,2))*10;
rez(:,3)=(w20(:,3)-w10(:,3))*10;
rez(:,4)=(w20(:,4)-w10(:,4))*10;

h=(rez(2,1)-rez(1,1))*1e-3;
shift=5*sigma-0.5*h;

subplot(3,1,1);
s_ECHO=rez(:,1)*1e-3-shift; WL_ECHO=rez(:,2)*1e12;
plot(xb,WL_imp*1e-12,s_ECHO,WL_ECHO*1e-12); xlim([-10*sigma 100*sigma]);
xlabel('s[mm]');ylabel('Wlong[V/pC]');
[L S P]=LossShape([xb yb],[xb WL_imp*1e-12]);
title(['Loss=' num2str(L) '[V/pC]']);

subplot(3,1,2);
WQ_ECHO=rez(:,3)*1e15;
plot(xb,WQ_imp*1e-15,s_ECHO,WQ_ECHO*1e-15); xlim([-10*sigma 100*sigma]);
xlabel('s[mm]');ylabel('Wquad[V/pC/mm]');
[L S P]=LossShape([xb yb],[xb WQ_imp*1e-15]);
title(['KickQ=' num2str(L) '[V/pC/mm]']);
subplot(3,1,3);
WD_ECHO=rez(:,4)*1e15;
plot(xb,WD_imp*1e-15,s_ECHO,WD_ECHO*1e-15); xlim([-10*sigma 100*sigma]);
xlabel('s[mm]');ylabel('Wdip[V/pC/mm]');
[L S P]=LossShape([xb yb],[xb WD_imp*1e-15]);
title(['KickD=' num2str(L) '[V/pC/mm]']);



