function [PD1 inds]=PhaseAdvance(PD,bounds,psi)
 PD1=PD;
 z0=mean( PD(:,3)); sig0=std(PD(:,3));
 inds=find(PD(:,3)>z0+sig0*bounds(1) & PD(:,3)<z0+sig0*bounds(2));
 [mx mxs mxx mxxs mxsxs emitx0]=Moments(PD(inds,1),PD(inds,4));
 beta=mxx/emitx0;alpha=-mxxs/emitx0 ;
 M=MfromTwiss([alpha beta 0],[alpha beta psi]);
 PD1(:,1)=M(1,1)*PD(:,1)+M(1,2)*PD(:,4);
 PD1(:,4)=M(2,1)*PD(:,1)+M(2,2)*PD(:,4);
 [mx mxs mxx mxxs mxsxs emitx0]=Moments(PD(inds,2),PD(inds,5));
 beta=mxx/emitx0; alpha=-mxxs/emitx0 ;
 M=MfromTwiss([alpha beta 0],[alpha beta psi]);
 PD1(:,2)=M(1,1)*PD(:,2)+M(1,2)*PD(:,5);
 PD1(:,5)=M(2,1)*PD(:,2)+M(2,2)*PD(:,5);


  

 
 
 
 
 
 
 
      
