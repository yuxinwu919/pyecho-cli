clear all; close all;
PhysConsts;
z0=-0.01; %start position in meters
astrafile='../ASTRA/dlw.0166.001'
echofile='../ECHO2D/InParticles/particles.in';
[PD Q]=LoadAstraParticles(astrafile); Q=Q*1e-9;
PD0=PD(:,1:6); PD=[];
PD0(:,3)=PD0(:,3)-PD0(1,3);
PD0(:,3)=PD0(:,3)+z0;
Np=length(PD0(:,1));
q0=Q/Np;
K=e/(me*c^2);
PD0(:,4:6)=PD0(:,4:6)*K; %p/(mc)
ff=fopen(echofile,'w');
p=[Np q0];
fwrite(ff,p,'double');
for i=1:6,
    fwrite(ff,PD0(:,i),'double');
end;
fclose(ff);
hist(PD0(:,3),200);
xlim([-0.016 -0.003])


break;
pz=PD(:,6);
[mx my mxx mxy myy emitt inds]=Moments(PD(:,1),PD(:,4),0);
xs_av=myy/mean(pz);

A=load('../ECHO2D/round/Iz.txt');
for i=1:20,
plot(A(:,1),A(:,i+1));hold on;
pause;
end;


