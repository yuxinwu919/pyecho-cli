function [P Q z0]=LoadAstraParticles2D(infile)
PD=load(infile); 
n=length(PD(:,1));
PD(2:n,3)=PD(2:n,3)+PD(1,3);
PD(2:n,6)=PD(2:n,6)+PD(1,6); %add reference particle
P(1:n,1:2)=0; P(1:n,1)=PD(:,3); %in m
P(1:n,2)=PD(:,6)*1e-6; %in MeV
Q=sum(PD(:,8))*1e-9; %total charge