function PD=Centre(PD, bounds, flags)
%function PD=Centre(PD, bounds, flags)
% substract mean values
z0=mean( PD(:,3)); sig0=std(PD(:,3));
inds=find(PD(:,3)>=z0+sig0*bounds(1) & PD(:,3)<=z0+sig0*bounds(2));
for i=1:6,
   if flags(i),    PD(:,i)=PD(:,i)-mean(PD(inds,i));   end;
end;

