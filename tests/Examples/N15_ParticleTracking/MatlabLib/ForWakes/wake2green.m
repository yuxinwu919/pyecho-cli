function [x y]=wake2green(x0,y0)
%converts wakepotential to Green function crudely
n0=length(x0); dx=x0(2)-x0(1);
i0=interp1(x0,[1:n0],0);
n=n0-i0+1;
x(1:n)=0;y(1:n)=0;
for i=1:n,
    x(i)=(i-1)*dx;
    y(i)=y0(i+i0-1);
    if (i<=i0), y(i)=y(i)+y0(i0-i+1);end;
end;
