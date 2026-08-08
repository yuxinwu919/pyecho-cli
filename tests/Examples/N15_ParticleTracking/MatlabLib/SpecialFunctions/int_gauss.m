function y=int_gauss(x,sigma)
y=0.5+0.5*erf(x/(sigma*sqrt(2)));