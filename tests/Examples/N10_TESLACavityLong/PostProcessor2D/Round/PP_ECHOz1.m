%Loss and Spread Calculation for ECHOz1
clear all;close all
%Input
dir='../../ECHOz1/';
%Body
path('../../../../MatLib4ECHO',path);
PhysConsts;
w=load([dir 'wake.dat']);
sigma=w(1,1);
s=w(2:end,1);W=w(2:end,2);
[loss,spread,bunch]=LongLoss2(s,W,sigma);
K=max(abs(W))/max(abs(bunch));
plot(s,bunch*K,s,W);
title(['Longitudinal wake, Loss=' num2str(loss) 'V/pC, Spread=' num2str(spread) 'V/pC']);
xlabel('s[m]');ylabel('W_|_|[V/pC]');

