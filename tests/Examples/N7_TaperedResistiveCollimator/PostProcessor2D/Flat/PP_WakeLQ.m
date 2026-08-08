%Wlong and Wquad terms near the axis x=y=0;
clear all;close all;
path('../../../../MatLib4ECHO',path);
Ncc=8;
dir_in='../../ECHO2D/magn/';
dir_out=dir_in;
Wcc=load([dir_in 'Wcc_odd.txt']);
D=Wcc(1,1);
s=Wcc(1,2:end); ns=length(s);
Nm=length(Wcc(2:end,1));
Nm=min([Ncc Nm]);
f=Wcc(2:Nm+1,1);
WL(1:ns)=0;
WQ(1:ns)=0;
FQ(1:Nm,1:ns)=0;
for i=1:Nm,
        M=f(i);
        WL=WL+Wcc(i+1,2:end);
        FQ(i,:)=M^2*Wcc(i+1,2:end);
        WQ=WQ+FQ(i,:);
end;

 subplot(2,2,1);
 mesh(s*1e3,f*1e-3,Wcc(2:Nm+1,2:end)*1e-3); zlabel('W_l_o(k,s)[V/pC]');xlabel('s[mm]');ylabel('k[1/mm]');
 subplot(2,2,3);
 mesh(s*1e3,f*1e-3,FQ*1e-6);zlabel('W_q_u(k,s)[V/pC/mm]');xlabel('s[mm]');ylabel('k[1/mm]');
 

h=s(2)-s(1);
WQ=-IntegrTr(h,WQ);

s=s;
WL=WL*2/D*1e-3;
WQ=WQ*2/D*1e-6;

out(1:ns,1:3)=0;
out(:,1)=s*1e3; 
out(:,2)=WL;
out(:,3)=WQ;

filename=[dir_out 'WakeLQ.txt'];
save(filename,'out','-ascii');
fileID = fopen(filename,'w');
fprintf(fileID,'%% %15s %16s %16s \n','s[mm]','Wlong[V/pC]','Wquad[V/pC/mm]');
fprintf(fileID,'%16.7e %16.7e %16.7e  \n',out');
fclose(fileID);

subplot(2,2,2)
plot(s,WL);ylabel('Wlo[V/pC]');xlabel('s[mm]');
subplot(2,2,4)
plot(s,WQ);ylabel('Wqu[V/pC/mm]');xlabel('s[mm]');

error_Wlo_in_procents=Nm*sum(Wcc(Nm+1,2:end).*Wcc(Nm+1,2:end))/sum(sum(Wcc(2:end,2:end).*Wcc(2:end,2:end)))*100,
error_Wqu_in_procents=Nm*sum(FQ(Nm,:).*FQ(Nm,:))/sum(sum(FQ.*FQ))*100,


Iz=load([dir_in 'Iz0.txt']); % Iz/c
filename='wakeL_01.txt';
w1=load([dir_in filename]);offset=w1(1,2);sigma=w1(2,2);
bunch(:,1)=Iz(:,1); 
bunch(:,2)=Iz(:,offset+3)*1e9; 
B=interp1(bunch(:,1),bunch(:,2),s,'linear',0);
[lossL,spreadL]=LossShape([s' B'],[s' WL']) %V/pC
[lossQ,spreadQ]=LossShape([s' B'],[s' -WQ']) %V/pC/mm