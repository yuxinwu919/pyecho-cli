function [PD,dP]=CenterSlices(PD,M)
[PD, inds]=sortrows(PD,3);
z=PD(:,3);
[mx mxs mxx mxxs mxsxs emittx]=SliceAnalysis (z,PD(:,1),PD(:,4),M,false);
[my mys myy myys mysys emitty]=SliceAnalysis (z,PD(:,2),PD(:,5),M,false);
dP=[mx my mxs mys];
PD(inds,:)=PD;dP(inds,:)=dP;  
PD(:,1:2)=PD(:,1:2)-dP(:,1:2);
PD(:,4:5)=PD(:,4:5)-dP(:,3:4);  
