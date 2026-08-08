function y=gauss(x,sigma)
% y=gauss(x,sigma)
y=exp(-x.*x/(2*sigma*sigma))/(sigma*sqrt(2*pi));