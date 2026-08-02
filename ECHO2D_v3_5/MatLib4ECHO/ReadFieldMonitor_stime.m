function [T Z R F kt kz kr D]= FieldMonitor_stime(FieldFile)
ff=fopen(FieldFile,'rt+');
Field=fscanf(ff,'%% Field=%s',1); 
timetype=fscanf(ff,' time=%s',1); 
D=fscanf(ff,' width=%g\n',1); 
In=fscanf(ff,'%% k_ct=%g h_ct=%g ct0=%g\n',3); 
kt=In(1); ht=In(2); t0=In(3); 
In=fscanf(ff,'%% k_r=%g h_r=%g r0=%g\n',3); 
kr=In(1); hr=In(2); r0=In(3);
In=fscanf(ff,'%% k_z=%g h_z=%g z0=%g\n',3); 
kz=In(1); hz=In(2); z0=In(3);
fclose(ff);
F=load(FieldFile);
R(1:kr)=0; for i=1:kr, R(i)=r0+hr*(i-1); end;
Z(1:kz)=0; for i=1:kz, Z(i)=z0+hz*(i-1); end;
T(1:kt)=0; for i=1:kt, T(i)=t0+ht*(i-1); end;


