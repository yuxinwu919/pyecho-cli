function [m sig]=FuncMoments(x,y)
norm=Int0(x,y);
y=y/norm;
f=x.*y;
m=Int0(x,f);
x=x-m;
f=x.*x.*y;
sig=sqrt(Int0(x,f));
