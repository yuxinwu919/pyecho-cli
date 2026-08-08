function [PD1, Q]=LoadAstraParticles(infile)
PD=load(infile); 
n=length(PD(:,1)); Q=abs(sum(PD(:,8)));
PD(2:n,3)=PD(2:n,3)+PD(1,3);PD(2:n,6)=PD(2:n,6)+PD(1,6); %add reference particle
%PD1=PD(:,1:6); 
inds=find(PD(:,10)>=0); % exclude lost particles
PD1=PD(inds,1:6);  

