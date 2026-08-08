%Loss and Spread Calculation for ECHOz1
clear all;close all
%Input
dir='../../ECHOz2/';
%Body
path('../../../../MatLib4ECHO',path);
PhysConsts;
w=load([dir 'wakeL.dat']);
sigma=w(1,1); mode=w(1,2);
s=w(2:end,1);W=w(2:end,2);
[loss,spread,bunch]=LongLoss2(s,W,sigma);
K=max(abs(W))/max(abs(bunch));
subplot(2,1,1);
plot(s,bunch*K,s,W);
units='V/pC';
if mode>0, units=['V/pC/m^' int2str(2*mode)]; end;
title(['Long. wake, Loss=' num2str(loss) units ', Spread=' num2str(spread) units]);
xlabel('s[m]');ylabel(['W_|_|[' units ']']);
w=load([dir 'wakeT.dat']);
sigma=w(1,1); mode=w(1,2);
s=w(2:end,1);W=w(2:end,2);
[kick,rms_kick,bunch]=LongLoss2(s,-W,sigma);
K=max(abs(W))/max(abs(bunch));
subplot(2,1,2);
plot(s,bunch*K,s,W);
units='V/pC';
if mode>0, units=['V/pC/m^' int2str(2*mode-1)]; end;
title(['Trans. wake, Kick=' num2str(kick) units ', Spread=' num2str(rms_kick) units]);
xlabel('s[m]');ylabel(['W_T[' units ']']);

