%Wlong, Wdipole and Wquad terms near the axis x=y=0;
clear all;close all;

Ncc=8;
dir_in_cc='../../ECHO2D/magn/';
Nss=15;
dir_in_ss='../../ECHO2D/elec/';
dir_out='../../ECHO2D/';

path('../../../../MatLib4ECHO',path);
filename='wakeL_01.txt';
w1=load([dir_in_cc filename]);
hr=w1(1,1);
offset=w1(1,2);
sigma=w1(2,2)*1e3; %in mm
dy=offset*hr;

Wcc=load([dir_in_cc 'Wcc_odd.txt']);
Wss=load([dir_in_ss 'Wss_odd.txt']);
D=Wcc(1,1);
s=Wcc(1,2:end); ns=length(s);
Nm=length(Wcc(2:end,1));
Nm=min([Ncc Nm]);
Nm=min([Ncc Nm]);
f=Wcc(2:Nm+1,1);
WL(1:ns)=0;
WQ(1:ns)=0;
WD(1:ns)=0;
FQ(1:Nm,1:ns)=0;
FD(1:Nm,1:ns)=0;
for i=1:Nm,
        M=f(i);
        WL=WL+Wcc(i+1,2:end);
        FQ(i,:)=M^2*Wcc(i+1,2:end);
        WQ=WQ+FQ(i,:);
        FD(i,:)=M^2*Wss(i+1,2:end);
        WD=WD+FD(i,:);
end;

 subplot(3,2,1);
 mesh(s*1e3,f*1e-3,Wcc(2:Nm+1,2:end)*1e-3); zlabel('W_l_o(k,s)[V/pC]');xlabel('s[mm]');ylabel('k[1/mm]');
 subplot(3,2,3);
 mesh(s*1e3,f*1e-3,FQ*1e-6);zlabel('W_q_u(k,s)[V/pC/mm]');xlabel('s[mm]');ylabel('k[1/mm]');
 subplot(3,2,5);
 mesh(s*1e3,f*1e-3,FD*1e-6);zlabel('W_d_i(k,s)[V/pC/mm]');xlabel('s[mm]');ylabel('k[1/mm]');


h=s(2)-s(1);
WQ=-IntegrTr(h,WQ);
WD=-IntegrTr(h,WD);

s=s;
WL=WL*2/D*1e-3;
WQ=WQ*2/D*1e-6;
WD=WD*2/D*1e-6;

out(1:ns,1:4)=0;
out(:,1)=s*1e3; 
out(:,2)=WL;
out(:,3)=WQ;
out(:,4)=WD;

filename=[dir_out 'WakeLQD.txt'];
save(filename,'out','-ascii');
fileID = fopen(filename,'w');
fprintf(fileID,'%% %15s %16s %16s  %16s \n','s[mm]','Wlong[V/pC]','Wquad[V/pC/mm]','Wdipole[V/pC/mm]');
fprintf(fileID,'%16.7e %16.7e %16.7e  %16.7e \n',out');
fclose(fileID);


error_Wlo_in_procents=Nm*sum(Wcc(Nm+1,2:end).*Wcc(Nm+1,2:end))/sum(sum(Wcc(2:end,2:end).*Wcc(2:end,2:end)))*100,
error_Wqu_in_procents=Nm*sum(FQ(Nm,:).*FQ(Nm,:))/sum(sum(FQ.*FQ))*100,
error_Wdi_in_procents=Nm*sum(FD(Nm,:).*FD(Nm,:))/sum(sum(FD.*FD))*100,

Iz=load([dir_in_cc 'Iz0.txt']); % Iz/c
filename='wakeL_01.txt';
w1=load([dir_in_cc filename]);offset=w1(1,2);sigma=w1(2,2);
bunch(:,1)=Iz(:,1); bunch(:,2)=Iz(:,offset+3)*1e9; 
B=interp1(bunch(:,1),bunch(:,2),s,'linear',0);
[lossL,spreadL]=LossShape([s' B'],[s' WL']) %V/pC
[lossD,spreadD]=LossShape([s' B'],[s' -WD']) %V/pC/mm
[lossQ,spreadQ]=LossShape([s' B'],[s' -WQ']) %V/pC/mm

subplot(3,2,2)
plot(s,WL);ylabel('Wlo[V/pC]');xlabel('s[mm]');
title(['Loss=' num2str(lossL) '[V/pC]']);
subplot(3,2,4)
plot(s,WQ);ylabel('Wqu[V/pC/mm]');xlabel('s[mm]');
title(['KickQ=' num2str(lossQ) '[V/pC/mm]']);
subplot(3,2,6)
plot(s,WD);ylabel('Wdi[V/pC/mm]');xlabel('s[mm]');
title(['KickD=' num2str(lossD) '[V/pC/mm]']);
