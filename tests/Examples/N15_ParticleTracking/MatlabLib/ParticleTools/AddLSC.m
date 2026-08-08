function [dE, x, W] =AddLSC (P,q,v,E0,E1,L,beta,emit,M)
%[P, x, W] =AddWakeL (P,q,v,w0_file,w1_file,RLC_file)
% wakes in V/pC
% energy in MeV
 if nargin<9, M=0.1; end;
 PhysConsts;
 gamma0=e*E0/(me*c*c)*1e6;
 gamma1=e*E1/(me*c*c)*1e6;
 
 rb0=sqrt(emit*beta/gamma0);
 
 sig0=M*std(P(:,1));
 B=s_to_cur(P(:,1),sig0,q,v); 
 x=-flipud(B(:,1));bunch=flipud(B(:,2))/(c*q);
  
 W=-wake_LSC(x,bunch,rb0,gamma0,gamma1,L)*1e12*q;
 
x=-flipud(x);W=flipud(W);
dE=interp1(x,W,P(:,1),'linear',0)*1e-6;

 
