function y=DiffL(h,x)
n=length(x);	
y(1)=0;
for j=2:n,
	y(j)=2*(x(j)-x(j-1))-y(j-1);
end;
y=y/h;