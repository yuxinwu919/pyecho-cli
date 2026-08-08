clear all; close all;
PhysConsts;
echofile='/Users/zagor/dataxxl/Example_CANDLE/round/Particles_019501.bin';
astrafile='../ECHO2D/round/particles.ast';
ff=fopen(echofile,'r');
p=fread(ff,2,'double');
Np=p(1); q0=p(2);
PD0(1:Np,1:7)=0.0;
for i=1:6,
    PD0(1:Np,i)=fread(ff,Np,'double');
end;
PD0(1:Np,7)=fread(ff,Np,'long');
fclose(ff);
inds=find(PD0(:,7)==1);
plot(PD0(:,1),PD0(:,2),'.',PD0(inds,1),PD0(inds,2),'k.')
PD0(inds,:)=[];

K=(me*c^2)/e;
PD0(:,4:6)=PD0(:,4:6)*K;
Q=q0*Np*1e9;
SaveAstraParticles(astrafile,PD0,Q);

return;



%check
[PD Q]=LoadAstraParticles(astrafile); Q=Q*1e-9;
PD0=PD(:,1:6);PD=[];
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
hist(PD0(:,3),52);


