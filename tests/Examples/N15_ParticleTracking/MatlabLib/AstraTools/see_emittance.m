clear all; close all;
PhysConsts;
s=[];betax=[];alphax=[];betay=[];alphay=[];E=[];emitx=[];emity=[];

r_optx=load('flash.Xemit.001');
r_opty=load('flash.Yemit.001');
r_optz=load('flash.Zemit.001');
r_E=r_optz(:,3)*1e6+E00; r_gamma=r_E*e/(me*c*c);
E=[E r_E'];
r_emitx=r_optx(:,6)*1e-6; r_sigmax=r_optx(:,4)*1e-3;
r_betax=r_sigmax.^2./r_emitx.*r_gamma;
r_emity=r_opty(:,6)*1e-6; r_sigmay=r_opty(:,4)*1e-3;
r_betay=r_sigmay.^2./r_emity.*r_gamma;
r_corx=r_optx(:,7)*1e-3.*r_sigmax; r_alphax=-r_corx./r_emitx.*r_gamma;
r_cory=r_opty(:,7)*1e-3.*r_sigmay; r_alphay=-r_cory./r_emity.*r_gamma;
s=[s r_optx(:,1)'];
betax=[betax r_betax'];betay=[betay r_betay'];
alphax=[alphax r_alphax'];alphay=[alphay r_alphay'];
emitx=[emitx r_emitx'];emity=[emity r_emity'];
plot(s,emitx,s,emity)
