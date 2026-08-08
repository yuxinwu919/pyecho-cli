function SaveAstraParticles(outfile,PD,Q,findref,z0)
%SaveAstraParticles(outfile,PD,Q,findref,z0)
n=length(PD(:,1));
if nargin<4, findref=false; end;
if findref,
    i0=FindRefParticle(PD,3,10);  
    P0=PD(1,:);PD(1,:)=PD(i0,:); PD(i0,:)=P0;
    PD(2:n,:)=sortrows(PD(2:n,:),3);
end;
PD(2:n,3)=PD(2:n,3)-PD(1,3);PD(2:n,6)=PD(2:n,6)-PD(1,6); %substract reference particle
PD1(1:n,1:10)=0; PD1(:,1:6)=PD(:,1:6);
PD1(:,8)=-Q/n; PD1(:,9)=1; PD1(:,10)=5;

if nargin==5, PD1(1,3)=z0; end;
save(outfile,'PD1', '-ASCII'); 

