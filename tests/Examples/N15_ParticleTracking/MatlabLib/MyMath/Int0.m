function Y=Int0(x,y)
n=length(x);
Y=y(1)*0.5*(x(2)-x(1));
for i=2:n-1,
    dx=0.5*(x(i+1)-x(i-1));
    Y=Y+y(i)*dx;
end;
Y=Y+y(n)*0.5*(x(n)-x(n-1));
