%TOTAL field assembling for Hx,Ey,Ez 
% Eq. (3) from PRSTAB 18 (2015) 10401
clear all;close all;
MonitorNumber=1;
Nm=35;
dir_in='../../../ECHO2D/magn/';
dir_out=dir_in;
x0=0; % x-position of source
x=0;  % x-podition of observation

%%%%%%%%%%%%%% DODY %%%%%%%%%%%%%%%%%
filename_format='Monitor_m%02i_N%02i.txt';
FieldFile=[dir_in sprintf(filename_format,1,MonitorNumber)];
ff=fopen(FieldFile,'rt+');
Field=fscanf(ff,'%% Field=%s',1); 
timetype=fscanf(ff,' time=%s',1); 
D=fscanf(ff,' width=%g\n',1); 
fclose(ff);

if timetype=='s',
    [T Z R F kt kz kr]= ReadFieldMonitor_stime(FieldFile);
   else
    [T Z R F kt kz kr]=ReadFieldMonitor_ztime(FieldFile);
 end;
 
p=kz*kr+1; 
f=pi/D;
F(:,2:p)=F(:,2:p)*sin(f*(x0+0.5*D))*sin(f*(x+0.5*D));
N1=norm(F(:,2:p));
for k=2:Nm,
    m=2*k-1;
    f=pi/D*m;
    FieldFile=[dir_in sprintf(filename_format,m,MonitorNumber)];
    F1=load(FieldFile);
    F(:,2:p)=F(:,2:p)+F1(:,2:p)*sin(f*(x0+0.5*D))*sin(f*(x+0.5*D));
    N=norm(F(:,2:p));
    err=(N-N1)/N*100,
    N1=N;
end;
F(:,2:p)=F(:,2:p)/D*2;

filename_format='MonitorTotal_N%02i.txt';
FieldFile=[dir_in sprintf(filename_format,MonitorNumber)];

if timetype=='s',
    SaveFieldMonitor_stime(FieldFile,T,Z,R,F,kt,kz,kr,D,Field);
   else
    SaveFieldMonitor_ztime(FieldFile,T,Z,R,F,kt,kz,kr,D,Field);
 end;






