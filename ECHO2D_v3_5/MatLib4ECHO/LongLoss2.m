function [loss,spread, bunch]=LongLoss2(x,w,sigma)
%x and sigma in cm!!!
%[loss,spread,bunch]=LongLoss2(wake(:,1),wake(:,2),sigma)
h=x(2)-x(1);
bunch(1,:)=gauss(x,sigma);
loss=-bunch*w*h;
spread=sqrt(bunch*(w+loss).^2*h);
