clear all; close all;
PhysConsts;
quiet=1;
sigmaz=1e-3; %in RMS in m 
Npz=10000;   % number of particles 
ds=1/Npz;

Particles(1:Npz,1)=0;

for i=1:Npz,
    Particles(i,1)=(i-0.5)*ds;           % z
end;

% to Gauss
Particles(:,1)=(Particles(:,1)-0.5)+0.5;
Particles(:,1)=sqrt(2)*sigmaz*erfinv(2*Particles(:,1)-1)+5*sigmaz;

hist(Particles(:,1),300)
ff=fopen('ECHO2D\particles.in','w');
fwrite(ff,Npz,'double');
fwrite(ff,Particles,'double');
fclose(ff);
 