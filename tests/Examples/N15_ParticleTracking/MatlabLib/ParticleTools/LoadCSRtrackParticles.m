function [PD1,Q,t0]=LoadCSRtrackParticles(infile,orient)
%H z x y pz px py -> x y z px py pz
%V z x y pz px py -> -y x z -py px pz 
if nargin<2, orient='H'; end;
PD=load(infile);
n=length(PD(:,1))-1;
Q=sum(PD(2:n+1,7))*1e9; t0=PD(1,1);
if orient=='H',
   PD1(:,1)=PD(2:n+1,2);PD1(:,2)=PD(2:n+1,3);PD1(:,3)=PD(2:n+1,1);
   PD1(:,4)=PD(2:n+1,5);PD1(:,5)=PD(2:n+1,6);PD1(:,6)=PD(2:n+1,4);
else
   PD1(:,1)=-PD(2:n+1,3);PD1(:,2)=PD(2:n+1,2);PD1(:,3)=PD(2:n+1,1);
   PD1(:,4)=-PD(2:n+1,6);PD1(:,5)=PD(2:n+1,5);PD1(:,6)=PD(2:n+1,4); 
end;    
for i=1:6, PD1(2:n,i)=PD1(2:n,i)+PD1(1,i); end; %add a reference particle

