function [PD,dP]=CenterSlices_igor(PD,M)
[PD, inds]=sortrows(PD,3);
z=PD(:,3);
[mx mxs p p p p]=SliceAnalysis (z,PD(:,1),PD(:,4),M,false);
[my mys p p p p]=SliceAnalysis (z,PD(:,2),PD(:,5),M,false);
[mz mE p p p p]=SliceAnalysis (z,PD(:,2),PD(:,5),M,false);

dP=[mx my mxs mys mz mE];
PD(inds,:)=PD;dP(inds,:)=dP;  
PD(:,1:2)=PD(:,1:2)-dP(:,1:2);
PD(:,4:5)=PD(:,4:5)-dP(:,3:4);  
