function [u,s,z]=ReadMainOutput(OutMainFile)
% M nz Ns dz ds s0 zPowerGap_mon sPowerGap_mon
ff=fopen(OutMainFile,'rt+');
%fgets(ff);
In=fscanf(ff,'%%%g %g %g %g %g %g %g %g');
M=In(1); nz=In(2); Ns=In(3); 
dz=In(4);	ds=In(5); s0=In(6); 
zPowerGap_mon=In(7); sPowerGap_mon=In(8);
fclose(ff);
u=load(OutMainFile);

Ns0=0;nz0=0;
for j=1:Ns,
    if (mod(j-1,sPowerGap_mon)==0),
        Ns0=Ns0+1;  
     end;
end;
for j=1:zPowerGap_mon:nz+1,
     nz0=nz0+1;  
end;
s(1:Ns0)=s0+([0:Ns0-1])*ds*sPowerGap_mon;
z(1:nz0)=[0:nz0-1]*dz*zPowerGap_mon;