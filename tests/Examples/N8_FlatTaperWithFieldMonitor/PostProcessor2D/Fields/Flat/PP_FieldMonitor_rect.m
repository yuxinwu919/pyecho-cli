clear all; close all;

PhysConsts;

%%%%%%%%% INPUT %%%%%%%%%%%%
FieldFile='../../../ECHO2D/magn/MonitorTotal_N01.txt';
% Point monitor position in m 
PM_z=0.03;PM_r=0.005; 

%%%%%%%%%%%%%%% BODY %%%%%%%%%%%%%
ff=fopen(FieldFile,'rt+');
Field=fscanf(ff,'%% Field=%s',1);
if Field(1)=='B', Field=['c' Field]; end; 
timetype=fscanf(ff,' time=%s\n',1); 
fclose(ff);
if timetype=='s',
    [T Z R F kt kz kr]= ReadFieldMonitor_stime(FieldFile);
    MeshPos(1:kt)= 0.0;
    lab='z [m]';
   else
    [T S R F kt ks kr]=ReadFieldMonitor_ztime(FieldFile);
     MeshPos= F(:,1);
     Z= -S; kz=ks;
    lab='s [m]';
 end;
 F(:,1)=[];

 %R=R-0.001;
 PM_Field(1:kt)=0;
 for i=1:kt,
        FF=-F(i,1:kr*kz);FF= reshape(FF, kz, kr)';
        PM_Field(i)=interp2(MeshPos(i)+Z,R,FF,PM_z,PM_r,'linear',0);
        subplot(2,1,1);  
        mesh(Z,R,FF);
        hold on;plot(PM_z-MeshPos(i),PM_r,'k.','MarkerSize',20);hold off;
        xlabel(lab);  ylabel('r [m]');zlabel([Field '/Q [V/m/nC]']);
        title(['Field = ' Field ' type=' timetype ' ct = ' num2str(T(i)) 'm']);
        subplot(2,1,2); 
        plot(T,PM_Field);
        title(['z = ' num2str(PM_z) '; r = ' num2str(PM_r)]);
        xlabel('ct [m]');ylabel([Field '/Q [V/m/nC]']);
        pause(0.01);
    end;

%%%%%%%%%%% OUTPUT %%%%%%%%%%%%%
out(:,1)=T; out(:,2)=PM_Field; 
save('PointMonitor.txt','out','-ascii');
Er=2/PM_r*1/sqrt(2*pi)/0.005*1/(4*pi*eps0)*1e-9




