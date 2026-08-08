function dL=VelocityBunching(E0,dE,L)
PhysConsts;
if L>0,
   E0=E0*1e6; e0=E0(1);
   e1=e0+dE*1e6;
   P0=sqrt(E0.*E0-E00*E00); p0=P0(1);
   alpha=(e1-e0)/L;
   if alpha==0, %drift
      ct0=e0/p0*L;
      dL=P0./E0*ct0-L;
   else % constant acceleration during the same time
      p1=sqrt(e1*e1-E00*E00);
      ct0=(p1-p0)/alpha;
      P1=P0+ct0*alpha;
      E1=sqrt(E00*E00+P1.*P1);
      dL=(E1-E0)/alpha-L;
   end;
else
    dL=0;
end;
