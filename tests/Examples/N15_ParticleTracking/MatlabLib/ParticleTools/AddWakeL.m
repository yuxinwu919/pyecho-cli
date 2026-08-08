function [dP, x, W] =AddWakeL (P,q,v,w0_file,w1_file,RLC_file,Length,M)
%[P, x, W] =AddWakeL (P,q,v,w0_file,w1_file,RLC_file)
% wakes in V/pC
% energy in MeV
 PhysConsts;
 if nargin<8, M=0.1; end;
 if nargin<7, Length=1; end;
 %N=0.25*length(P(:,1));
 %sig0=M*std(P(:,1))/sqrt(N);
 sig0=M*std(P(:,1));
 B=s_to_cur(P(:,1),sig0,q,v); 
 x=-flipud(B(:,1));bunch=flipud(B(:,2))/(c*q);
 d1_bunch=Der(x,bunch);
 
 nb=length(x);
 W0=0; W1=0;WC=0;WR=0; WL=0; WC=0;
 if ~strcmp(w0_file,'0'),
    w0=load(w0_file);
    ww=wakeconvolution([x,bunch],w0); 
    W0=-ww(1:nb,2)*q;
 end;
 if ~strcmp(w1_file,'0'),
   w1=load(w1_file);
   ww=wakeconvolution([x d1_bunch],w1);
   W1=-ww(1:nb,2)*c*q;
 end;
 if ~strcmp(RLC_file,'0'),
   RLC=load(RLC_file); R=RLC(1);   L=RLC(2); Cinv=RLC(3);
   WR=-bunch*R*c*q;
   WL=-d1_bunch*L*c*c*q;
   if Cinv~=0,
      int_bunch=Int1(x,bunch); 
      WC=-int_bunch*Cinv*q; 
    end;
end;
 W=Length*(W0+W1+WR+WL+WC)*1e12;
 
x=-flipud(x);W=flipud(W);
dP=interp1(x,W,P(:,1),'linear',0)*1e-6;
 
