function Y=Int1(x,y)
n=length(x);
Y(1:n,1)=0;
Y(1)=0;

for i=2:n,
    Y(i)=Y(i-1)+0.5*(y(i)+y(i-1))*(x(i)-x(i-1));
    %Y(i)=Y(i-1)+y(i)*(x(i)-x(i-1));
end;