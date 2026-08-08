%% electrostatic solver to find the initial field through Lorentz transform
%% magnetic boundary conditions at z-directions (to be changed)
clear all; close all;
PhysConsts;

%%%%%%%%%%%%%% INPUT %%%%%%%%%%%%%%
ParticleFile='../ECHO2D/InParticles/particles.in';
FieldFile='../ECHO2D/InField/Field_00.bin';
MeshPositionZ=-0.003; %initial position of the mesh head in meters  
a=0.2e-2; %pipe radius in meters
StepZ=0.5e-04; %mesh steps
StepY=StepZ;
MeshLength=400; %mesh length 
CurrentFilter=1; %smoothing parameter

%%%%%%%%%%%%%% BODY %%%%%%%%%%%%%%%
nz=MeshLength+6; hr=StepY; hz=StepZ; 
zMeshHead=MeshPositionZ; FilterOrder=CurrentFilter;

ff=fopen(ParticleFile,'r');
p=fread(ff,2,'double');
Np=p(1); q0=p(2);
PD0(1:Np,1:6)=0.0;
for i=1:6,
    PD0(1:Np,i)=fread(ff,Np,'double');
end;
fclose(ff);

nr=floor(a/hr)+1;
r(1:nr)=[1:nr]*hr;
[Ro]=Particles2Charge(zMeshHead,nz,nr,hz,hr,PD0);
q2 = q0*Z0 / (hz*hr * 2 * pi);
Ro = Ro*q2;
%filter
if FilterOrder>0,
    for i=1:FilterOrder,
    Ro(1:nz-1,:)=0.5*(Ro(1:nz-1,:)+Ro(2:nz,:));
    Ro(2:nz,:)=0.5*(Ro(2:nz,:)+Ro(1:nz-1,:));
    end;
end;

pz = mean(PD0(:,6));
gamma = sqrt(pz*pz + 1); 
betaz = pz / gamma;
hz=hz*gamma;
epsr(1:nr)=0;
for i=1:nr,
    b=r(i)+0.5*hr;
    if b<a, 
        epsr(i)=1; 
    else
        if r(i)-0.5*hr<a, 
            epsr(i)=1/(1-(b-a)/hr); 
        end;
    end;
end;
muez=epsr;

epsz(1:nz)=1; epsz(1)=1;
epsz(nz-1)=1; epsz(nz)=0;
%magnetic
epsz(1)=2;epsz(nz-1)=2;

epsz=epsz/(hz*hz);
epsr=epsr/(hr*hr).*r;
nn=nr*nz;
Pz=sparse(nn,nn);
EpsR=sparse(nn,nn);
EpsZ=sparse(nn,nn);
Pr=sparse(nn,nn);
for i=1:nz,
    i,
    for j=1:nr,
        ind=(i-1)*nr+j;
        Pz(ind,ind)=-1;
        Pr(ind,ind)=-1;
        EpsR(ind,ind)=epsr(j);
        EpsZ(ind,ind)=epsz(i)*(r(j)-0.5*hr);
        ind1=ind+nr;
        if (i<nz), Pz(ind,ind1)=1; end;
        if (j<nr), Pr(ind,ind+1)=1; end;
    end;
end;

p(1:nn)=1;
p(1:nr)=0;p(nn-nr:nn)=0;
p([1:nz]*nr)=0;
zeilen = find(p);
P0=sparse(1:nn,1:nn,p);
P=P0(zeilen,1:nn);

A=P*(Pz'*EpsZ*Pz+Pr'*EpsR*Pr)*P';

Ro0(1:nn,1)=0;
for i=1:nz,
    for j=1:nr-1,
       ind=(i-1)*nr+j;
       Ro0(ind)=Ro(i,j+1);
    end;
end;

Ro0=P*Ro0;
tol = 1e-6; maxit=3000,
fi =P'*symmlq(A,Ro0,tol,maxit);
Ez=-Pz*fi/hz/gamma; Er=Pr*fi/hr; hz=hz/gamma;

Ex0(1:nz,1:nr+1)=0;Ey0(1:nz,1:nr+1)=0;Ez0(1:nz,1:nr+1)=0;
Hx0(1:nz,1:nr+1)=0;Hy0(1:nz,1:nr+1)=0;Hz0(1:nz,1:nr+1)=0;
for i=2:nz-1,
    for j=2:nr,
        ind=(i-1)*nr+j-1;
        Ex0(i,j)=(0.5*Ez(ind)+0.5*Ez(ind-nr));
        Ey0(i,j)=Er(ind);
        Hz0(i,j)=Er(ind)*r(j-1)*betaz*muez(j-1);
    end;
end;
mesh(Ex0);

ff=fopen(FieldFile,'w');
p=[nz nr+1];
fwrite(ff,p,'long');
fwrite(ff,Ex0','double');
fwrite(ff,Ey0','double');
fwrite(ff,Ez0','double');
fwrite(ff,Hx0','double');
fwrite(ff,Hy0','double');
fwrite(ff,Hz0','double');
fclose(ff);


