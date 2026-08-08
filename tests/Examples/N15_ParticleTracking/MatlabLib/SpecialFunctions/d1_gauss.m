function y=d1_gauss(x,sigma)
y=-x.*exp(-x.*x/(2*sigma*sigma))/((sigma^3)*sqrt(2*pi));