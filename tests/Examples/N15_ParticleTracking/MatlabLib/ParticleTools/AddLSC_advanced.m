function [dP, x, W] =AddLSC_advanced (P,q,v,z,emit,beta,gamma)
% [dP, x, W] =AddLSC_advanced (P,q,v,z,emit,beta,gamma)
% wakes in V/pC
% energy in MeV
 
 N=0.25*length(P(:,1));
 sig0=4*std(P(:,1))/sqrt(N);
 B=s_to_cur(P(:,1),sig0,q,v); 
 x=-flipud(B(:,1));bunch=flipud(B(:,2))/(c*q);
  
 W=-wake_LSC_advanced(x,bunch,z,emit,beta,gamma)*1e12*q;
 
x=-flipud(x);W=flipud(W);
dP=interp1(x,W,P(:,1),'linear',0)*1e-6;

 
