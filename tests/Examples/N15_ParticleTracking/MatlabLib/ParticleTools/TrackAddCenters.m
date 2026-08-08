function PD=TrackAddCenters(PD0,PD,dP,M,cols)
 [PD, inds]=sortrows(PD,3); PD0=PD0(inds,:); dP=dP(inds,:); 
 n=length(PD(:,1)); 
 for i=1:M:n,
   i0=i; i1=i0+M-1; if i1>n, i1=n; end;  
    X=PD0(i0:i1,:)'*PD0(i0:i1,:); Y=PD0(i0:i1,:)'*PD(i0:i1,cols);  
    A=(inv(X)*Y)';   dP0=(A*dP(i0:i1,:)')'; PD(i0:i1,cols)=PD(i0:i1,cols)+dP0; %shift slices back
 end;
 PD(inds,:)=PD;  