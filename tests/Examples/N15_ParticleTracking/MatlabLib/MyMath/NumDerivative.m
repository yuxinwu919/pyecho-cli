function [x1 y1]=NumDerivative(x,y)
dx=diff(x); dy=diff(y);
y1=dy./dx;
n=length(x);
x1=0.5*(x(1:n-1)+x(2:n));
