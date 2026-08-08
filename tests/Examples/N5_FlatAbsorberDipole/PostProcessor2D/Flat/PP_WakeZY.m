%Wz and Wy components for arbitrary offsets y0 and y; x0=x=0 
clear all;close all;
y0=30e-3; 
y=y0;

Ncc=8;
dir_in_cc='../../ECHO2D/magn/';
Nss=8;
dir_in_ss='../../ECHO2D/elec/';
dir_out='../../ECHO2D/';

path('../../../../MatLib4ECHO',path);
Wcc=load([dir_in_cc 'Wcc_odd.txt']);
Wss=load([dir_in_ss 'Wss_odd.txt']);
D=Wcc(1,1);
s=Wcc(1,2:end); ns=length(s);
Wy(1:ns)=0;
Wz(1:ns)=0;
Nm=length(Wcc(2:end,1));
Nm=min([Ncc Nm]);
f=Wcc(2:Nm+1,1);
Fz(1:Nm,1:ns)=0;
Fy(1:Nm,1:ns)=0;
for i=1:Nm,
        M=f(i);
        Fz(i,1:ns)=Wcc(i+1,2:end)*cosh(M*y)*cosh(M*y0)+Wss(i+1,2:end)*sinh(M*y)*sinh(M*y0);
        Fy(i,1:ns)=M*Wcc(i+1,2:end)*sinh(M*y)*cosh(M*y0)+M*Wss(i+1,2:end)*cosh(M*y)*sinh(M*y0);
        Wz=Wz+Fz(i,:);
        Wy=Wy+Fy(i,:);
end;
subplot(2,2,1);
mesh(s*1e3,f*1e-3,Fz*1e-3); zlabel('W_z(k,s)[V/pC]');xlabel('s[mm]');ylabel('k[1/mm]');
title(['offsets[mm]: y0=' num2str(y0*1e3) ' y=' num2str(y*1e3)]);
subplot(2,2,3);
mesh(s*1e3,f*1e-3,Fy*1e-3);zlabel('W_y(k,s)[V/pC]');xlabel('s[mm]');ylabel('k[1/mm]');
h=s(2)-s(1);
Wy=-IntegrTr(h,Wy);

s=s*1e3;
Wy=Wy*2/D*1e-3;
Wz=Wz*2/D*1e-3;

out(1:ns,1:3)=0;
out(:,1)=s; 
out(:,2)=Wz;
out(:,3)=Wy;

filename=[dir_out 'WakeZY.txt'];

fileID = fopen(filename,'w');
fprintf(fileID,'%% Offsets[mm]: y0=%14.7e      y=%14.7e \n',y0*1e3,y*1e3);
fprintf(fileID,'%% %15s %16s %16s \n','s[mm]','Wz[V/pC]','Wy[V/pC]');
fprintf(fileID,'%16.7e %16.7e %16.7e \n',out');
fclose(fileID);


subplot(2,2,2)
plot(s,Wz);ylabel('W_z[V/pC]');xlabel('s[mm]');
subplot(2,2,4)
plot(s,Wy); ylabel('W_y[V/pC]');xlabel('s[mm]');


error_Wy_in_procents=Nm*sum(Fy(Nm,:).*Fy(Nm,:))/sum(sum(Fy.*Fy))*100,
error_Wz_in_procents=Nm*sum(Fz(Nm,:).*Fz(Nm,:))/sum(sum(Fz.*Fz))*100,


