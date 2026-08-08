function dy=Der(x,y)
n=length(x);
dy(1:n,1)=0;
dy(1)=(y(2)-y(1))/(x(2)-x(1));
dy(n)=(y(n)-y(n-1))/(x(n)-x(n-1));
for i=2:n-1,
    dy(i)=(y(i+1)-y(i-1))/(x(i+1)-x(i-1));
end;