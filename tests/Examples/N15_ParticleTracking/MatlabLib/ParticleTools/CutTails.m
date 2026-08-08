function [P1, N, inds]=CutTails(P0,iz,bounds)
sig0=std(P0(:,iz));
z0=P0(1,iz);
inds=find(P0(:,iz)>z0+sig0*bounds(1) & P0(:,iz)<z0+sig0*bounds(2));
N=length(inds);
P1(1:N,:)=P0(inds,:);
