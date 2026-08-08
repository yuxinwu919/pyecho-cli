function [i0 r]=FindRefParticle(PD,col,weight,m)
if nargin<4, m=6; end;
for i=1:m;
    x0=mean(PD(:,i));
    PD(:,i)=PD(:,i)-x0;
    sig0=std(PD(:,i));
    PD(:,i)=abs(PD(:,i));
    if sig0>0,PD(:,i)=PD(:,i)/sig0;end;
end;
PD(:,col)=PD(:,col)*weight;
[r,i0]=min(sum(PD'));
