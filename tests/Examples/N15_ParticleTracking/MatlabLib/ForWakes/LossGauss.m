function [loss,spread]=LossGauss(x,w,sigma)
%load('d:\wake.dat'); [loss,spread]=LossGauss(x,w,sigma)
h=x(2)-x(1);
bi2(1,:)=gauss(x,sigma);
loss=-bi2*w*h;
spread=sqrt(bi2*(w+loss).^2*h);
