function SaveCSRtrackParticles(outfile,PD,Q,t0,orient)
%H x y z px py pz -> z x y pz px py
%V x y z px py pz -> z y -x pz py -px
if nargin<5, orient='H'; end;
n=length(PD(:,1));
for i=1:6, PD(2:n,i)=PD(2:n,i)-PD(1,i); end; %substract a reference particle
PD1(1:n+1,1:7)=0;
if orient=='H'
   PD1(2:n+1,1)=PD(:,3);PD1(2:n+1,2)=PD(:,1);PD1(2:n+1,3)=PD(:,2);
   PD1(2:n+1,4)=PD(:,6);PD1(2:n+1,5)=PD(:,4);PD1(2:n+1,6)=PD(:,5);
else %'V'
   PD1(2:n+1,1)=PD(:,3);PD1(2:n+1,2)=PD(:,2);PD1(2:n+1,3)=-PD(:,1);
   PD1(2:n+1,4)=PD(:,6);PD1(2:n+1,5)=PD(:,5);PD1(2:n+1,6)=-PD(:,4); 
end;
PD1(2:n+1,7)=Q/n*1e-9;  PD1(1,1)=t0; PD1(2,1)=t0;
save(outfile,'PD1', '-ASCII'); 

